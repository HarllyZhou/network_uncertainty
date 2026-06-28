from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import load_config
from .name_matching import add_simple_customer_name_matches
from .optional_networks import load_optional_network_edges
from .regressions import run_diagnostic_regressions
from .transforms import (
    build_network_measures,
    finalize_panel,
    prepare_edges,
    prepare_financials,
    read_financial_uncertainty,
    write_summary_tables,
)
from .wrds_extract import (
    connect_wrds,
    discover_customer_segment_tables,
    extract_customer_segments,
    extract_fundamentals,
    find_first_table,
    inspect_libraries,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the baseline Compustat customer-network panel.")
    parser.add_argument("--config", default=None, help="Path to YAML config. Defaults to config/pipeline_config.yaml.")
    parser.add_argument("--skip-wrds", action="store_true", help="Use existing raw extracts in data/raw.")
    parser.add_argument("--skip-regressions", action="store_true", help="Skip optional diagnostic regressions.")
    return parser.parse_args(argv)


def _write_wrds_access_log(log_path: Path, exc: BaseException) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    message = [
        f"WRDS access check failed at {timestamp}.",
        "",
        "The pipeline stopped before WRDS extraction. This is expected if the WRDS account",
        "is not approved yet, credentials are not configured, or the required WRDS libraries",
        "and tables are not available to the account.",
        "",
        "No generated repo structure, config templates, source files, or scripts were removed.",
        "After WRDS approval is active, rerun:",
        "python -m src.baseline_pipeline.build_baseline --config config/pipeline_config.yaml",
        "",
        "Error:",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    log_path.write_text("\n".join(message), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cfg = load_config(args.config)
    cfg.outputs.ensure()

    if args.skip_wrds:
        fundamentals_path = cfg.outputs.raw / "compustat_fundamentals_annual.csv"
        customer_path = cfg.outputs.raw / "compustat_customer_segments_raw.csv"
        fundamentals_raw = pd.read_csv(fundamentals_path, parse_dates=["datadate"])
        customer_raw = pd.read_csv(customer_path)
        if cfg.start_year is not None:
            fundamentals_raw = fundamentals_raw.loc[
                pd.to_numeric(fundamentals_raw["fyear"], errors="coerce").ge(cfg.start_year)
            ].copy()
            customer_raw = customer_raw.loc[
                pd.to_numeric(customer_raw["year"], errors="coerce").ge(cfg.start_year)
            ].copy()
        if cfg.end_year is not None:
            fundamentals_raw = fundamentals_raw.loc[
                pd.to_numeric(fundamentals_raw["fyear"], errors="coerce").le(cfg.end_year)
            ].copy()
            customer_raw = customer_raw.loc[
                pd.to_numeric(customer_raw["year"], errors="coerce").le(cfg.end_year)
            ].copy()
    else:
        try:
            conn = connect_wrds()
            inspect_libraries(conn, cfg.outputs.interim)
            fundamentals_table = find_first_table(
                conn,
                cfg.values["wrds"]["fundamentals_library_candidates"],
                cfg.values["wrds"]["fundamentals_table_candidates"],
            )
            pd.DataFrame(
                [{"library": fundamentals_table.library, "table": fundamentals_table.table}]
            ).to_csv(cfg.outputs.interim / "selected_fundamentals_table.csv", index=False)
            fundamentals_raw = extract_fundamentals(conn, fundamentals_table, cfg.start_year, cfg.end_year)
            fundamentals_raw.to_csv(cfg.outputs.raw / "compustat_fundamentals_annual.csv", index=False)

            segment_tables = discover_customer_segment_tables(
                conn,
                cfg.values["wrds"]["customer_segment_library_candidates"],
                cfg.values["wrds"]["customer_segment_keywords"],
                cfg.outputs.interim,
            )
            customer_raw = extract_customer_segments(conn, segment_tables, cfg.start_year, cfg.end_year)
            customer_raw.to_csv(cfg.outputs.raw / "compustat_customer_segments_raw.csv", index=False)
        except Exception as exc:
            log_path = cfg.outputs.logs / "wrds_access_check.log"
            _write_wrds_access_log(log_path, exc)
            print(f"WRDS access check failed. Details were written to {log_path}.")
            print("Generated repo structure and scripts are intact; rerun after WRDS approval is active.")
            return 0

    financials = prepare_financials(fundamentals_raw, cfg.outputs.interim)
    financials.to_csv(cfg.outputs.interim / "financials_with_ratios.csv", index=False)

    customer_raw = add_simple_customer_name_matches(customer_raw, financials, cfg.outputs.interim)
    customer_raw.to_csv(cfg.outputs.interim / "customer_segments_with_simple_name_matches.csv", index=False)
    edges, _unmatched = prepare_edges(customer_raw, cfg.outputs.interim)
    optional_edges_raw = load_optional_network_edges(cfg.optional_network_paths)
    if not optional_edges_raw.empty:
        optional_edges, _ = prepare_edges(optional_edges_raw, cfg.outputs.interim)
        edges = pd.concat([edges, optional_edges], ignore_index=True, sort=False).drop_duplicates()
        edges.to_csv(cfg.outputs.interim / "clean_compustat_customer_edges.csv", index=False)
    network = build_network_measures(
        edges,
        financials,
        compute_expensive_metrics=cfg.compute_expensive_network_metrics,
    )
    network.to_csv(cfg.outputs.interim / "network_measures_compustat_customer.csv", index=False)

    fu = (
        read_financial_uncertainty(cfg.fu_path, cfg.financial_uncertainty_value_column)
        if cfg.fu_path
        else None
    )
    if fu is not None:
        fu.to_csv(cfg.outputs.interim / "financial_uncertainty_annual.csv", index=False)

    panel = finalize_panel(financials, network, fu)
    if cfg.write_csv:
        panel.to_csv(cfg.outputs.processed / "analysis_panel_compustat_customer.csv", index=False)
    if cfg.write_parquet:
        parquet_path = cfg.outputs.processed / "analysis_panel_compustat_customer.parquet"
        try:
            panel.to_parquet(parquet_path, index=False)
        except ImportError as exc:
            (parquet_path.with_suffix(".parquet.SKIPPED.txt")).write_text(
                f"Parquet output was skipped because no parquet engine is installed: {exc}\n",
                encoding="utf-8",
            )

    write_summary_tables(panel, edges, cfg.outputs.tables)

    if cfg.run_diagnostic_regressions and not args.skip_regressions:
        run_diagnostic_regressions(panel, cfg.outputs.regressions)

    print("Baseline panel build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
