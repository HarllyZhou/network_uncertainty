from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ALIAS_OVERRIDES = {
    "AM TEL AND TEL": "AMERICAN TELEPHONE AND TELEGRAPH",
    "AT AND T": "AMERICAN TELEPHONE AND TELEGRAPH",
    "AT T": "AMERICAN TELEPHONE AND TELEGRAPH",
    "DAIMLERCHRYSLER": "DAIMLER CHRYSLER",
    "GEN ELEC": "GENERAL ELECTRIC",
    "GEN MOTORS": "GENERAL MOTORS",
    "GEN MTR": "GENERAL MOTORS",
    "HEWLETT PCK": "HEWLETT PACKARD",
    "INTL BUS MA": "INTERNATIONAL BUSINESS MACHINES",
    "K MART": "KMART",
    "MCDONNEL DG": "MCDONNELL DOUGLAS",
    "PENNEY JC": "J C PENNEY",
    "SEARS ROEBK": "SEARS ROEBUCK",
    "WAL MART": "WALMART",
}

TOKEN_EXPANSIONS = {
    "AIRL": "AIRLINES",
    "AMER": "AMERICAN",
    "AUTO": "AUTOMOTIVE",
    "BK": "BANK",
    "BUS": "BUSINESS",
    "CHEM": "CHEMICAL",
    "COMM": "COMMUNICATIONS",
    "COMMS": "COMMUNICATIONS",
    "DEPT": "DEPARTMENT",
    "ELEC": "ELECTRIC",
    "EQ": "EQUIPMENT",
    "GEN": "GENERAL",
    "IND": "INDUSTRIES",
    "INDS": "INDUSTRIES",
    "INTL": "INTERNATIONAL",
    "LABS": "LABORATORIES",
    "MFG": "MANUFACTURING",
    "MTR": "MOTOR",
    "MTRS": "MOTORS",
    "NATL": "NATIONAL",
    "PETE": "PETROLEUM",
    "PHARM": "PHARMACEUTICAL",
    "PRODS": "PRODUCTS",
    "SYS": "SYSTEMS",
    "TECH": "TECHNOLOGIES",
    "TEL": "TELEPHONE",
}

GENERIC_CUSTOMER_NAMES = {
    "",
    "ALL OTHER",
    "COMMERCIAL",
    "CUSTOMERS",
    "DOMESTIC",
    "FOREIGN",
    "GOVERNMENT",
    "INTERNATIONAL",
    "NORTH AMERICA",
    "NOT REPORTED",
    "OTHER",
    "REST OF WORLD",
    "UNITED STATES",
    "US GOVERNMENT",
    "U S GOVERNMENT",
}

LEGAL_SUFFIXES = {
    "AG",
    "BV",
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "GROUP",
    "HOLDING",
    "HOLDINGS",
    "INC",
    "INCORPORATED",
    "L L C",
    "LC",
    "LLC",
    "LP",
    "LTD",
    "LIMITED",
    "NV",
    "PLC",
    "SA",
    "S A",
}


