# Information precision and uncertainty

This module tests whether firms' forecast errors become large relative to their
own fundamental volatility when volatility is high. The baseline uses the public,
de-identified Atlanta Fed Survey of Business Uncertainty (SBU) sales panel.

## Empirical design

For firm `i` responding in month `t`, the code matches its one-year-ahead sales
forecast only to its own realization exactly 12 calendar months later. Realized
sales growth is reconstructed from reported current-sales levels using the same
Davis–Haltiwanger–Schuh growth rate used by the SBU forecast. There is no nearest
date match, interpolation, or future fill.

For each firm, ARMA(p,q) models with a constant and linear trend are compared for
`p,q in {0,...,4}`. BIC is the baseline selection criterion and AIC is available by
configuration. Because the dependent variable is already a growth rate, `d=0`.
Firm fits run in bounded worker processes, and each candidate has a documented
optimizer iteration cap so a pathological nonconvergent fit cannot stall the run.
For a selected AR order `p`, the first `p-1` observations are excluded and the
usable residual sequence begins at `y_p`, following the requested indexing
convention. At every calendar date, volatility is the sample standard deviation
of the last observed residuals strictly before that date.

The baseline aligns volatility to the **forecast target date**, not the forecast
origin. A forecast made in January 2022 for January 2023 is paired with the same
firm's January 2023 volatility by an exact firm/date join. It is never paired with
January 2022 volatility, a nearest date, or an interpolated value. The analysis
panel retains `date`, `target_date`, origin-date `sigma_w*`, and target-date
`sigma_target_w*` columns so this timing is directly auditable.

SBU firms alternate between sales and employment forms. Six, nine, and twelve
sales responses therefore correspond approximately to 12, 18, and 24 calendar
months. Six responses is the completed-data baseline because longer windows leave
insufficient within-firm variation after exact horizon matching; all three remain
in the robustness output. Exact elapsed time varies when a firm misses a wave,
and the analysis panel retains the actual dates.

The main regression is

```text
FE(t+12)^2 / sigma(t+12)^2 = firm FE + forecast-origin date FE
                  + beta*sigma(t+12)
                  + current output growth + current price growth + error.
```

Standard errors are clustered by firm and date. Missing controls are retained
using zero imputation plus missing-value indicators because the price question is
available only in a subset of SBU waves. Robustness output includes log volatility,
winsorized forecast errors, lagged controls, sector-by-date effects, and alternative
rolling windows. A second run with `criterion: aic` supplies the requested AIC
model-selection robustness.

The conditional-moment output reports both
`Var(FE | bin) / E[sigma^2 | bin]` and `E[FE^2 / sigma^2 | bin]`, with firm-level
bootstrap confidence intervals. The Gaussian mapping `tau^2 = R/(1-R)` is emitted
only where `0 <= R < 1`; elsewhere it is marked invalid rather than extrapolated.

## Run

From the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r information_precision_uncertainty/requirements.txt
.venv/bin/python -m information_precision_uncertainty.download_sbu
.venv/bin/python -m information_precision_uncertainty.cli \
  --config information_precision_uncertainty/config/sbu_baseline.yaml
```

On machines whose numerical libraries create their own thread pools, avoid CPU
oversubscription with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` before the command.

The matched AIC robustness configuration is `config/sbu_short_panel_aic.yaml`.
A fast end-to-end check is:

```bash
.venv/bin/python -m information_precision_uncertainty.cli \
  --config information_precision_uncertainty/config/sbu_smoke.yaml
.venv/bin/pytest information_precision_uncertainty/tests
```

`config/sbu_short_panel.yaml` is the completed-data specification shipped with
this module. It restricts `p,q` to 0--2 because the public SBU sales stream is
effectively bimonthly and only 274 firms have 12 reconstructed growth observations.
The unrestricted `sbu_baseline.yaml` keeps the 0--4 grid requested for a longer run.
Set `reuse_checkpoint: true` to rerun tables and figures from an existing analysis
panel without repeating firm-level model selection.

## Outputs

- `analysis_panel.parquet`: timing-auditable observation-level data.
- `arima_orders.csv`: selected firm models and information criteria.
- `regressions.csv`: baseline and robustness coefficient tables.
- `conditional_bins.csv`: both normalized conditional moments, bootstrap bands,
  and the model-implied signal-noise variance.
- `conditional_variance.png` and `model_implied_tau2.png`: requested figures.
- `diagnostics.json`: sample counts and standardized-innovation checks.
- `diagnostic_regressions.csv`: numerator, variance, elasticity, and normalized-error
  regressions under no fixed effects, firm effects, and firm-plus-time effects.
- `state_volatility_regressions.csv`: leave-one-out aggregate and sector-state tests.
- `diagnostic_bins.csv` and `diagnostic_decomposition.png`: separate binned numerator
  and normalized-error moments with firm-bootstrap confidence intervals.
- `firm_data_availability.csv`: outcome-specific panel-depth audit. The public SBU
  file currently has too few repeated price-growth reports per firm to estimate
  the requested firm-level price ARIMA reliably; the matched price errors are
  retained and the binding panel-depth count is reported rather than presenting
  an underidentified price exercise.

## Interpretation limits

A positive volatility coefficient or upward conditional-moment plot supports the
specific claim that forecast errors rise relative to estimated fundamental
variance. Larger raw forecast errors alone do not establish lower information
quality. The structural `tau^2` series is a Gaussian-benchmark interpretation, not
a direct measure. This module does not invoke endogenous information acquisition,
rational inattention, managerial attention, or endogenous learning effort.

## Data provenance

The data downloader uses the Atlanta Fed's official public SBU microdata archive.
The raw file is intentionally ignored by git. Microdata are updated over time, so
archive the download date or checksum for a frozen replication release.

Official references: [Atlanta Fed SBU overview](https://www.atlantafed.org/research-and-data/surveys/business-uncertainty),
[public microdata request/download page](https://www.atlantafed.org/forms/research/surveys/survey-microdata-sbu/survey-microdata-sbu-request-thank-you),
and [Surveying Business Uncertainty](https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research/publication/working-paper/2019/06/17/surveying-business-uncertainty.pdf).
