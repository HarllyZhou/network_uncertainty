from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS


def winsorize(series: pd.Series, lower: float, upper: float) -> pd.Series:
    clean = series.dropna()
    if clean.empty:
        return series
    return series.clip(clean.quantile(lower), clean.quantile(upper))


def make_outcome(panel: pd.DataFrame, fe_col: str, sigma_col: str) -> pd.DataFrame:
    out = panel.copy()
    positive = out[sigma_col] > 0
    out.loc[positive, "q"] = out.loc[positive, fe_col].pow(2) / out.loc[positive, sigma_col].pow(2)
    out.loc[~np.isfinite(out["q"]), "q"] = np.nan
    return out


def panel_regression(
    panel: pd.DataFrame,
    sigma_col: str,
    *,
    log_sigma: bool = False,
    lag_controls: bool = False,
    sector_time_effects: bool = False,
) -> tuple[pd.DataFrame, object]:
    work = panel.copy().sort_values(["firm_id", "date"])
    regressor = "log_sigma" if log_sigma else sigma_col
    if log_sigma:
        work[regressor] = np.log(work[sigma_col].where(work[sigma_col] > 0))
    controls = ["output_growth", "price_growth"]
    if lag_controls:
        for col in controls:
            work[col] = work.groupby("firm_id", sort=False)[col].shift(1)
    cols = ["q", regressor, *controls, "firm_id", "date", "sector"]
    work = work[cols].dropna(subset=["q", regressor, "firm_id", "date"])
    # Controls can be sparse in SBU; retain the sample and make missingness explicit.
    for col in controls:
        work[f"{col}_missing"] = work[col].isna().astype(float)
        work[col] = work[col].fillna(0.0)
    work = work.set_index(["firm_id", "date"])
    xcols = [regressor, *controls, *(f"{c}_missing" for c in controls)]
    # Sparse survey modules can make a control or missingness flag constant in a
    # particular rolling-window sample. Such columns contain no identifying variation.
    xcols = [col for col in xcols if col == regressor or work[col].nunique(dropna=True) > 1]
    other = None
    time_effects = not sector_time_effects
    if sector_time_effects:
        date_text = work.index.get_level_values("date").astype(str)
        other = pd.DataFrame(
            {"sector_time": work["sector"].fillna("Unknown").astype(str) + "::" + date_text},
            index=work.index,
        )
    model = PanelOLS(
        work["q"], work[xcols], entity_effects=True, time_effects=time_effects,
        other_effects=other, drop_absorbed=True, check_rank=False,
    )
    fit = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    table = pd.DataFrame(
        {
            "term": fit.params.index,
            "coefficient": fit.params.values,
            "std_error": fit.std_errors.values,
            "t_stat": fit.tstats.values,
            "p_value": fit.pvalues.values,
            "nobs": fit.nobs,
            "rsquared_within": fit.rsquared_within,
        }
    )
    return table, fit


def conditional_bins(
    panel: pd.DataFrame,
    sigma_col: str,
    fe_col: str,
    n_bins: int = 5,
) -> tuple[pd.DataFrame, np.ndarray]:
    work = panel[["firm_id", sigma_col, fe_col]].dropna().copy()
    work = work[work[sigma_col] > 0]
    _, edges = pd.qcut(work[sigma_col], n_bins, retbins=True, duplicates="drop")
    edges[0], edges[-1] = -np.inf, np.inf
    work["bin"] = pd.cut(work[sigma_col], edges, labels=False, include_lowest=True)
    stats = _bin_stats(work, sigma_col, fe_col)
    return stats, edges


def _bin_stats(work: pd.DataFrame, sigma_col: str, fe_col: str) -> pd.DataFrame:
    def summarize(group: pd.DataFrame) -> pd.Series:
        mean_sigma2 = group[sigma_col].pow(2).mean()
        ratio = group[fe_col].var(ddof=1) / mean_sigma2 if mean_sigma2 > 0 else np.nan
        mean_q = (group[fe_col].pow(2) / group[sigma_col].pow(2)).mean()
        return pd.Series(
            {"mean_sigma": group[sigma_col].mean(), "ratio_of_moments": ratio,
             "mean_normalized_fe2": mean_q, "nobs": len(group),
             "n_firms": group["firm_id"].nunique()}
        )
    return work.groupby("bin", observed=True).apply(summarize, include_groups=False).reset_index()


def firm_bootstrap_bins(
    panel: pd.DataFrame,
    sigma_col: str,
    fe_col: str,
    edges: np.ndarray,
    reps: int,
    seed: int,
) -> pd.DataFrame:
    base = panel[["firm_id", sigma_col, fe_col]].dropna().copy()
    base = base[base[sigma_col] > 0]
    base["bin"] = pd.cut(base[sigma_col], edges, labels=False, include_lowest=True)
    firms = base["firm_id"].unique()
    groups = {firm: g for firm, g in base.groupby("firm_id", sort=False)}
    rng = np.random.default_rng(seed)
    draws = []
    for rep in range(reps):
        sampled = rng.choice(firms, size=len(firms), replace=True)
        pieces = [groups[firm].assign(_draw=j) for j, firm in enumerate(sampled)]
        draw = pd.concat(pieces, ignore_index=True)
        stat = _bin_stats(draw, sigma_col, fe_col)
        stat["rep"] = rep
        draws.append(stat)
    boot = pd.concat(draws, ignore_index=True)
    intervals = (
        boot.groupby("bin")[["ratio_of_moments", "mean_normalized_fe2"]]
        .quantile([0.025, 0.975]).unstack()
    )
    intervals.columns = [f"{metric}_{'lo' if q == 0.025 else 'hi'}" for metric, q in intervals.columns]
    return intervals.reset_index()


def structural_mapping(bins: pd.DataFrame) -> pd.DataFrame:
    out = bins.copy()
    r = out["ratio_of_moments"]
    out["tau2_model_implied"] = np.where((r >= 0) & (r < 1), r / (1 - r), np.nan)
    out["structural_mapping_valid"] = (r >= 0) & (r < 1)
    return out
