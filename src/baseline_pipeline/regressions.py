from __future__ import annotations

from pathlib import Path

import pandas as pd


OUTCOMES = ["D_ap_cogs", "D_ar_sales", "D_cash_assets", "sales_growth", "employment_growth"]
CONTROLS = [
    "L1_log_assets",
    "L1_leverage_w",
    "L1_cash_assets_w",
    "L1_ap_cogs_w",
    "L1_ar_sales_w",
    "L1_short_debt_assets_w",
]
MAIN = "FU_x_low_cash_x_centrality"


def run_diagnostic_regressions(panel: pd.DataFrame, output_dir: Path) -> None:
    try:
        import statsmodels.formula.api as smf
    except ImportError as exc:
        raise RuntimeError("Diagnostic regressions require statsmodels.") from exc

    rows = []
    text_blocks = []
    df = panel.loc[panel["baseline_sample"].eq(1)].copy()
    df["sic2_year"] = df["sic2"].astype(str) + "_" + df["fyear"].astype(str)
    regressors = [MAIN, *CONTROLS]

    for outcome in OUTCOMES:
        needed = [outcome, "gvkey", "sic2_year", *regressors]
        reg_df = df.dropna(subset=needed).copy()
        if reg_df.empty:
            rows.append({"outcome": outcome, "status": "no_complete_cases"})
            continue
        formula = f"{outcome} ~ {' + '.join(regressors)} + C(gvkey) + C(sic2_year)"
        result = smf.ols(formula, data=reg_df).fit(
            cov_type="cluster", cov_kwds={"groups": reg_df["gvkey"]}
        )
        coef = result.params.get(MAIN)
        se = result.bse.get(MAIN)
        pval = result.pvalues.get(MAIN)
        rows.append(
            {
                "outcome": outcome,
                "nobs": int(result.nobs),
                "r2": result.rsquared,
                "main_regressor": MAIN,
                "coef": coef,
                "clustered_se": se,
                "p_value": pval,
            }
        )
        text_blocks.append(f"\n\n=== {outcome} ===\n{result.summary().as_text()}")

    pd.DataFrame(rows).to_csv(output_dir / "diagnostic_regressions.csv", index=False)
    (output_dir / "diagnostic_regressions.txt").write_text(
        "Diagnostic regressions with firm fixed effects, SIC2-year fixed effects, "
        "and standard errors clustered by firm."
        + "".join(text_blocks),
        encoding="utf-8",
    )

