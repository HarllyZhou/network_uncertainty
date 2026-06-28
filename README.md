# Baseline Compustat Customer-Network Pipeline

This workspace builds a baseline firm-year panel combining Compustat Fundamentals Annual, Compustat Customer Segment supplier-customer links, and an annualized financial uncertainty series.

## Setup

Install dependencies in your preferred environment:

```bash
python -m pip install -r requirements.txt
```

Copy the example config and fill in the financial uncertainty file path:

```bash
cp config/pipeline_config.example.yaml config/pipeline_config.yaml
```

The WRDS connection uses the standard `wrds` Python package behavior. Configure WRDS credentials via your local WRDS setup before running.

## Run

```bash
python -m src.baseline_pipeline.build_baseline --config config/pipeline_config.yaml
```

If WRDS login or table access is not active yet, the command stops gracefully and writes:

```text
data/logs/wrds_access_check.log
```

The generated repo structure, config templates, source files, and scripts remain in place. Once WRDS approval is active, rerun the same command.

If raw WRDS extracts already exist at `data/raw/compustat_fundamentals_annual.csv` and `data/raw/compustat_customer_segments_raw.csv`, run:

```bash
python -m src.baseline_pipeline.build_baseline --skip-wrds --config config/pipeline_config.yaml
```

## WRDS Discovery

The pipeline first writes `data/interim/wrds_libraries.csv`, then locates the Fundamentals Annual table from configured candidates. It also searches configured WRDS libraries for customer-segment table candidates and writes the inspected metadata to `data/interim/wrds_customer_segment_table_candidates.csv`.

The default Fundamentals candidate is `comp.funda`, but the code checks WRDS metadata before extraction.

## Outputs

Final panel:

- `data/processed/analysis_panel_compustat_customer.parquet`
- `data/processed/analysis_panel_compustat_customer.csv`

Summary tables:

- `data/output/tables/sample_coverage_by_year.csv`
- `data/output/tables/summary_statistics.csv`
- `data/output/tables/correlation_matrix.csv`
- `data/output/tables/network_coverage.csv`
- `data/output/tables/merge_rates.csv`

Optional diagnostics:

- `data/output/regression_checks/diagnostic_regressions.txt`
- `data/output/regression_checks/diagnostic_regressions.csv`

## Interpretation Notes

- `dlc` is treated as short-term debt or current debt, not bank credit.
- `ap_cogs` measures trade credit received from suppliers.
- `ar_sales` measures trade credit provided to customers.
- `net_trade_credit_assets` measures the net trade-credit position.

## Limitations

1. Public-firm network data are not the full production network.
2. Compustat customer-segment links mainly capture disclosed major customers.
3. The baseline network is closer to the extensive margin than the full intensive transaction network unless sales-to-customer values are available.
4. Accounts payable and accounts receivable are firm-level trade-credit stocks, not link-level payment delays.
5. DLC is short-term debt, not necessarily bank credit.
6. The analysis is about listed firms and disclosed supplier-customer links, not all firms in the economy.
