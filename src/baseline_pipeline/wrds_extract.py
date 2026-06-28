from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .variables import FUNDAMENTALS_REQUIRED_FILTERS, FUNDAMENTALS_VARIABLES


@dataclass(frozen=True)
class WrdsTable:
    library: str
    table: str
    columns: list[str]

    @property
    def label(self) -> str:
        return f"{self.library}.{self.table}"


def connect_wrds():
    try:
        import wrds
    except ImportError as exc:
        raise RuntimeError("The wrds package is required for WRDS extraction.") from exc
    return wrds.Connection()


def inspect_libraries(conn, output_dir: Path) -> list[str]:
    libraries = sorted(conn.list_libraries())
    pd.Series(libraries, name="library").to_csv(output_dir / "wrds_libraries.csv", index=False)
    return libraries


def find_first_table(conn, library_candidates: list[str], table_candidates: list[str]) -> WrdsTable:
    libraries = set(conn.list_libraries())
    for library in library_candidates:
        if library not in libraries:
            continue
        tables = set(conn.list_tables(library=library))
        for table in table_candidates:
            if table in tables:
                columns = list(conn.describe_table(library=library, table=table).index)
                return WrdsTable(library, table, columns)
    raise RuntimeError(
        "Could not find a Fundamentals Annual table among "
        f"libraries={library_candidates}, tables={table_candidates}."
    )


def discover_customer_segment_tables(
    conn,
    library_candidates: list[str],
    keywords: list[str],
    output_dir: Path,
) -> list[WrdsTable]:
    libraries = set(conn.list_libraries())
    matches: list[WrdsTable] = []
    keyword_tuple = tuple(k.lower() for k in keywords)
    for library in library_candidates:
        if library not in libraries:
            continue
        for table in conn.list_tables(library=library):
            haystack = table.lower()
            if any(keyword in haystack for keyword in keyword_tuple):
                columns = list(conn.describe_table(library=library, table=table).index)
                matches.append(WrdsTable(library, table, columns))

    rows = [
        {"library": item.library, "table": item.table, "columns": "|".join(item.columns)}
        for item in matches
    ]
    pd.DataFrame(rows).to_csv(output_dir / "wrds_customer_segment_table_candidates.csv", index=False)
    return matches


def extract_fundamentals(conn, table: WrdsTable, start_year: int | None, end_year: int | None) -> pd.DataFrame:
    available = [col for col in FUNDAMENTALS_VARIABLES if col in table.columns]
    missing_filters = [col for col in FUNDAMENTALS_REQUIRED_FILTERS if col not in table.columns]
    if missing_filters:
        raise RuntimeError(f"{table.label} is missing expected filter columns: {missing_filters}")

    where = ["indfmt = 'INDL'", "datafmt = 'STD'", "popsrc = 'D'", "consol = 'C'"]
    if start_year is not None:
        where.append(f"fyear >= {int(start_year)}")
    if end_year is not None:
        where.append(f"fyear <= {int(end_year)}")

    sql = f"""
        select {", ".join(available)}
        from {table.library}.{table.table}
        where {" and ".join(where)}
    """
    return conn.raw_sql(sql, date_cols=["datadate"])


def _choose_first(columns: list[str], candidates: list[str]) -> str | None:
    lower_map = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def extract_customer_segments(
    conn,
    discovered_tables: list[WrdsTable],
    start_year: int | None,
    end_year: int | None,
) -> pd.DataFrame:
    if not discovered_tables:
        raise RuntimeError("No candidate customer-segment tables were discovered in WRDS metadata.")

    frames: list[pd.DataFrame] = []
    for table in discovered_tables:
        supplier_col = _choose_first(table.columns, ["gvkey", "gvkey_supp", "supplier_gvkey"])
        customer_col = _choose_first(
            table.columns,
            ["cgvkey", "gvkey_cust", "customer_gvkey", "custgvkey", "gvkey_customer"],
        )
        customer_name_col = _choose_first(
            table.columns,
            ["cnms", "conm_customer", "customer_name", "custname", "customer"],
        )
        year_col = _choose_first(table.columns, ["fyear", "srcdate", "year"])
        datadate_col = _choose_first(table.columns, ["datadate", "srcdate"])
        sales_col = _choose_first(table.columns, ["sales", "sale", "salecs", "amount", "cust_sales"])
        share_col = _choose_first(table.columns, ["pct", "percent", "customer_share", "sales_pct"])

        if supplier_col is None or (customer_col is None and customer_name_col is None):
            continue

        selected = {
            supplier_col,
            *(col for col in [customer_col, customer_name_col, year_col, datadate_col, sales_col, share_col] if col),
        }
        sql = f"select {', '.join(sorted(selected))} from {table.library}.{table.table}"
        frame = conn.raw_sql(sql, date_cols=[datadate_col] if datadate_col else None)
        rename = {
            supplier_col: "supplier_gvkey",
            customer_col: "customer_gvkey" if customer_col else customer_col,
            customer_name_col: "customer_name_original" if customer_name_col else customer_name_col,
            year_col: "year_raw" if year_col else year_col,
            datadate_col: "datadate" if datadate_col else datadate_col,
            sales_col: "sales_to_customer" if sales_col else sales_col,
            share_col: "customer_share" if share_col else share_col,
        }
        frame = frame.rename(columns={k: v for k, v in rename.items() if k and v})
        frame["source_dataset"] = table.label
        frames.append(frame)

    if not frames:
        raise RuntimeError("Candidate tables were found, but none exposed usable supplier/customer columns.")

    edges = pd.concat(frames, ignore_index=True, sort=False)
    if "year_raw" in edges:
        if pd.api.types.is_datetime64_any_dtype(edges["year_raw"]):
            edges["year"] = edges["year_raw"].dt.year
        else:
            edges["year"] = pd.to_numeric(edges["year_raw"], errors="coerce")
    elif "datadate" in edges:
        edges["year"] = pd.to_datetime(edges["datadate"], errors="coerce").dt.year
    else:
        edges["year"] = pd.NA

    if start_year is not None:
        edges = edges.loc[edges["year"].ge(start_year) | edges["year"].isna()]
    if end_year is not None:
        edges = edges.loc[edges["year"].le(end_year) | edges["year"].isna()]
    return edges

