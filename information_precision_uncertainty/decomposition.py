from __future__ import annotations

from math import erfc, sqrt

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS


FE_SPECS = {
    "none": (False, False),
    "firm": (True, False),
    "firm_time": (True, True),
}


def prepare_decomposition(
    panel: pd.DataFrame, sigma_col: str
) -> tuple[pd.DataFrame, float]:
    out = panel.copy()
    out["fe2"] = out["sales_fe"].pow(2)
    out["sigma2"] = out[sigma_col].pow(2)
    out["normalized_fe2"] = out["fe2"] / out["sigma2"]
    positive = out.loc[out["fe2"] > 0, "fe2"]
    # One percent of the median positive squared error is small but scale-aware.
    log_offset = float(0.01 * positive.median())
    out["log_fe2_c"] = np.log(out["fe2"] + log_offset)
    out["log_sigma2"] = np.log(out["sigma2"].where(out["sigma2"] > 0))
    return out, log_offset


def _normal_two_sided(t_stat: float) -> float:
    return erfc(abs(t_stat) / sqrt(2.0))


def _normal_upper_tail(t_stat: float) -> float:
    return 0.5 * erfc(t_stat / sqrt(2.0))


def diagnostic_regression(
    panel: pd.DataFrame,
    outcome: str,
    regressor: str,
    fe_spec: str,
) -> dict[str, float | str | int]:
    if fe_spec not in FE_SPECS:
        raise ValueError(f"unknown fixed-effect specification: {fe_spec}")
    entity_effects, time_effects = FE_SPECS[fe_spec]
    controls = ["output_growth", "price_growth"]
    columns = [outcome, regressor, *controls, "firm_id", "date"]
    work = panel[columns].dropna(subset=[outcome, regressor, "firm_id", "date"]).copy()
    for col in controls:
        work[f"{col}_missing"] = work[col].isna().astype(float)
        work[col] = work[col].fillna(0.0)
    work = work.set_index(["firm_id", "date"])
    xcols = [regressor, *controls, *(f"{col}_missing" for col in controls)]
    xcols = [col for col in xcols if col == regressor or work[col].nunique() > 1]
    if not entity_effects and not time_effects:
        work["constant"] = 1.0
        xcols.append("constant")
    model = PanelOLS(
        work[outcome], work[xcols], entity_effects=entity_effects,
        time_effects=time_effects, drop_absorbed=True, check_rank=False,
    )
    fit = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    coefficient = float(fit.params[regressor])
    std_error = float(fit.std_errors[regressor])
    t_zero = coefficient / std_error
    result: dict[str, float | str | int] = {
        "outcome": outcome,
        "regressor": regressor,
        "fixed_effects": fe_spec,
        "coefficient": coefficient,
        "std_error": std_error,
        "t_stat_zero": t_zero,
        "p_value_zero_two_sided": float(fit.pvalues[regressor]),
        "nobs": int(fit.nobs),
        "r_squared": float(fit.rsquared),
    }
    if outcome == "log_fe2_c" and regressor.startswith("log_"):
        t_one = (coefficient - 1.0) / std_error
        result.update(
            {
                "null_value": 1.0,
                "t_stat_eta_eq_1": t_one,
                "p_value_eta_eq_1_two_sided": _normal_two_sided(t_one),
                "p_value_eta_gt_1_one_sided": _normal_upper_tail(t_one),
            }
        )
    return result


def decomposition_table(panel: pd.DataFrame, sigma_col: str) -> pd.DataFrame:
    models = [
        ("fe2", sigma_col),
        ("fe2", "sigma2"),
        ("log_fe2_c", "log_sigma2"),
        ("normalized_fe2", sigma_col),
    ]
    rows = []
    for outcome, regressor in models:
        for fe_spec in FE_SPECS:
            try:
                rows.append(diagnostic_regression(panel, outcome, regressor, fe_spec))
            except (ValueError, np.linalg.LinAlgError) as exc:
                rows.append(
                    {"outcome": outcome, "regressor": regressor,
                     "fixed_effects": fe_spec, "error": str(exc)}
                )
    return pd.DataFrame(rows)


