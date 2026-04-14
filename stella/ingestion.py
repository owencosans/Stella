"""
ingestion.py — File upload, schema validation, promo period detection, brand detection.
"""

import pandas as pd
import numpy as np
from datetime import timedelta
from config import IRI_COLUMNS, POS_COLUMNS, STAR_COLUMNS


# ─── Schema Validation ─────────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame, expected_cols: dict, file_label: str) -> list[str]:
    """Returns list of critical error strings. Empty = passed."""
    errors = []
    missing = [c for c in expected_cols if c not in df.columns]
    extra = [c for c in df.columns if c not in expected_cols]
    if missing:
        errors.append(f"**{file_label}**: Missing columns: {missing}")
    if extra:
        # Extra columns are warnings, not critical
        pass
    return errors


def validate_schema_warnings(df: pd.DataFrame, expected_cols: dict, file_label: str) -> list[str]:
    warnings = []
    extra = [c for c in df.columns if c not in expected_cols]
    if extra:
        warnings.append(f"**{file_label}**: Extra columns ignored: {extra}")
    return warnings


# ─── Data Cleaning ─────────────────────────────────────────────────────────────

def normalize_strings(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Strip whitespace and title-case brand/sku string columns."""
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().str.title()
    return df


def parse_dates(df: pd.DataFrame, file_label: str) -> tuple[pd.DataFrame, list[str]]:
    """Parse week_ending to datetime. Returns (df, critical_errors)."""
    errors = []
    try:
        df["week_ending"] = pd.to_datetime(df["week_ending"])
    except Exception as e:
        errors.append(f"**{file_label}**: Date column 'week_ending' could not be parsed: {e}")
    return df, errors


# ─── Structural Checks ─────────────────────────────────────────────────────────

def check_min_weeks(df: pd.DataFrame, file_label: str) -> list[str]:
    n = df["week_ending"].nunique()
    if n < 8:
        return [f"**{file_label}**: Fewer than 8 weeks of data ({n} found). Minimum required."]
    return []


def check_duplicates(df: pd.DataFrame, file_label: str) -> list[str]:
    key = ["brand", "sku", "week_ending"]
    dupes = df.duplicated(subset=key).sum()
    if dupes > 0:
        return [f"**{file_label}**: {dupes} duplicate rows found (same brand + SKU + week)."]
    return []


def check_date_continuity(df: pd.DataFrame, file_label: str) -> list[str]:
    """Check that each brand/SKU series has no missing weeks."""
    errors = []
    gaps_found = []
    weeks_sorted = sorted(df["week_ending"].unique())
    if len(weeks_sorted) < 2:
        return []
    # Expected weekly cadence
    expected_delta = timedelta(days=7)
    for i in range(len(weeks_sorted) - 1):
        delta = weeks_sorted[i + 1] - weeks_sorted[i]
        if delta != expected_delta:
            gaps_found.append(
                f"{weeks_sorted[i].date()} → {weeks_sorted[i+1].date()} (gap: {delta.days} days)"
            )
    if gaps_found:
        errors.append(
            f"**{file_label}**: Non-contiguous dates detected. Gaps: {gaps_found[:5]}"
            + (" (and more)" if len(gaps_found) > 5 else "")
        )
    return errors


def check_negative_values(df: pd.DataFrame, numeric_cols: list[str], file_label: str) -> list[str]:
    warnings = []
    for c in numeric_cols:
        if c in df.columns:
            n_neg = (df[c] < 0).sum()
            if n_neg > 0:
                warnings.append(f"**{file_label}**: {n_neg} negative values in '{c}'.")
    return warnings


# ─── Cross-Source Consistency ──────────────────────────────────────────────────

def check_share_sums(iri: pd.DataFrame) -> list[str]:
    warnings = []
    weekly = iri.groupby("week_ending")["market_share_dollars"].sum()
    bad = weekly[weekly > 1.05]
    if not bad.empty:
        warnings.append(
            f"Market share sums > 1.05 in {len(bad)} week(s): "
            + ", ".join(str(d.date()) for d in bad.index[:3])
            + (" ..." if len(bad) > 3 else "")
        )
    return warnings


def check_loyalty_sums(pos: pd.DataFrame, promoted_brand: str) -> list[str]:
    warnings = []
    lid_cols = [
        "loyalty_pct_brand_loyalist",
        "loyalty_pct_competitor_switch",
        "loyalty_pct_category_expander",
    ]
    pb_pos = pos[pos["brand"] == promoted_brand].copy()
    if pb_pos.empty or not all(c in pb_pos.columns for c in lid_cols):
        return warnings
    pb_pos = pb_pos.dropna(subset=lid_cols)
    if pb_pos.empty:
        return warnings
    # Check per-row (each SKU row must sum to 1.0, not the weekly aggregate)
    row_sums = pb_pos[lid_cols].sum(axis=1)
    bad_rows = row_sums[abs(row_sums - 1.0) > 0.03]
    if not bad_rows.empty:
        n_bad_weeks = pb_pos.loc[bad_rows.index, "week_ending"].nunique()
        warnings.append(
            f"loyalty_pct columns don't sum to 1.0 (±0.03) in {n_bad_weeks} week(s) for {promoted_brand}. Will normalize."
        )
    return warnings


def check_pos_vs_iri_volume(pos: pd.DataFrame, iri: pd.DataFrame, promoted_brand: str) -> list[str]:
    warnings = []
    try:
        pos_total = pos[pos["brand"] == promoted_brand]["pos_unit_sales"].sum()
        iri_total = iri[iri["brand"] == promoted_brand]["unit_sales"].sum()
        if iri_total > 0:
            ratio = pos_total / iri_total
            if abs(ratio - 1.0) > 0.25:
                warnings.append(
                    f"POS units ({pos_total:,.0f}) vs. IRI units ({iri_total:,.0f}) differ by "
                    f"{abs(ratio-1)*100:.0f}% for {promoted_brand}. Cross-source alignment check — "
                    "note this in interpretation."
                )
    except Exception:
        pass
    return warnings


# ─── Brand Detection ───────────────────────────────────────────────────────────

def detect_promoted_brand(star: pd.DataFrame) -> str:
    """Promoted brand = brand in STAR data (should be only one)."""
    brands = star["brand"].unique()
    return brands[0]  # validated elsewhere to have only promoted brand


# ─── Promo Period Detection ────────────────────────────────────────────────────

def detect_promo_periods(
    pos: pd.DataFrame, promoted_brand: str
) -> tuple[list, list[str]]:
    """
    Detect promo weeks from scan_deal_dollars > 0 for the promoted brand.
    Returns (sorted list of promo week_ending dates, warnings).
    """
    warnings = []
    pb = pos[pos["brand"] == promoted_brand]
    weekly_deal = pb.groupby("week_ending")["scan_deal_dollars"].sum()
    promo_weeks = sorted(weekly_deal[weekly_deal > 0].index.tolist())

    if len(promo_weeks) == 0:
        warnings.append("No promo weeks detected (no scan_deal_dollars > 0 for promoted brand).")
        return [], warnings

    # Check contiguity
    is_contiguous = all(
        promo_weeks[i + 1] - promo_weeks[i] == pd.Timedelta(days=7)
        for i in range(len(promo_weeks) - 1)
    )
    if not is_contiguous:
        warnings.append(
            f"Non-contiguous promo weeks detected: {[str(w.date()) for w in promo_weeks]}. "
            "Using full range as promo period."
        )
        # Fill the full span
        all_weeks = pos["week_ending"].unique()
        all_weeks_sorted = sorted(all_weeks)
        promo_weeks = [
            w for w in all_weeks_sorted
            if promo_weeks[0] <= w <= promo_weeks[-1]
        ]

    return promo_weeks, warnings


# ─── Main Load and Validate Function ──────────────────────────────────────────

def load_and_validate(iri_file, pos_file, stars_file) -> dict:
    """
    Load three files, validate, return results dict with:
      - iri, pos, stars: DataFrames
      - promoted_brand: str
      - promo_weeks: list of dates
      - pre_weeks, post_weeks: list of dates
      - critical_errors: list of str (blocks analysis)
      - warnings: list of str
      - passed: bool
    """
    result = {
        "iri": None,
        "pos": None,
        "stars": None,
        "promoted_brand": None,
        "promo_weeks": [],
        "pre_weeks": [],
        "post_weeks": [],
        "critical_errors": [],
        "warnings": [],
        "passed": False,
    }

    critical = []
    warnings = []

    # ── Load files ──
    try:
        iri = pd.read_excel(iri_file)
    except Exception as e:
        critical.append(f"**IRI file**: Could not read file: {e}")
        result["critical_errors"] = critical
        return result

    try:
        pos = pd.read_excel(pos_file)
    except Exception as e:
        critical.append(f"**POS file**: Could not read file: {e}")
        result["critical_errors"] = critical
        return result

    try:
        stars = pd.read_excel(stars_file)
    except Exception as e:
        critical.append(f"**STARS file**: Could not read file: {e}")
        result["critical_errors"] = critical
        return result

    # ── Schema validation ──
    critical += validate_schema(iri, IRI_COLUMNS, "IRI")
    critical += validate_schema(pos, POS_COLUMNS, "POS")
    critical += validate_schema(stars, STAR_COLUMNS, "STARS")
    warnings += validate_schema_warnings(iri, IRI_COLUMNS, "IRI")
    warnings += validate_schema_warnings(pos, POS_COLUMNS, "POS")
    warnings += validate_schema_warnings(stars, STAR_COLUMNS, "STARS")

    if critical:
        result["critical_errors"] = critical
        return result

    # ── Normalize string columns ──
    iri = normalize_strings(iri, ["brand", "sku"])
    pos = normalize_strings(pos, ["brand", "sku"])
    stars = normalize_strings(stars, ["brand", "sku"])

    # ── Parse dates ──
    iri, errs = parse_dates(iri, "IRI")
    critical += errs
    pos, errs = parse_dates(pos, "POS")
    critical += errs
    stars, errs = parse_dates(stars, "STAR")
    critical += errs

    if critical:
        result["critical_errors"] = critical
        return result

    # ── Min weeks ──
    critical += check_min_weeks(iri, "IRI")
    critical += check_min_weeks(pos, "POS")
    critical += check_min_weeks(stars, "STAR")

    # ── Duplicates ──
    critical += check_duplicates(iri, "IRI")
    critical += check_duplicates(pos, "POS")
    critical += check_duplicates(stars, "STAR")

    # ── Date continuity ──
    critical += check_date_continuity(iri, "IRI")
    critical += check_date_continuity(pos, "POS")
    critical += check_date_continuity(stars, "STAR")

    if critical:
        result["critical_errors"] = critical
        return result

    # ── Promoted brand detection ──
    promoted_brand = detect_promoted_brand(stars)

    # Validate promoted brand exists in IRI and POS
    if promoted_brand not in iri["brand"].unique():
        critical.append(
            f"**STAR brand '{promoted_brand}' not found in IRI data.** "
            f"IRI brands: {list(iri['brand'].unique())}"
        )
    if promoted_brand not in pos["brand"].unique():
        critical.append(
            f"**STAR brand '{promoted_brand}' not found in POS data.** "
            f"POS brands: {list(pos['brand'].unique())}"
        )

    if critical:
        result["critical_errors"] = critical
        return result

    # ── Date range alignment ──
    iri_weeks = set(iri["week_ending"])
    pos_weeks = set(pos["week_ending"])
    star_weeks = set(stars["week_ending"])
    common_weeks = iri_weeks & pos_weeks & star_weeks
    if iri_weeks != pos_weeks or iri_weeks != star_weeks:
        warnings.append(
            f"Date ranges differ across files. "
            f"IRI: {len(iri_weeks)}, POS: {len(pos_weeks)}, STAR: {len(star_weeks)} weeks. "
            f"Analyzing intersection of {len(common_weeks)} weeks."
        )
        iri = iri[iri["week_ending"].isin(common_weeks)]
        pos = pos[pos["week_ending"].isin(common_weeks)]
        stars = stars[stars["week_ending"].isin(common_weeks)]

    # ── Structural warnings ──
    warnings += check_negative_values(
        iri, ["dollar_sales", "unit_sales", "avg_net_price"], "IRI"
    )
    warnings += check_negative_values(
        pos, ["pos_dollar_sales", "pos_unit_sales", "pos_price"], "POS"
    )
    warnings += check_share_sums(iri)
    warnings += check_loyalty_sums(pos, promoted_brand)
    warnings += check_pos_vs_iri_volume(pos, iri, promoted_brand)

    # ── Promo period detection ──
    promo_weeks, promo_warnings = detect_promo_periods(pos, promoted_brand)
    warnings += promo_warnings

    all_weeks = sorted(iri["week_ending"].unique())

    if not promo_weeks:
        critical.append("No promo weeks could be detected from scan_deal_dollars. Cannot analyze.")
        result["critical_errors"] = critical
        return result

    pre_weeks = [w for w in all_weeks if w < promo_weeks[0]]
    post_weeks = [w for w in all_weeks if w > promo_weeks[-1]]

    if len(pre_weeks) < 2:
        warnings.append(
            f"Limited baseline period ({len(pre_weeks)} pre-promo week(s)). KPIs may be unreliable."
        )
    if len(post_weeks) < 4:
        warnings.append(
            f"Limited post-promo data ({len(post_weeks)} week(s)). Post-promo deficit marked as incomplete."
        )

    result.update({
        "iri": iri,
        "pos": pos,
        "stars": stars,
        "promoted_brand": promoted_brand,
        "promo_weeks": promo_weeks,
        "pre_weeks": pre_weeks,
        "post_weeks": post_weeks,
        "critical_errors": critical,
        "warnings": warnings,
        "passed": True,
    })
    return result
