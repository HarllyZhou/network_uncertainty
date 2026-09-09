import numpy as np
import pandas as pd

from information_precision_uncertainty.arima import (
    add_backward_volatility,
    add_target_date_volatility,
)
from information_precision_uncertainty.estimation import structural_mapping
from information_precision_uncertainty.decomposition import (
    add_leave_one_out_states,
    prepare_decomposition,
)
from information_precision_uncertainty.sbu import dhs_growth


def test_dhs_growth():
    result = dhs_growth(pd.Series([110.0]), pd.Series([100.0])).iloc[0]
    assert np.isclose(result, 20 / 210)


def test_volatility_is_strictly_backward_looking():
    panel = pd.DataFrame(
        {"firm_id": ["a"] * 5, "date": pd.date_range("2020-01-01", periods=5, freq="MS"),
         "innovation": [1.0, 2.0, 3.0, 100.0, 5.0]}
    )
    out = add_backward_volatility(panel, "innovation", [3])
    assert np.isnan(out.loc[2, "sigma_w3"])
    assert np.isclose(out.loc[3, "sigma_w3"], np.std([1, 2, 3], ddof=1))
    # The current shock of 100 is used only at the following date.
    assert np.isclose(out.loc[4, "sigma_w3"], np.std([2, 3, 100], ddof=1))


def test_volatility_stays_aligned_with_multiple_firms():
    panel = pd.DataFrame(
        {"firm_id": ["a"] * 4 + ["b"] * 4,
         "date": list(pd.date_range("2020-01-01", periods=4, freq="MS")) * 2,
         "innovation": [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]},
        index=[7, 2, 9, 1, 8, 0, 6, 3],
    )
    out = add_backward_volatility(panel, "innovation", [3])
    a_last = out[(out.firm_id == "a") & (out.date == "2020-04-01")].iloc[0]
    b_last = out[(out.firm_id == "b") & (out.date == "2020-04-01")].iloc[0]
    assert np.isclose(a_last.sigma_w3, np.std([1, 2, 3], ddof=1))
    assert np.isclose(b_last.sigma_w3, np.std([10, 20, 30], ddof=1))


def test_volatility_uses_last_observed_residuals_across_survey_gaps():
    panel = pd.DataFrame(
        {"firm_id": ["a"] * 7,
         "date": pd.date_range("2020-01-01", periods=7, freq="MS"),
         "innovation": [1.0, np.nan, 2.0, np.nan, 3.0, np.nan, 4.0]}
    )
    out = add_backward_volatility(panel, "innovation", [3])
    assert np.isclose(out.loc[6, "sigma_w3"], np.std([1, 2, 3], ddof=1))


def test_forecast_row_receives_exact_target_date_volatility():
    panel = pd.DataFrame(
        {"firm_id": ["a", "a", "b"],
         "date": pd.to_datetime(["2022-01-01", "2023-01-01", "2023-01-01"]),
         "target_date": pd.to_datetime(["2023-01-01", "2024-01-01", "2024-01-01"]),
         "sigma_w6": [1.0, 2.0, 9.0]}
    )
    out = add_target_date_volatility(panel, [6])
    assert out.loc[0, "sigma_target_w6"] == 2.0
    assert np.isnan(out.loc[1, "sigma_target_w6"])
    rerun = add_target_date_volatility(out, [6])
    assert rerun.loc[0, "sigma_target_w6"] == 2.0


def test_structural_mapping_respects_domain():
    bins = pd.DataFrame({"ratio_of_moments": [0.2, 0.5, 1.1]})
    result = structural_mapping(bins)
    assert np.allclose(result["tau2_model_implied"].iloc[:2], [0.25, 1.0])
    assert np.isnan(result["tau2_model_implied"].iloc[2])


def test_log_decomposition_uses_scale_aware_positive_offset():
    panel = pd.DataFrame({"sales_fe": [0.0, 1.0, 2.0], "sigma_w6": [1.0, 1.0, 2.0]})
    out, offset = prepare_decomposition(panel, "sigma_w6")
    assert offset > 0
    assert np.isfinite(out["log_fe2_c"]).all()
    assert np.allclose(out["normalized_fe2"], [0.0, 1.0, 1.0])


def test_state_volatility_is_leave_one_out():
    panel = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-01"] * 3), "sector": ["x", "x", "y"],
         "sigma_w6": [1.0, 2.0, 3.0]}
    )
    out = add_leave_one_out_states(panel, "sigma_w6")
    assert np.isclose(out.loc[0, "aggregate_sigma_loo"], np.sqrt((4 + 9) / 2))
    assert np.isclose(out.loc[0, "sector_sigma_loo"], 2.0)
    assert np.isnan(out.loc[2, "sector_sigma_loo"])