def add_leave_one_out_states(panel: pd.DataFrame, sigma_col: str) -> pd.DataFrame:
    out = panel.copy()
    out["_sigma2_state"] = out[sigma_col].pow(2)
    for keys, prefix in [(["date"], "aggregate"), (["sector", "date"], "sector")]:
        grouped = out.groupby(keys, dropna=False)["_sigma2_state"]
        total = grouped.transform("sum") - out["_sigma2_state"]
        count = grouped.transform("count") - out["_sigma2_state"].notna().astype(int)
        state_sigma2 = total / count.where(count > 0)
        out[f"{prefix}_sigma_loo"] = np.sqrt(state_sigma2)
        out[f"log_{prefix}_sigma2_loo"] = np.log(state_sigma2.where(state_sigma2 > 0))
    return out.drop(columns="_sigma2_state")


def state_volatility_table(panel: pd.DataFrame) -> pd.DataFrame:
    designs = [
        ("aggregate", "normalized_fe2", "aggregate_sigma_loo", "firm"),
        ("aggregate", "log_fe2_c", "log_aggregate_sigma2_loo", "firm"),
        ("sector", "normalized_fe2", "sector_sigma_loo", "firm_time"),
        ("sector", "log_fe2_c", "log_sector_sigma2_loo", "firm_time"),
    ]
    rows = []
    for state, outcome, regressor, effects in designs:
        try:
            row = diagnostic_regression(panel, outcome, regressor, effects)
            row["state"] = state
            rows.append(row)
        except (ValueError, np.linalg.LinAlgError) as exc:
            rows.append(
                {"state": state, "outcome": outcome, "regressor": regressor,
                 "fixed_effects": effects, "error": str(exc)}
            )
    return pd.DataFrame(rows)


def decomposition_bins(
    panel: pd.DataFrame, sigma_col: str, n_bins: int, reps: int, seed: int
) -> pd.DataFrame:
    work = panel[["firm_id", sigma_col, "fe2", "normalized_fe2"]].dropna().copy()
    work = work[work[sigma_col] > 0]
    work["bin"], edges = pd.qcut(
        work[sigma_col], n_bins, labels=False, retbins=True, duplicates="drop"
    )

    def summarize(frame: pd.DataFrame) -> pd.DataFrame:
        return (
            frame.groupby("bin", observed=True)
            .agg(mean_sigma=(sigma_col, "mean"), mean_fe2=("fe2", "mean"),
                 mean_normalized_fe2=("normalized_fe2", "mean"), nobs=("fe2", "size"),
                 n_firms=("firm_id", "nunique"))
            .reset_index()
        )

    point = summarize(work)
    firms = work["firm_id"].unique()
    groups = {firm: group for firm, group in work.groupby("firm_id", sort=False)}
    rng = np.random.default_rng(seed)
    draws = []
    edges[0], edges[-1] = -np.inf, np.inf
    for rep in range(reps):
        sampled = rng.choice(firms, size=len(firms), replace=True)
        draw = pd.concat([groups[firm].assign(_draw=j) for j, firm in enumerate(sampled)])
        draw["bin"] = pd.cut(draw[sigma_col], edges, labels=False, include_lowest=True)
        stats = summarize(draw)
        stats["rep"] = rep
        draws.append(stats)
    bootstrap = pd.concat(draws, ignore_index=True)
    intervals = (
        bootstrap.groupby("bin")[["mean_fe2", "mean_normalized_fe2"]]
        .quantile([0.025, 0.975]).unstack()
    )
    intervals.columns = [
        f"{metric}_{'lo' if quantile == 0.025 else 'hi'}"
        for metric, quantile in intervals.columns
    ]
    return point.merge(intervals.reset_index(), on="bin", how="left")
