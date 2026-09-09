from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .arima import add_backward_volatility, add_target_date_volatility, select_and_fit_firm_arima
from .config import AnalysisConfig
from .decomposition import (
    add_leave_one_out_states,
    decomposition_bins,
    decomposition_table,
    prepare_decomposition,
    state_volatility_table,
)
from .estimation import (
    conditional_bins,
    firm_bootstrap_bins,
    make_outcome,
    panel_regression,
    structural_mapping,
    winsorize,
)
from .plots import plot_bins, plot_decomposition, plot_structural_mapping
from .sbu import load_sbu


def _diagnostics(panel: pd.DataFrame, window: int) -> dict[str, float | int]:
    z = panel[f"std_innovation_w{window}"].replace([np.inf, -np.inf], np.nan).dropna()
    return {
        "panel_rows": int(len(panel)),
        "firms": int(panel["firm_id"].nunique()),
        "matched_sales_forecasts": int(panel["sales_fe"].notna().sum()),
        "analysis_rows": int(panel["q"].notna().sum()),
        "standardized_innovation_mean": float(z.mean()),
        "standardized_innovation_std": float(z.std(ddof=1)),
    }


def run(config: AnalysisConfig) -> None:
    output = config.output_dir
    output.mkdir(parents=True, exist_ok=True)
    panel_checkpoint = output / "analysis_panel.parquet"
    orders_checkpoint = output / "arima_orders.csv"
    if config.reuse_checkpoint and panel_checkpoint.exists() and orders_checkpoint.exists():
        panel = pd.read_parquet(panel_checkpoint)
        orders = pd.read_csv(orders_checkpoint)
    else:
        panel = load_sbu(config.raw_data)
        if config.max_firms:
            eligible = panel.groupby("firm_id")["realized_sales_growth"].count()
            keep = eligible.sort_values(ascending=False).head(config.max_firms).index
            panel = panel[panel["firm_id"].isin(keep)].copy()

        panel["innovation"], orders = select_and_fit_firm_arima(
            panel, criterion=config.criterion, max_ar=config.max_ar, max_ma=config.max_ma,
            min_obs=config.min_arima_obs, n_jobs=config.n_jobs,
            optimizer_maxiter=config.optimizer_maxiter,
        )
    # Always rebuild this cheap step, including from checkpoints, so window changes
    # and corrected timing logic propagate without repeating ARIMA selection.
    panel = add_backward_volatility(
        panel, "innovation", config.windows, config.min_rolling_obs,
    )
    panel = add_target_date_volatility(panel, config.windows)

    availability = (
        panel.groupby("firm_id")
        .agg(
            sales_growth_observations=("realized_sales_growth", "count"),
            matched_sales_forecasts=("sales_fe", "count"),
            price_growth_observations=("price_growth", "count"),
            matched_price_forecasts=("price_fe", "count"),
        )
        .reset_index()
    )
    availability.to_csv(output / "firm_data_availability.csv", index=False)

    sigma_prefix = "sigma_target_w" if config.volatility_alignment == "target" else "sigma_w"
    sigma = f"{sigma_prefix}{config.baseline_window}"
    panel = make_outcome(panel, "sales_fe", sigma)
    panel["sales_fe_winsor"] = winsorize(panel["sales_fe"], config.winsor_lower, config.winsor_upper)
    panel["q_winsor"] = panel["sales_fe_winsor"].pow(2) / panel[sigma].pow(2)

    # Checkpoint expensive model-selection work before downstream specifications.
    orders.to_csv(output / "arima_orders.csv", index=False)
    panel.to_parquet(output / "analysis_panel.parquet", index=False)

    specifications = []
    variants = [
        ("baseline", False, False, False, "q"),
        ("log_volatility", True, False, False, "q"),
        ("lagged_controls", False, True, False, "q"),
        ("sector_time_fe", False, False, True, "q"),
        ("winsorized_fe", False, False, False, "q_winsor"),
    ]
    for label, log_sigma, lag_controls, sector_time, outcome in variants:
        work = panel.copy()
        work["q"] = work[outcome]
        try:
            table, _ = panel_regression(
                work, sigma, log_sigma=log_sigma, lag_controls=lag_controls,
                sector_time_effects=sector_time,
            )
            table.insert(0, "specification", label)
            specifications.append(table)
        except (ValueError, np.linalg.LinAlgError) as exc:
            specifications.append(pd.DataFrame({"specification": [label], "error": [str(exc)]}))

    for window in config.windows:
        col = f"{sigma_prefix}{window}"
        work = make_outcome(panel, "sales_fe", col)
        try:
            table, _ = panel_regression(work, col)
            table.insert(0, "specification", f"window_{window}")
            specifications.append(table)
        except (ValueError, np.linalg.LinAlgError) as exc:
            specifications.append(pd.DataFrame({"specification": [f"window_{window}"], "error": [str(exc)]}))
    regressions = pd.concat(specifications, ignore_index=True, sort=False)

    bins, edges = conditional_bins(panel, sigma, "sales_fe", config.n_bins)
    intervals = firm_bootstrap_bins(
        panel, sigma, "sales_fe", edges, config.bootstrap_reps, config.seed,
    )
    bins = structural_mapping(bins.merge(intervals, on="bin", how="left"))

    decomposition_panel, log_offset = prepare_decomposition(panel, sigma)
    decomposition = decomposition_table(decomposition_panel, sigma)
    state_panel = add_leave_one_out_states(decomposition_panel, sigma)
    state_regressions = state_volatility_table(state_panel)
    diagnostic_bins = decomposition_bins(
        decomposition_panel, sigma, config.n_bins, config.bootstrap_reps, config.seed + 1,
    )

    regressions.to_csv(output / "regressions.csv", index=False)
    bins.to_csv(output / "conditional_bins.csv", index=False)
    decomposition.to_csv(output / "diagnostic_regressions.csv", index=False)
    state_regressions.to_csv(output / "state_volatility_regressions.csv", index=False)
    diagnostic_bins.to_csv(output / "diagnostic_bins.csv", index=False)
    plot_bins(bins, output / "conditional_variance.png")
    plot_decomposition(diagnostic_bins, output / "diagnostic_decomposition.png")
    plot_structural_mapping(bins, output / "model_implied_tau2.png")
    diagnostics = _diagnostics(panel, config.baseline_window)
    diagnostics.update(
        {"criterion": config.criterion, "baseline_window": config.baseline_window,
         "bootstrap_reps": config.bootstrap_reps,
         "volatility_alignment": config.volatility_alignment,
         "volatility_column": sigma,
         "target_volatility_matches": int(panel[sigma].notna().sum()),
         "log_fe2_offset": log_offset,
         "matched_price_forecasts": int(panel["price_fe"].notna().sum()),
         "firms_with_12_price_growth_observations": int(
             (availability["price_growth_observations"] >= 12).sum()
         )}
    )
    (output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
