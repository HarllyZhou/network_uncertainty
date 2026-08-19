# Network Uncertainty

This repository contains a theory and empirical project on production networks, credit conditions, and aggregate uncertainty.

The paper draft is the center of the project. The data pipeline is supporting infrastructure for taking the model to firm-level evidence.

## Project Idea

The draft studies how uncertainty can be formed and propagated through a production network when firms face working-capital needs and financial frictions.

The current theoretical environment has:

```text
monopolistically competitive firms by sector
Cobb-Douglas production with labor and intermediate inputs
sector-level productivity risk and uncertainty shocks
working-capital borrowing
financial intermediaries
credit spreads and borrowing capacity affected by uncertainty
households and monetary policy
```

The empirical side is meant to discipline and test related mechanisms using firm financial statements, disclosed supplier-customer links, and financial uncertainty measures.

## Repository Structure

```text
draft/
  draft.tex
  draft.pdf
  network_uncertainty.bib
  aer.bst
  archive/

literature/
  arellano_bai_kehoe.tex
  arellano_bai_kehoe.pdf
  jermann_quadrini.tex
  jermann_quadrini.pdf

src/baseline_pipeline/
  build_baseline.py
  config.py
  name_matching.py
  optional_networks.py
  regressions.py
  transforms.py
  variables.py
  wrds_extract.py

config/
  pipeline_config.example.yaml
  pipeline_config.yaml

data/
  raw/
  interim/
  processed/
  output/
  logs/
```

## Draft

Main paper draft:

```text
draft/draft.tex
```

Compiled PDF:

```text
draft/draft.pdf
```

Bibliography:

```text
draft/network_uncertainty.bib
```

The current title in the draft is:

```text
Production Networks and Formation of Aggregate Uncertainty
```

## Literature Notes

The `literature/` folder contains notes on papers that are useful for the model:

```text
Arellano, Bai, and Kehoe: financial frictions and volatility shocks
Jermann and Quadrini: financial shocks, enforcement constraints, working capital
```

The bibliography already includes production-network, uncertainty, financial-friction, and trade-credit references.

## Empirical Pipeline

The empirical pipeline builds a firm-year panel from:

```text
Compustat Fundamentals Annual
Compustat Segment customer disclosures
Jurado-Ludvigson-Ng financial uncertainty
optional supply-chain robustness datasets
```

Main command:

```bash
python -m src.baseline_pipeline.build_baseline --config config/pipeline_config.yaml
```

If local downloaded raw files are already available:

```bash
python -m src.baseline_pipeline.build_baseline --skip-wrds --config config/pipeline_config.yaml
```

For faster development runs:

```bash
python -m src.baseline_pipeline.build_baseline --skip-wrds --skip-regressions --config config/pipeline_config.yaml
```

If WRDS login or table access fails, the pipeline stops gracefully and writes:

```text
data/logs/wrds_access_check.log
```

## Empirical Objects

Firm financial statements from Compustat provide:

```text
assets
cash
accounts payable
accounts receivable
short-term debt
long-term debt
sales
cost of goods sold
employment
capital expenditure
```

Trade-credit variables:

```text
ap_cogs = accounts payable / cost of goods sold
ar_sales = accounts receivable / sales
net_trade_credit_assets = (accounts receivable - accounts payable) / assets
ap_assets = accounts payable / assets
ar_assets = accounts receivable / assets
```

Network variables:

```text
supplier_gvkey -> customer_gvkey
edge_weight = sales to customer when available
pagerank
in_degree
out_degree
weighted_in_degree
weighted_out_degree
customer_hhi
supplier_hhi
supplier/customer fragility exposure
```

Financial uncertainty variables:

```text
FU_mean_year
FU_max_year
FU_q4_year
FU_dec_year
FU_lag1
FU_lag2
```

## Customer Matching

Compustat customer-segment data often reports customer names rather than clean customer firm identifiers.

The pipeline therefore has a conservative deterministic name-matching module:

```text
src/baseline_pipeline/name_matching.py
```

It:

```text
normalizes company names
removes legal suffixes
expands common abbreviations
matches exact normalized names by year
keeps ambiguous matches separate
does not force fuzzy matches into the baseline
```

This creates an observed public-firm core network. It should not be interpreted as the full economy-wide production network.

## What The Data Can Say

With Compustat and customer-segment data, the project can study:

```text
firm-level trade-credit adjustment
liquidity and debt responses to financial uncertainty
heterogeneity by supplier-customer network position
exposure to financially fragile counterparties in the observed public-firm network
```

The clean empirical interpretation is:

```text
firm-level trade-credit adjustment along disclosed supplier-customer relationships
```

## What The Data Cannot Say Alone

Compustat Fundamentals Annual cannot directly observe:

```text
firm A delays a specific invoice payment to firm B
firm A changes payment terms on a specific link
invoice due dates or payment dates
link-level payment delinquency
```

For direct evidence of `A delays payment to B`, the project would need link-level invoice or payment data with:

```text
buyer_id
supplier_id
invoice_date
due_date
payment_date
invoice_amount
payment_terms
```

This distinction matters for the paper. The model can be about link-level payment delay, while the baseline Compustat empirics are a firm-level proxy unless stronger payment data are added.

## Configuration

Main config:

```text
config/pipeline_config.yaml
```

Important fields:

```yaml
paths:
  financial_uncertainty: "data/raw/macro_finance_uncertainty_202602_update/FinancialUncertaintyToCirculate.xlsx"
  factset_revere: ""
  factset_supply_chain: ""
  capital_iq_supply_chain: ""

pipeline:
  start_year: 1976
  end_year:
  financial_uncertainty_value_column: "h=12"
  compute_expensive_network_metrics: false
```

`compute_expensive_network_metrics` controls betweenness and eigenvector centrality. PageRank, degree, weighted degree, HHI, and fragility exposure variables still run when this is `false`.

## Outputs

Final empirical panel:

```text
data/processed/analysis_panel_compustat_customer.csv
data/processed/analysis_panel_compustat_customer.parquet
```

Summary tables:

```text
data/output/tables/sample_coverage_by_year.csv
data/output/tables/summary_statistics.csv
data/output/tables/correlation_matrix.csv
data/output/tables/network_coverage.csv
data/output/tables/merge_rates.csv
```

Diagnostic regressions:

```text
data/output/regression_checks/diagnostic_regressions.txt
data/output/regression_checks/diagnostic_regressions.csv
```

## Current Roadmap

1. Finish the benchmark model in `draft/draft.tex`.
2. Clarify which model objects map to firm-level Compustat variables and which require link-level payment data.
3. Add outside-demand exposure variables from unmatched customer names and sales-to-customer values.
4. Run baseline trade-credit regressions without network interactions.
5. Add network interactions using the conservative matched public-firm network.
6. Decide whether the paper needs additional invoice/payment data to support the stronger `A delays payment to B` interpretation.

## Core Limitations

1. Public-firm network data are not the full production network.
2. Compustat customer-segment links mainly capture disclosed major customers.
3. Customer-name matching gives an observed public-firm core network, not a complete economy-wide network.
4. Accounts payable and accounts receivable are firm-level trade-credit stocks, not link-level payment delays.
5. `dlc` is short-term debt or current debt, not bank credit.
6. The empirical sample is listed firms and disclosed supplier-customer links.

