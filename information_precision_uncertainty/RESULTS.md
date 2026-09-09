# Results: target-date volatility specification

## Construction implemented

For a forecast made at `t` for `t+12`, the analysis constructs the exact same-firm
forecast error and attaches volatility measured at `t+12`:

```text
forecast at t -> realization and FE at t+12 -> sigma measured at t+12
```

Firm ARMA models are fitted to realized sales growth. If the selected model has
AR order `p`, the first `p-1` observations are discarded and the usable residual
sequence begins at `y_p`, following the requested convention. Target-date
volatility uses the last 6 observed residuals strictly before the target date;
9- and 12-residual windows are robustness checks.

The saved panel exposes both timing concepts: `sigma_w6` is origin-row volatility
and `sigma_target_w6` is the target-date variable actually used in the regressions.

## Sample

- Public Atlanta Fed SBU data through February 2026.
- 53,186 firm-wave rows and 4,549 firms.
- 9,326 exact 12-month forecast-realization matches.
- BIC analysis: 4,101 observations, 271 firms, 82 forecast-origin dates; target
  dates run from September 2018 through February 2026.
- AIC analysis: 4,075 observations and 271 firms.

## Normalized-error regression

| Selection | Coefficient on target-date sigma | Two-way clustered SE | p-value | N |
|---|---:|---:|---:|---:|
| BIC | -33.468 | 7.062 | 0.0000022 | 4,101 |
| AIC | -26.570 | 5.851 | 0.0000058 | 4,075 |

The normalized ratio remains decreasing, but its interpretation changes once
volatility is correctly aligned to the target date. Forecast-error variance no
longer falls within firms; instead, it rises weakly and less than proportionally
to target-date fundamental variance.

The negative ratio coefficient is robust to log volatility, lagged controls,
winsorized forecast errors, sector-by-time effects, and 9- and 12-residual windows.

## Numerator and elasticity diagnostics

| Outcome and regressor | Fixed effects | BIC coefficient | SE | AIC coefficient | SE |
|---|---|---:|---:|---:|---:|
| `FE² ~ target sigma` | none | 0.715 | 0.075 | 0.761 | 0.079 |
| `FE² ~ target sigma` | firm | 0.085 | 0.089 | 0.098 | 0.085 |
| `FE² ~ target sigma` | firm + time | 0.096 | 0.092 | 0.108 | 0.089 |
| `FE² ~ target sigma²` | none | 0.673 | 0.101 | 0.789 | 0.081 |
| `FE² ~ target sigma²` | firm | 0.010 | 0.110 | 0.047 | 0.107 |
| `FE² ~ target sigma²` | firm + time | 0.021 | 0.112 | 0.058 | 0.109 |
| `log(FE²+c) ~ log(target sigma²)` | none | 0.549 | 0.032 | 0.568 | 0.034 |
| `log(FE²+c) ~ log(target sigma²)` | firm | 0.128 | 0.041 | 0.131 | 0.044 |
| `log(FE²+c) ~ log(target sigma²)` | firm + time | 0.113 | 0.042 | 0.111 | 0.044 |
| `FE²/sigma² ~ target sigma` | firm + time | -33.468 | 7.062 | -26.570 | 5.851 |

The numerator now behaves in the direction suggested by the intuition:

- Pooled squared forecast errors increase strongly with target-date volatility.
- Within firms, the point estimates remain positive after adding firm and time
  effects, although the level regressions are not statistically significant.
- The log elasticity is positive and significant, but far below one. For BIC,
  `eta=0.113` with SE `0.042`; for AIC, `eta=0.111` with SE `0.044`.
- The one-sided test of `eta > 1` has p-value effectively one. Thus forecast
  errors increase, but much less than proportionally to target-date variance.

Under the stated mapping, these estimates still do not support A2's required
`eta > 1`. They do, however, remove the earlier and misleading conclusion that
within-firm forecast-error variance itself falls when volatility rises.

## Volatility bins and structural mapping

For increasing BIC target-volatility quintiles, average target volatility is
`0.063, 0.125, 0.192, 0.305, 0.600`. The ratio
`Var(FE|bin)/E[sigma²|bin]` is `7.21, 3.37, 2.63, 1.61, 1.02`.
The corresponding observation-level mean ratios are
`12.79, 3.55, 2.61, 1.73, 1.23`.

All BIC bin ratios are at or above one, so the Gaussian mapping
`tau²=R/(1-R)` is outside its admissible domain and no structural curve is
reported.

## Aggregate and sector states

Leave-one-out state regressors avoid feeding a firm's own volatility mechanically
into its state measure. Under BIC:

- Aggregate normalized-error coefficient with firm effects: -5.38
  (SE 18.93, p=0.776).
- Aggregate log elasticity: 0.155 (SE 0.245), below one.
- Sector normalized-error coefficient with firm and time effects: 13.55
  (SE 13.57, p=0.318).
- Sector log elasticity: -0.078 (SE 0.076), below one.

These state results are imprecise and do not establish an aggregate- or
sector-volatility version of A2.

## Remaining limitations

- Standardized innovations have near-zero means but standard deviations above
  one (BIC 1.77; AIC 1.56), indicating noisy rolling volatility estimates.
- ARMA parameters are estimated using each firm's full usable history; target-date
  volatility uses only residuals dated before the target, but parameter estimation
  itself is not recursive real-time estimation.
- The public file has 1,343 matched price forecast errors but insufficient repeated
  firm price realizations for firm-specific price ARMA estimation.
- Completed estimates restrict `p,q` to 0--2 because firm histories are short and
  effectively bimonthly; the unrestricted 0--4 configuration remains available.

## Output locations

BIC artifacts are in `outputs/short_panel/`; AIC artifacts are in
`outputs/short_panel_aic/`. Each includes the timing-auditable panel, selected
orders, main regressions, decomposition regressions, bins, bootstrap intervals,
state regressions, figures, and diagnostics.