def add_simple_customer_name_matches(
    customer_raw: pd.DataFrame,
    financials: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    """Add customer_gvkey from deterministic same-year normalized-name matches.

    This is intentionally conservative. It does not use fuzzy matching and does not
    use an external index. A customer name is matched only when its normalized name
    maps to one unique Compustat gvkey in the same fiscal year.
    """
    customer_name_col = _first_existing(customer_raw, ["customer_name_original", "cnms"])
    year_col = _first_existing(customer_raw, ["year", "fyear", "year_raw"])
    if customer_name_col is None or year_col is None or "conm" not in financials:
        return customer_raw

    out = customer_raw.copy()
    out["_customer_name_key"] = out[customer_name_col].map(normalize_company_name)
    out["_match_year"] = pd.to_numeric(out[year_col], errors="coerce").astype("Int64")

    customer_type = out.get("customer_segment_type", out.get("ctype", pd.Series(pd.NA, index=out.index)))
    is_company = customer_type.astype("string").str.upper().eq("COMPANY")
    is_specific_name = ~out["_customer_name_key"].map(is_generic_customer_key)
    needs_match = out.get("customer_gvkey", pd.Series(pd.NA, index=out.index)).isna()
    matchable = needs_match & is_company & is_specific_name & out["_customer_name_key"].notna()

    lookup = _build_company_name_lookup(financials)
    lookup = lookup.dropna(subset=["gvkey", "fyear", "_customer_name_key"]).copy()
    lookup = lookup.loc[lookup["_customer_name_key"].notna()]
    lookup = lookup.loc[~lookup["_customer_name_key"].map(is_generic_customer_key)]
    lookup["fyear"] = pd.to_numeric(lookup["fyear"], errors="coerce").astype("Int64")
    lookup["gvkey"] = lookup["gvkey"].astype("string").str.extract(r"(\d+)")[0].str.zfill(6)

    if "customer_gvkey" not in out:
        out["customer_gvkey"] = pd.NA
    if "match_quality_if_available" not in out:
        out["match_quality_if_available"] = pd.NA

    matched_frames = []
    ambiguous_frames = []
    for tier_name, tier_matches, tier_ambiguous in _run_match_tiers(out, matchable, lookup):
        if tier_matches.empty:
            continue
        unmatched_now = out.loc[tier_matches["index"], "customer_gvkey"].isna().to_numpy()
        tier_matches = tier_matches.loc[unmatched_now].copy()
        if tier_matches.empty:
            continue
        out.loc[tier_matches["index"], "customer_gvkey"] = tier_matches["customer_gvkey"].to_numpy()
        out.loc[tier_matches["index"], "match_quality_if_available"] = tier_name
        tier_rows = out.loc[tier_matches["index"]].copy()
        tier_rows["matched_customer_name"] = tier_matches["matched_customer_name"].to_numpy()
        tier_rows["matched_alias_source"] = tier_matches["matched_alias_source"].to_numpy()
        matched_frames.append(tier_rows)
        if not tier_ambiguous.empty:
            tier_ambiguous = tier_ambiguous.copy()
            tier_ambiguous["match_tier"] = tier_name
            ambiguous_frames.append(tier_ambiguous)

    matched_rows = pd.concat(matched_frames, ignore_index=True, sort=False) if matched_frames else out.iloc[0:0]
    ambiguous = (
        pd.concat(ambiguous_frames, ignore_index=True, sort=False)
        if ambiguous_frames
        else pd.DataFrame()
    )
    matched_rows.to_csv(output_dir / "customer_name_matches_exact.csv", index=False)
    ambiguous.to_csv(output_dir / "customer_name_matches_ambiguous.csv", index=False)

    summary = pd.DataFrame(
        [
            {"metric": "raw_customer_rows", "value": len(out)},
            {"metric": "matchable_company_name_rows", "value": int(matchable.sum())},
            {"metric": "deterministic_matched_rows", "value": int(out["customer_gvkey"].notna().sum())},
            {"metric": "ambiguous_same_year_rows", "value": len(ambiguous)},
            {
                "metric": "unique_supplier_customer_year_edges_after_matching",
                "value": int(
                    out.loc[out["customer_gvkey"].notna(), ["supplier_gvkey", "customer_gvkey", year_col]]
                    .drop_duplicates()
                    .shape[0]
                )
                if "supplier_gvkey" in out
                else 0,
            },
        ]
    )
    summary.to_csv(output_dir / "customer_name_match_summary.csv", index=False)

    return out.drop(columns=["_customer_name_key", "_match_year"])


def normalize_company_name(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\bTHE\b", " ", text)
    tokens = [token for token in text.split() if token]
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = ALIAS_OVERRIDES.get(normalized, normalized)
    if re.fullmatch(r"\d+\s+CUSTOMERS?", normalized):
        return normalized
    tokens = [TOKEN_EXPANSIONS.get(token, token) for token in normalized.split()]
    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = ALIAS_OVERRIDES.get(normalized, normalized)
    return normalized or None


def is_generic_customer_key(value: object) -> bool:
    if pd.isna(value):
        return True
    text = str(value)
    return text in GENERIC_CUSTOMER_NAMES or bool(re.fullmatch(r"\d+\s+CUSTOMERS?", text))


def _first_existing(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in frame:
            return candidate
    return None


def _build_company_name_lookup(financials: pd.DataFrame) -> pd.DataFrame:
    alias_cols = [col for col in ["conm", "conml"] if col in financials]
    frames = []
    for col in alias_cols:
        frame = financials[["gvkey", "fyear", col]].rename(columns={col: "matched_customer_name"}).copy()
        frame["matched_alias_source"] = col
        frame["_customer_name_key"] = frame["matched_customer_name"].map(normalize_company_name)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["gvkey", "fyear", "matched_customer_name", "matched_alias_source", "_customer_name_key"])
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates()


def _run_match_tiers(
    customer_rows: pd.DataFrame,
    matchable: pd.Series,
    lookup: pd.DataFrame,
) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    merge_input = customer_rows.loc[matchable, ["_customer_name_key", "_match_year"]].reset_index()
    tiers = []

    same_year = _unique_lookup(lookup, ["_customer_name_key", "fyear"])
    matched = merge_input.merge(
        same_year,
        left_on=["_customer_name_key", "_match_year"],
        right_on=["_customer_name_key", "fyear"],
        how="left",
    )
    tiers.append(_split_matches("exact_normalized_name_same_year", matched))

    adjacent_lookup = []
    for offset in (-1, 1):
        shifted = lookup.copy()
        shifted["match_year"] = shifted["fyear"] + offset
        adjacent_lookup.append(shifted)
    adjacent = _unique_lookup(pd.concat(adjacent_lookup, ignore_index=True), ["_customer_name_key", "match_year"])
    still_unmatched = _remaining_indices(customer_rows, matchable, tiers)
    matched = merge_input.loc[merge_input["index"].isin(still_unmatched)].merge(
        adjacent,
        left_on=["_customer_name_key", "_match_year"],
        right_on=["_customer_name_key", "match_year"],
        how="left",
    )
    tiers.append(_split_matches("exact_normalized_name_adjacent_year", matched))

    all_year = _unique_lookup(lookup, ["_customer_name_key"])
    still_unmatched = _remaining_indices(customer_rows, matchable, tiers)
    matched = merge_input.loc[merge_input["index"].isin(still_unmatched)].merge(
        all_year,
        on="_customer_name_key",
        how="left",
    )
    tiers.append(_split_matches("exact_normalized_name_all_year_unique", matched))
    return tiers


def _unique_lookup(lookup: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    counts = lookup.groupby(keys)["gvkey"].nunique().rename("candidate_gvkey_count").reset_index()
    names = (
        lookup.groupby(keys, as_index=False)
        .agg(
            customer_gvkey=("gvkey", "first"),
            matched_customer_name=("matched_customer_name", "first"),
            matched_alias_source=("matched_alias_source", "first"),
        )
        .merge(counts, on=keys, how="left")
    )
    return names


def _split_matches(tier_name: str, matched: pd.DataFrame) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    unique_matches = matched.loc[matched["candidate_gvkey_count"].eq(1)].copy()
    ambiguous = matched.loc[matched["candidate_gvkey_count"].gt(1)].copy()
    return tier_name, unique_matches, ambiguous


def _remaining_indices(
    customer_rows: pd.DataFrame,
    matchable: pd.Series,
    tiers: list[tuple[str, pd.DataFrame, pd.DataFrame]],
) -> set[int]:
    already = set()
    for _tier_name, matches, _ambiguous in tiers:
        already.update(matches["index"].dropna().astype(int).tolist())
    all_matchable = set(customer_rows.loc[matchable].index.astype(int).tolist())
    return all_matchable - already
