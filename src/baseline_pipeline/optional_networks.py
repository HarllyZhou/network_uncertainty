from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_optional_network_edges(paths: dict[str, Path]) -> pd.DataFrame:
    frames = []
    for source_name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Optional network path does not exist: {path}")
        raw = _read_table(path)
        frame = _normalize_optional_edges(raw, source_name)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _normalize_optional_edges(raw: pd.DataFrame, source_name: str) -> pd.DataFrame:
    columns = {str(col).lower(): col for col in raw.columns}

    supplier_col = _first(columns, ["supplier_gvkey", "gvkey_supplier", "source_gvkey", "gvkey"])
    customer_col = _first(columns, ["customer_gvkey", "gvkey_customer", "target_gvkey", "cgvkey"])
    year_col = _first(columns, ["year", "fyear", "fiscal_year"])
    date_col = _first(columns, ["datadate", "date", "relationship_date", "start_date"])
    weight_col = _first(columns, ["edge_weight", "sales_to_customer", "sales", "revenue", "customer_share"])
    customer_name_col = _first(columns, ["customer_name", "customer_name_original", "target_name", "company_name"])
    quality_col = _first(columns, ["match_quality", "match_quality_if_available", "confidence", "score"])

    if supplier_col is None or customer_col is None:
        raise RuntimeError(
            f"{source_name} needs supplier and customer gvkey columns. "
            f"Available columns: {list(raw.columns)}"
        )

    out = pd.DataFrame(
        {
            "source_dataset": source_name,
            "supplier_gvkey": raw[supplier_col],
            "customer_gvkey": raw[customer_col],
            "customer_name_original": raw[customer_name_col] if customer_name_col else pd.NA,
            "match_quality_if_available": raw[quality_col] if quality_col else pd.NA,
        }
    )
    if year_col:
        out["year"] = pd.to_numeric(raw[year_col], errors="coerce")
    elif date_col:
        out["year"] = pd.to_datetime(raw[date_col], errors="coerce").dt.year
    else:
        out["year"] = pd.NA

    if weight_col:
        out["edge_weight"] = pd.to_numeric(raw[weight_col], errors="coerce")
        out["edge_weight_type"] = weight_col
    else:
        out["edge_weight"] = 1.0
        out["edge_weight_type"] = "equal_weight"
    return out


def _first(columns: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None
