from __future__ import annotations

import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA


@dataclass(frozen=True)
class SelectedOrder:
    firm_id: str
    p: int
    d: int
    q: int
    criterion: str
    score: float
    nobs: int


def _fit_one_firm(args):
    firm_id, y, criterion, max_ar, max_ma, optimizer_maxiter = args
    best = None
    values = y.to_numpy()
    for p in range(max_ar + 1):
        for q in range(max_ma + 1):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = ARIMA(
                        values, order=(p, 0, q), trend="ct",
                        enforce_stationarity=True, enforce_invertibility=True,
                    ).fit(
                        method_kwargs={"warn_convergence": False, "maxiter": optimizer_maxiter}
                    )
                score = float(getattr(fit, criterion))
                if np.isfinite(score) and (best is None or score < best[0]):
                    best = (score, p, q, np.asarray(fit.resid))
            except (ValueError, np.linalg.LinAlgError):
                continue
    if best is None:
        return None
    score, p, q, residual_values = best
    residual = pd.Series(residual_values, index=y.index)
    # User-specified convention: discard the first p-1 observations and begin
    # the usable innovation series at y_p (one-based indexing).
    burn = max(p - 1, 0)
    if burn:
        residual.iloc[:burn] = np.nan
    return residual, SelectedOrder(str(firm_id), p, 0, q, criterion, score, len(y))


def select_and_fit_firm_arima(
    panel: pd.DataFrame,
    value_col: str = "realized_sales_growth",
    criterion: str = "bic",
    max_ar: int = 4,
    max_ma: int = 4,
    min_obs: int = 18,
    n_jobs: int = 1,
    optimizer_maxiter: int = 75,
) -> tuple[pd.Series, pd.DataFrame]:
    """Select low-order firm ARMA models and return date-aligned innovations.

    Growth is not mechanically differenced (d=0). A linear trend plus intercept is
    used whenever estimable. Model fitting may use the full firm history, but the
    downstream volatility statistic shifts residuals before rolling, so it never
    contains the current or a future residual.
    """
    if criterion not in {"aic", "bic"}:
        raise ValueError("criterion must be aic or bic")
    tasks = []
    for firm_id, group in panel.groupby("firm_id", sort=False):
        y = group[value_col].dropna().astype(float)
        if len(y) >= min_obs:
            tasks.append((firm_id, y, criterion, max_ar, max_ma, optimizer_maxiter))
    if n_jobs == 1:
        results = list(map(_fit_one_firm, tasks))
    else:
        try:
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                results = list(executor.map(_fit_one_firm, tasks, chunksize=1))
        except (PermissionError, OSError):
            # Some managed research environments disallow process semaphores.
            results = list(map(_fit_one_firm, tasks))
    innovations = pd.Series(np.nan, index=panel.index, dtype=float, name="innovation")
    selected: list[SelectedOrder] = []
    for result in results:
        if result is None:
            continue
        residual, order = result
        innovations.loc[residual.index] = residual
        selected.append(order)
    return innovations, pd.DataFrame([x.__dict__ for x in selected])


def add_backward_volatility(
    panel: pd.DataFrame,
    innovation_col: str,
    windows: list[int],
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Add sigma_W using residuals strictly before the row's forecast date."""
    result = panel.sort_values(["firm_id", "date"]).copy()
    for window in windows:
        required = window if min_periods is None else min_periods
        def historical_sd(values: pd.Series) -> pd.Series:
            history: list[float] = []
            estimates: list[float] = []
            for value in values.to_numpy():
                recent = history[-window:]
                estimates.append(
                    float(np.std(recent, ddof=1)) if len(recent) >= required else np.nan
                )
                if np.isfinite(value):
                    history.append(float(value))
            return pd.Series(estimates, index=values.index)

        result[f"sigma_w{window}"] = result.groupby("firm_id", sort=False)[
            innovation_col
        ].transform(historical_sd)
        result[f"std_innovation_w{window}"] = result[innovation_col] / result[f"sigma_w{window}"]
    return result.sort_index()


def add_target_date_volatility(panel: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    """Attach same-firm volatility measured exactly at each forecast's target date."""
    target_cols = [f"sigma_target_w{window}" for window in windows]
    result = panel.drop(columns=target_cols, errors="ignore").copy()
    volatility_cols = [f"sigma_w{window}" for window in windows]
    lookup = result[["firm_id", "date", *volatility_cols]].copy()
    lookup = lookup.rename(
        columns={
            "date": "target_date",
            **{col: col.replace("sigma_w", "sigma_target_w") for col in volatility_cols},
        }
    )
    return result.merge(
        lookup, on=["firm_id", "target_date"], how="left", validate="many_to_one"
    )
