from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .variables import PANEL_LAGS, RATIO_VARIABLES, WINSORIZE_BY_YEAR


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.where(denominator != 0)
    return numerator / denominator


def _safe_log(series: pd.Series) -> pd.Series:
    return np.log(series.where(series > 0))


def prepare_financials(raw: pd.DataFrame, interim_dir: Path) -> pd.DataFrame:
    df = raw.copy()
    filter_values = {
        "indfmt": "INDL",
        "datafmt": "STD",
        "consol": "C",
        "popsrc": "D",
    }
    filter_rows = []
    for col, expected in filter_values.items():
        if col in df:
            before = len(df)
            df = df.loc[df[col].astype("string").eq(expected)].copy()
            filter_rows.append({"filter": f"{col} == {expected}", "rows_before": before, "rows_after": len(df)})
    if "fic" in df:
        before = len(df)
        df = df.loc[df["fic"].astype("string").eq("USA")].copy()
        filter_rows.append({"filter": "fic == USA", "rows_before": before, "rows_after": len(df)})
    if filter_rows:
        pd.DataFrame(filter_rows).to_csv(interim_dir / "fundamentals_filter_audit.csv", index=False)

    required_identifiers = {"gvkey", "fyear"}
    missing_identifiers = required_identifiers - set(df.columns)
    if missing_identifiers:
        raise RuntimeError(f"Fundamentals extract is missing required identifiers: {missing_identifiers}")
    if "datadate" not in df:
        df["datadate"] = pd.NaT
    df["gvkey"] = df["gvkey"].astype(str).str.zfill(6)
    df["fyear"] = pd.to_numeric(df["fyear"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["gvkey", "fyear"])

    duplicate_mask = df.duplicated(["gvkey", "fyear"], keep=False)
    duplicates = df.loc[duplicate_mask].sort_values(["gvkey", "fyear", "datadate"])
    duplicates.to_csv(interim_dir / "fundamentals_duplicate_gvkey_fyear.csv", index=False)

    numeric_cols = [
        "at",
        "act",
        "lct",
        "che",
        "rect",
        "ap",
        "invt",
        "dlc",
        "dltt",
        "lt",
        "sale",
        "cogs",
        "xint",
        "capx",
        "emp",
    ]
    for col in numeric_cols:
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["_accounting_completeness"] = df[numeric_cols].notna().sum(axis=1)
    df = (
        df.sort_values(["gvkey", "fyear", "_accounting_completeness", "datadate"])
        .drop_duplicates(["gvkey", "fyear"], keep="last")
        .drop(columns=["_accounting_completeness"])
    )

    df["unrestricted_sample"] = 1
    df["positive_assets_for_ratios"] = df["at"].gt(0)
    df = df.loc[df["positive_assets_for_ratios"]].copy()

    df["cash_assets"] = _safe_divide(df["che"], df["at"])
    df["current_ratio"] = _safe_divide(df["act"], df["lct"])
    df["total_debt"] = df["dlc"].fillna(0) + df["dltt"].fillna(0)
    df["leverage"] = _safe_divide(df["total_debt"], df["at"])
    df["short_debt_assets"] = _safe_divide(df["dlc"], df["at"])
    df["long_debt_assets"] = _safe_divide(df["dltt"], df["at"])
    df["interest_burden_sales"] = _safe_divide(df["xint"], df["sale"])
    df["interest_burden_debt"] = _safe_divide(df["xint"], df["total_debt"])
    df["ap_cogs"] = _safe_divide(df["ap"], df["cogs"])
    df["ar_sales"] = _safe_divide(df["rect"], df["sale"])
    df["net_trade_credit_assets"] = _safe_divide(df["rect"] - df["ap"], df["at"])
    df["ap_assets"] = _safe_divide(df["ap"], df["at"])
    df["ar_assets"] = _safe_divide(df["rect"], df["at"])
    df["inventory_assets"] = _safe_divide(df["invt"], df["at"])
    df["cogs_sales"] = _safe_divide(df["cogs"], df["sale"])
    df["capx_assets"] = _safe_divide(df["capx"], df["at"])
    df["log_assets"] = _safe_log(df["at"])
    df["log_sales"] = _safe_log(df["sale"])
    df["log_cogs"] = _safe_log(df["cogs"])
    df["log_emp"] = _safe_log(df["emp"])

    if "sic" not in df:
        df["sic"] = pd.NA
    sic_num = pd.to_numeric(df["sic"], errors="coerce")
    df["sic2"] = (sic_num // 100).astype("Int64")
    df["baseline_sample"] = (~sic_num.between(6000, 6999) & ~sic_num.between(4900, 4999)).astype(int)

    for col in WINSORIZE_BY_YEAR:
        df[f"{col}_w"] = df.groupby("fyear", dropna=False)[col].transform(_winsorize_1_99)

    _add_low_cash_indicators(df)
    return df


def _winsorize_1_99(series: pd.Series) -> pd.Series:
    if series.notna().sum() < 5:
        return series
    low = series.quantile(0.01)
    high = series.quantile(0.99)
    return series.clip(lower=low, upper=high)


def prepare_edges(raw_edges: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    edges = raw_edges.copy()
    if "supplier_gvkey" not in edges:
        raise RuntimeError("Customer-segment extract is missing supplier_gvkey.")
    edges["supplier_gvkey"] = _clean_gvkey(edges["supplier_gvkey"])
    if "customer_gvkey" in edges:
        edges["customer_gvkey"] = _clean_gvkey(edges["customer_gvkey"])
    else:
        edges["customer_gvkey"] = pd.NA
    if "year" not in edges:
        edges["year"] = pd.NA
    edges["year"] = pd.to_numeric(edges["year"], errors="coerce").astype("Int64")

    sales = _numeric_or_missing(edges, "sales_to_customer")
    share = _numeric_or_missing(edges, "customer_share")
    edges["edge_weight"] = sales.where(sales.notna(), share)
    edges["edge_weight_type"] = np.select(
        [sales.notna(), share.notna()],
        ["sales_to_customer", "customer_share"],
        default="equal_weight",
    )
    edges["edge_weight"] = edges["edge_weight"].fillna(1.0)
    edges["match_quality_if_available"] = edges.get("match_quality_if_available", pd.NA)

    keep_cols = [
        "source_dataset",
        "year",
        "supplier_gvkey",
        "customer_gvkey",
        "edge_weight",
        "edge_weight_type",
        "customer_name_original",
        "match_quality_if_available",
    ]
    for col in keep_cols:
        if col not in edges:
            edges[col] = pd.NA

    unmatched = edges.loc[edges["customer_gvkey"].isna(), keep_cols].copy()
    clean = edges.loc[
        edges["supplier_gvkey"].notna() & edges["customer_gvkey"].notna() & edges["year"].notna(),
        keep_cols,
    ].copy()
    clean = clean.drop_duplicates()
    clean.to_csv(output_dir / "clean_compustat_customer_edges.csv", index=False)
    unmatched.to_csv(output_dir / "unmatched_customer_name_observations.csv", index=False)
    return clean, unmatched


def _clean_gvkey(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.extract(r"(\d+)")[0]
    return cleaned.str.zfill(6)


def _numeric_or_missing(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def build_network_measures(
    edges: pd.DataFrame,
    financials: pd.DataFrame,
    compute_expensive_metrics: bool = True,
) -> pd.DataFrame:
    network_columns = [
        "gvkey",
        "fyear",
        "out_degree",
        "in_degree",
        "weighted_out_degree",
        "weighted_in_degree",
        "pagerank",
        "betweenness",
        "eigenvector_centrality",
        "customer_hhi",
        "supplier_hhi",
        "supplier_low_liquidity_exposure",
        "customer_low_liquidity_exposure",
        "supplier_high_ap_exposure",
        "customer_high_ap_exposure",
        "supplier_high_ar_exposure",
        "customer_high_ar_exposure",
        "supplier_short_debt_exposure",
        "customer_short_debt_exposure",
    ]
    if edges.empty:
        return pd.DataFrame(columns=network_columns)

    try:
        import networkx as nx
    except ImportError:
        nx = None

    lag_fin = financials.sort_values(["gvkey", "fyear"]).copy()
    exposure_vars = {
        "low_liquidity": "low_cash_indyr_p25",
        "high_ap": "ap_cogs_w",
        "high_ar": "ar_sales_w",
        "short_debt": "short_debt_assets_w",
    }
    for source in exposure_vars.values():
        lag_fin[f"L1_{source}"] = lag_fin.groupby("gvkey")[source].shift(1)
    lag_fin = lag_fin[["gvkey", "fyear", *(f"L1_{v}" for v in exposure_vars.values())]]

    rows: list[dict[str, float | int | str]] = []
    for year, year_edges in edges.groupby("year"):
        grouped = (
            year_edges.groupby(["supplier_gvkey", "customer_gvkey"], as_index=False)["edge_weight"].sum()
        )
        if nx is None:
            rows.extend(_basic_network_rows(grouped, lag_fin, int(year), exposure_vars))
            continue

        graph = nx.DiGraph()
        for row in grouped.itertuples(index=False):
            graph.add_edge(row.supplier_gvkey, row.customer_gvkey, weight=float(row.edge_weight))

        pagerank = nx.pagerank(graph, weight="weight") if graph.number_of_nodes() else {}
        if compute_expensive_metrics:
            betweenness = (
                nx.betweenness_centrality(graph, weight="weight", normalized=True)
                if graph.number_of_nodes() <= 5000
                else {}
            )
            try:
                eigenvector = nx.eigenvector_centrality_numpy(graph, weight="weight")
            except Exception:
                eigenvector = {}
        else:
            betweenness = {}
            eigenvector = {}

        out_weights = dict(graph.out_degree(weight="weight"))
        in_weights = dict(graph.in_degree(weight="weight"))
        out_degree = dict(graph.out_degree())
        in_degree = dict(graph.in_degree())
        customer_hhi = _counterparty_hhi(grouped, "supplier_gvkey", "customer_gvkey")
        supplier_hhi = _counterparty_hhi(grouped, "customer_gvkey", "supplier_gvkey")

        exposure = _counterparty_exposures(grouped, lag_fin, int(year), exposure_vars)
        for node in graph.nodes:
            row = {
                "gvkey": node,
                "fyear": int(year),
                "out_degree": out_degree.get(node, 0),
                "in_degree": in_degree.get(node, 0),
                "weighted_out_degree": out_weights.get(node, 0.0),
                "weighted_in_degree": in_weights.get(node, 0.0),
                "pagerank": pagerank.get(node, 0.0),
                "betweenness": betweenness.get(node, math.nan),
                "eigenvector_centrality": eigenvector.get(node, math.nan),
                "customer_hhi": customer_hhi.get(node, math.nan),
                "supplier_hhi": supplier_hhi.get(node, math.nan),
            }
            row.update(exposure.get(node, {}))
            rows.append(row)
    return pd.DataFrame(rows).reindex(columns=network_columns)


def _basic_network_rows(
    grouped: pd.DataFrame,
    lag_fin: pd.DataFrame,
    year: int,
    exposure_vars: dict[str, str],
) -> list[dict[str, float | int | str]]:
    nodes = sorted(set(grouped["supplier_gvkey"]).union(grouped["customer_gvkey"]))
    out_degree = grouped.groupby("supplier_gvkey")["customer_gvkey"].nunique().to_dict()
    in_degree = grouped.groupby("customer_gvkey")["supplier_gvkey"].nunique().to_dict()
    weighted_out = grouped.groupby("supplier_gvkey")["edge_weight"].sum().to_dict()
    weighted_in = grouped.groupby("customer_gvkey")["edge_weight"].sum().to_dict()
    pagerank = _weighted_pagerank(grouped, nodes)
    customer_hhi = _counterparty_hhi(grouped, "supplier_gvkey", "customer_gvkey")
    supplier_hhi = _counterparty_hhi(grouped, "customer_gvkey", "supplier_gvkey")
    exposure = _counterparty_exposures(grouped, lag_fin, year, exposure_vars)

    rows = []
    for node in nodes:
        row = {
            "gvkey": node,
            "fyear": year,
            "out_degree": int(out_degree.get(node, 0)),
            "in_degree": int(in_degree.get(node, 0)),
            "weighted_out_degree": float(weighted_out.get(node, 0.0)),
            "weighted_in_degree": float(weighted_in.get(node, 0.0)),
            "pagerank": float(pagerank.get(node, 0.0)),
            "betweenness": math.nan,
            "eigenvector_centrality": math.nan,
            "customer_hhi": customer_hhi.get(node, math.nan),
            "supplier_hhi": supplier_hhi.get(node, math.nan),
        }
        row.update(exposure.get(node, {}))
        rows.append(row)
    return rows


def _weighted_pagerank(
    edges: pd.DataFrame,
    nodes: list[str],
    damping: float = 0.85,
    max_iter: int = 100,
    tol: float = 1.0e-10,
) -> dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    rank = pd.Series(1.0 / n, index=nodes, dtype="float64")
    out_weight = edges.groupby("supplier_gvkey")["edge_weight"].sum()
    adjacency = edges.copy()
    adjacency["transition"] = adjacency["edge_weight"] / adjacency["supplier_gvkey"].map(out_weight)

    for _ in range(max_iter):
        new_rank = pd.Series((1.0 - damping) / n, index=nodes, dtype="float64")
        dangling = rank.loc[~rank.index.isin(out_weight.index)].sum()
        if dangling:
            new_rank += damping * dangling / n
        for row in adjacency.itertuples(index=False):
            new_rank.loc[row.customer_gvkey] += damping * rank.loc[row.supplier_gvkey] * row.transition
        if (new_rank - rank).abs().sum() < tol:
            rank = new_rank
            break
        rank = new_rank
    return rank.to_dict()


def _counterparty_hhi(edges: pd.DataFrame, focal_col: str, counterparty_col: str) -> dict[str, float]:
    out = {}
    for focal, group in edges.groupby(focal_col):
        weights = group.groupby(counterparty_col)["edge_weight"].sum()
        total = weights.sum()
        out[focal] = float(((weights / total) ** 2).sum()) if total > 0 else math.nan
    return out


def _counterparty_exposures(
    edges: pd.DataFrame,
    lag_fin: pd.DataFrame,
    year: int,
    exposure_vars: dict[str, str],
) -> dict[str, dict[str, float]]:
    fin = lag_fin.loc[lag_fin["fyear"].eq(year)].set_index("gvkey")
    out: dict[str, dict[str, float]] = {}

    def weighted_mean(group: pd.DataFrame, counterparty_col: str, column: str) -> float:
        values = fin.reindex(group[counterparty_col])[column].to_numpy(dtype=float)
        weights = group["edge_weight"].to_numpy(dtype=float)
        valid = ~np.isnan(values)
        if not valid.any():
            return math.nan
        weights = weights[valid]
        values = values[valid]
        return float(np.average(values, weights=weights if weights.sum() > 0 else None))

    for supplier, group in edges.groupby("supplier_gvkey"):
        out.setdefault(supplier, {})
        for label, source in exposure_vars.items():
            out[supplier][f"customer_{label}_exposure"] = weighted_mean(
                group, "customer_gvkey", f"L1_{source}"
            )
    for customer, group in edges.groupby("customer_gvkey"):
        out.setdefault(customer, {})
        for label, source in exposure_vars.items():
            out[customer][f"supplier_{label}_exposure"] = weighted_mean(
                group, "supplier_gvkey", f"L1_{source}"
            )
    return out


def read_financial_uncertainty(path: Path, value_column: str | None = None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path)
    else:
        raw = pd.read_csv(path)
    raw.columns = [str(col).strip() for col in raw.columns]

    date_col = _find_col(raw, ["date", "month", "yyyymm", "time"])
    value_col = value_column if value_column in raw.columns else None
    if value_column and value_col is None:
        raise RuntimeError(
            f"Configured financial uncertainty column {value_column!r} was not found. "
            f"Available columns: {list(raw.columns)}"
        )
    value_col = value_col or _find_col(
        raw, ["financial_uncertainty", "fu", "jln", "uncertainty", "value", "h=12", "h=1", "h=3"]
    )
    if value_col is None:
        numeric = raw.select_dtypes(include="number").columns.tolist()
        value_col = numeric[-1] if numeric else None
    if date_col is None or value_col is None:
        raise RuntimeError("Could not infer date and uncertainty columns from the FU file.")

    dates = _parse_dates(raw[date_col])
    fu = pd.DataFrame({"date": dates, "FU": pd.to_numeric(raw[value_col], errors="coerce")}).dropna()
    fu["year"] = fu["date"].dt.year
    fu["month"] = fu["date"].dt.month

    annual = fu.groupby("year")["FU"].agg(FU_mean_year="mean", FU_max_year="max").reset_index()
    q4 = fu.loc[fu["month"].isin([10, 11, 12])].groupby("year")["FU"].mean().rename("FU_q4_year")
    dec = fu.loc[fu["month"].eq(12)].groupby("year")["FU"].mean().rename("FU_dec_year")
    annual = annual.merge(q4, on="year", how="left").merge(dec, on="year", how="left")
    annual["FU_lag1"] = annual["FU_mean_year"].shift(1)
    annual["FU_lag2"] = annual["FU_mean_year"].shift(2)
    return annual.rename(columns={"year": "fyear"})


def _find_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {col.lower(): col for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def _parse_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        text = series.astype("Int64").astype(str)
        return pd.to_datetime(text, format="%Y%m", errors="coerce").fillna(
            pd.to_datetime(text, format="%Y", errors="coerce")
        )
    return pd.to_datetime(series, errors="coerce")


def finalize_panel(financials: pd.DataFrame, network: pd.DataFrame, fu: pd.DataFrame | None) -> pd.DataFrame:
    panel = financials.merge(network, on=["gvkey", "fyear"], how="left", indicator="network_merge")
    if fu is not None:
        panel = panel.merge(fu, on="fyear", how="left", indicator="fu_merge")
    else:
        panel["FU_mean_year"] = np.nan
        panel["FU_max_year"] = np.nan
        panel["FU_q4_year"] = np.nan
        panel["FU_dec_year"] = np.nan
        panel["FU_lag1"] = np.nan
        panel["FU_lag2"] = np.nan
        panel["fu_merge"] = "not_provided"

    panel = panel.sort_values(["gvkey", "fyear"])
    _add_low_cash_indicators(panel)
    for col in PANEL_LAGS:
        if col in panel:
            panel[f"L1_{col}"] = panel.groupby("gvkey")[col].shift(1)

    panel["D_ap_cogs"] = panel["ap_cogs_w"] - panel["L1_ap_cogs_w"]
    panel["D_ar_sales"] = panel["ar_sales_w"] - panel["L1_ar_sales_w"]
    panel["D_cash_assets"] = panel["cash_assets_w"] - panel["L1_cash_assets_w"]
    panel["D_short_debt_assets"] = panel["short_debt_assets_w"] - panel["L1_short_debt_assets_w"]
    panel["sales_growth"] = panel["log_sales"] - panel["L1_log_sales"]
    panel["cogs_growth"] = panel["log_cogs"] - panel["L1_log_cogs"]
    panel["asset_growth"] = panel["log_assets"] - panel["L1_log_assets"]
    panel["employment_growth"] = panel["log_emp"] - panel["L1_log_emp"]

    panel["FU_x_liquidity"] = panel["FU_mean_year"] * panel["L1_cash_assets_w"]
    panel["FU_x_centrality"] = panel["FU_mean_year"] * panel["L1_pagerank"]
    panel["FU_x_liquidity_x_centrality"] = (
        panel["FU_mean_year"] * panel["L1_cash_assets_w"] * panel["L1_pagerank"]
    )
    panel["FU_x_low_cash"] = panel["FU_mean_year"] * panel["L1_low_cash_indyr_p25"]
    panel["FU_x_low_cash_x_centrality"] = (
        panel["FU_mean_year"] * panel["L1_low_cash_indyr_p25"] * panel["L1_pagerank"]
    )
    panel["FU_x_centrality_x_ap"] = panel["FU_mean_year"] * panel["L1_pagerank"] * panel["L1_ap_cogs_w"]
    panel["FU_x_centrality_x_ar"] = panel["FU_mean_year"] * panel["L1_pagerank"] * panel["L1_ar_sales_w"]
    panel["FU_x_supplier_fragility"] = (
        panel["FU_mean_year"] * panel["L1_supplier_low_liquidity_exposure"]
    )
    panel["FU_x_customer_fragility"] = (
        panel["FU_mean_year"] * panel["L1_customer_low_liquidity_exposure"]
    )
    return panel


def _add_low_cash_indicators(frame: pd.DataFrame) -> None:
    med = frame.groupby(["sic2", "fyear"])["cash_assets_w"].transform("median")
    p25 = frame.groupby(["sic2", "fyear"])["cash_assets_w"].transform(lambda s: s.quantile(0.25))
    frame["low_cash_indyr_median"] = frame["cash_assets_w"].lt(med).astype("Int64")
    frame["low_cash_indyr_p25"] = frame["cash_assets_w"].lt(p25).astype("Int64")


def write_summary_tables(panel: pd.DataFrame, edges: pd.DataFrame, output_dir: Path) -> None:
    coverage = panel.groupby("fyear").agg(
        observations=("gvkey", "size"),
        firms=("gvkey", "nunique"),
        baseline_sample=("baseline_sample", "sum"),
        network_matched=("network_merge", lambda s: (s == "both").sum()),
    )
    coverage.to_csv(output_dir / "sample_coverage_by_year.csv")

    summary_cols = [col for col in [*RATIO_VARIABLES, *(f"{c}_w" for c in WINSORIZE_BY_YEAR)] if col in panel]
    panel[summary_cols].describe(percentiles=[0.01, 0.25, 0.5, 0.75, 0.99]).T.to_csv(
        output_dir / "summary_statistics.csv"
    )
    corr_cols = [
        col
        for col in [
            "cash_assets_w",
            "ap_cogs_w",
            "ar_sales_w",
            "short_debt_assets_w",
            "leverage_w",
            "pagerank",
            "out_degree",
            "in_degree",
            "FU_mean_year",
        ]
        if col in panel
    ]
    panel[corr_cols].corr().to_csv(output_dir / "correlation_matrix.csv")

    if edges.empty:
        network_coverage = pd.DataFrame(
            columns=["edges", "suppliers", "customers", "weighted_edges"]
        )
    else:
        network_coverage = edges.groupby("year").agg(
            edges=("supplier_gvkey", "size"),
            suppliers=("supplier_gvkey", "nunique"),
            customers=("customer_gvkey", "nunique"),
            weighted_edges=("edge_weight", lambda s: s.notna().sum()),
        )
    network_coverage.to_csv(output_dir / "network_coverage.csv")

    merge_rates = pd.DataFrame(
        {
            "merge": ["network", "financial_uncertainty"],
            "matched_observations": [
                int((panel["network_merge"] == "both").sum()),
                int((panel["fu_merge"] == "both").sum()) if "fu_merge" in panel else 0,
            ],
            "total_observations": [len(panel), len(panel)],
        }
    )
    merge_rates["match_rate"] = merge_rates["matched_observations"] / merge_rates["total_observations"]
    merge_rates.to_csv(output_dir / "merge_rates.csv", index=False)
