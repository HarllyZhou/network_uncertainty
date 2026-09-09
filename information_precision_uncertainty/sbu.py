from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


SBU_URL = (
    "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
    "research/surveys/business-uncertainty/data/SBU_microdata.zip"
)


def dhs_growth(future: pd.Series, current: pd.Series) -> pd.Series:
    """DHS growth, 2*(future-current)/(future+current), with invalid levels excluded."""
    future = pd.to_numeric(future, errors="coerce")
    current = pd.to_numeric(current, errors="coerce")
    denominator = future + current
    result = 2.0 * (future - current) / denominator
    return result.where((future >= 0) & (current >= 0) & (denominator > 0))


def _unique_firm_date(df: pd.DataFrame) -> pd.DataFrame:
    # The public file is normally unique. If not, prefer the last nonmissing response.
    completeness = df.notna().sum(axis=1)
    return (
        df.assign(_completeness=completeness)
        .sort_values(["firm_id", "date", "_completeness"])
        .drop_duplicates(["firm_id", "date"], keep="last")
        .drop(columns="_completeness")
    )


def load_sbu(path: str | Path) -> pd.DataFrame:
    """Build an exact-horizon SBU panel from the official public microdata.

    Forecasts at t are joined only to the same firm's report at t+12 calendar months.
    Sales realizations are reconstructed from levels so forecast and realization use
    the same DHS-growth units. No nearest-date or lead-fill matching is permitted.
    """
    usecols = [
        "date",
        "contactid",
        "sector",
        "sr_current",
        "sr_gr_dhsforecast_nw",
        "price_dhs_nw",
        "price_gr_dhsforecast_nw",
    ]
    raw = pd.read_stata(path, columns=usecols, convert_categoricals=False)
    raw = raw.rename(
        columns={
            "contactid": "firm_id",
            "sr_gr_dhsforecast_nw": "expected_sales_growth",
            "price_dhs_nw": "price_growth",
            "price_gr_dhsforecast_nw": "expected_price_growth",
        }
    )
    raw["date"] = pd.to_datetime(raw["date"]).dt.to_period("M").dt.to_timestamp()
    raw = raw.dropna(subset=["firm_id", "date"])
    raw["firm_id"] = raw["firm_id"].astype("int64").astype(str)
    raw = _unique_firm_date(raw)

    lagged = raw[["firm_id", "date", "sr_current"]].copy()
    lagged["date"] = lagged["date"] + pd.DateOffset(months=12)
    lagged = lagged.rename(columns={"sr_current": "sales_lag12"})
    panel = raw.merge(lagged, on=["firm_id", "date"], how="left", validate="one_to_one")
    panel["realized_sales_growth"] = dhs_growth(panel["sr_current"], panel["sales_lag12"])
    current_log = np.log(panel["sr_current"].where(panel["sr_current"] > 0))
    lagged_log = np.log(panel["sales_lag12"].where(panel["sales_lag12"] > 0))
    panel["output_growth"] = current_log - lagged_log

    future = panel[
        ["firm_id", "date", "realized_sales_growth", "price_growth"]
    ].copy()
    future["date"] = future["date"] - pd.DateOffset(months=12)
    future = future.rename(
        columns={
            "realized_sales_growth": "future_sales_growth",
            "price_growth": "future_price_growth",
        }
    )
    panel = panel.merge(future, on=["firm_id", "date"], how="left", validate="one_to_one")
    panel["sales_fe"] = panel["future_sales_growth"] - panel["expected_sales_growth"]
    panel["price_fe"] = panel["future_price_growth"] - panel["expected_price_growth"]
    panel["target_date"] = panel["date"] + pd.DateOffset(months=12)
    return panel.sort_values(["firm_id", "date"]).reset_index(drop=True)
