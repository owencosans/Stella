"""
config.py — Schemas, defaults, color palette, grading thresholds, recommendation rules.
"""

# ─── Column Schemas ────────────────────────────────────────────────────────────

IRI_COLUMNS = {
    "week_ending": "date",
    "brand": "str",
    "sku": "str",
    "dollar_sales": "float",
    "unit_sales": "float",
    "avg_net_price": "float",
    "market_share_dollars": "float",
    "market_share_units": "float",
    "tdp": "float",
    "any_promo_flag": "bool",
}

POS_COLUMNS = {
    "week_ending": "date",
    "brand": "str",
    "sku": "str",
    "pos_dollar_sales": "float",
    "pos_unit_sales": "float",
    "pos_price": "float",
    "scan_deal_dollars": "float",
    "loyalty_pct_brand_loyalist": "float",
    "loyalty_pct_competitor_switch": "float",
    "loyalty_pct_category_expander": "float",
}

STAR_COLUMNS = {
    "week_ending": "date",
    "brand": "str",
    "sku": "str",
    "cases_shipped": "int",
    "units_per_case": "int",
    "units_shipped": "int",
    "returns_units": "int",
    "estimated_retail_on_hand": "int",
}

# ─── Default Financial Values ──────────────────────────────────────────────────

DEFAULTS = {
    "list_price": 6.29,
    "cogs": 2.10,
    "standard_trade_rate": 18.0,
    "tpr_per_unit": 1.25,
    "retailer_name": "",
    "funding_type": "Manufacturer-funded scan-back",
    "analysis_notes": "",
}

DEFAULT_WEIGHTS = {
    "roi": 40,
    "share": 25,
    "volume": 20,
    "inventory": 15,
}

# ─── Color Palette ─────────────────────────────────────────────────────────────

BRAND_COLORS = [
    "#1E88E5",  # Promoted brand — blue
    "#8E24AA",  # 2nd — purple
    "#43A047",  # 3rd — green
    "#FB8C00",  # 4th — orange
    "#757575",  # 5th — gray
]

GRADE_COLORS = {
    "A": "#2E7D32",   # green
    "B": "#F57F17",   # amber
    "C": "#C62828",   # red
}

GRADE_BG_COLORS = {
    "A": "#E8F5E9",
    "B": "#FFF8E1",
    "C": "#FFEBEE",
}

# ─── Grading Thresholds ────────────────────────────────────────────────────────

def grade_from_score(score: float) -> str:
    if score >= 75:
        return "A"
    elif score >= 50:
        return "B"
    else:
        return "C"


def roi_score(roi: float) -> float:
    """0–100. ROI >= 1.5 → 100; <= 0 → 0; linear between.
    NOTE: The 1.5 top-end threshold is configurable — for shallow TPRs a 0.28 ROI
    may be typical. Consider lowering to ~0.8 after seeing calibrated real data."""
    if roi >= 1.5:
        return 100.0
    elif roi <= 0:
        return 0.0
    else:
        return (roi / 1.5) * 100.0


def share_score(share_gain_pp: float, share_retention: float | None) -> float:
    """
    0–100. Share gain >= 2pp → 100; <= 0 → 0; linear.

    Retention adjusts the base score:
      - None (no post-promo data): multiply by 0.5
      - >= 0 (share held at or above baseline after promo): no penalty — returning
        to baseline is a healthy TPR outcome, not a failure
      - < 0 (share dropped below baseline post-promo): apply penalty
        score = base × max(0, 1 + retention)

    This prevents the score from collapsing to 0 when a promotion does its job
    (lifts share temporarily) but doesn't permanently move the needle.
    """
    if share_gain_pp <= 0:
        return 0.0
    base = min(share_gain_pp / 2.0, 1.0) * 100.0
    if share_retention is None:
        return base * 0.5
    elif share_retention >= 0.0:
        return base  # full credit; share held at or above baseline
    else:
        return base * max(0.0, 1.0 + share_retention)


def volume_score(net_incr_pct: float, pantry_loading_index: float) -> float:
    """
    Net incremental as % of baseline-window total. >= 20% → 100; <= 0 → 0; linear.
    If pantry loading index > 55%, multiply by 0.8.
    """
    if net_incr_pct >= 20.0:
        raw = 100.0
    elif net_incr_pct <= 0:
        raw = 0.0
    else:
        raw = (net_incr_pct / 20.0) * 100.0

    if pantry_loading_index > 0.55:
        raw *= 0.8
    return raw


def inventory_health_score(pipeline_fill: float, inventory_risk: str) -> float:
    """
    Pipeline fill scoring:
      1.00–1.05 → 100
      1.05–1.10 → 80
      1.10–1.15 → 50
      1.15–1.20 → 25
      > 1.20    → 0
    Deduct 20 if risk = High.
    """
    if pipeline_fill <= 1.05:
        score = 100.0
    elif pipeline_fill <= 1.10:
        score = 80.0
    elif pipeline_fill <= 1.15:
        score = 50.0
    elif pipeline_fill <= 1.20:
        score = 25.0
    else:
        score = 0.0

    if inventory_risk == "High":
        score = max(0.0, score - 20.0)
    return score


# ─── Inventory Risk Thresholds ─────────────────────────────────────────────────

def inventory_risk_level(
    pipeline_fill: float,
    returns_rate: float,
    post_promo_shipment_collapse_weeks_60: int,
    post_promo_shipment_collapse_weeks_50: int,
) -> tuple[str, str]:
    """
    Returns (risk_level, explanation).
    """
    if (
        pipeline_fill > 1.20
        or returns_rate > 0.03
        or post_promo_shipment_collapse_weeks_50 >= 3
    ):
        level = "High"
        if pipeline_fill > 1.20:
            explanation = f"Pipeline fill of {pipeline_fill:.2f}× indicates significant overfill."
        elif returns_rate > 0.03:
            explanation = f"Returns rate of {returns_rate*100:.1f}% exceeds acceptable threshold."
        else:
            explanation = "Post-promo shipments collapsed below 50% of baseline for 3+ weeks."
    elif (
        pipeline_fill > 1.10
        or post_promo_shipment_collapse_weeks_60 >= 2
    ):
        level = "Moderate"
        if pipeline_fill > 1.10:
            explanation = f"Pipeline fill of {pipeline_fill:.2f}× suggests possible inventory overhang."
        else:
            explanation = "Post-promo shipments dropped below 60% of baseline for 2+ weeks."
    else:
        level = "Low"
        explanation = "Pipeline fill is within healthy range with no signs of overhang."

    return level, explanation


# ─── Sourcing Quality Labels ───────────────────────────────────────────────────

def sourcing_quality_label(
    avg_loyalist_pct: float,
    avg_switcher_pct: float,
    avg_expander_pct: float,
) -> str:
    if avg_switcher_pct >= 0.30 or avg_expander_pct >= 0.20:
        return "High Quality"
    elif avg_loyalist_pct <= 0.60 and (avg_switcher_pct + avg_expander_pct) >= 0.30:
        return "Mixed"
    else:
        return "Pantry-Loaded"


# ─── Recommendation Rules ──────────────────────────────────────────────────────

def compute_recommendation(
    grade: str,
    sourcing_label: str,
    inventory_risk: str,
    net_incr_volume: float,
    roi: float,
    margin_delta: float,
) -> dict:
    """
    Returns dict with 'primary' recommendation and 'rationale' list.
    """
    primary = ""
    rationale = []

    if grade == "A" and sourcing_label != "Pantry-Loaded" and inventory_risk == "Low":
        primary = "Repeat with similar mechanics."
        rationale = [
            "Volume, economics, and sourcing all support re-execution.",
            "Maintain current TPR depth and promo duration.",
        ]
    elif grade == "B" and sourcing_label == "High Quality" and inventory_risk == "Low":
        primary = "Repeat with similar mechanics."
        rationale = [
            "Sourcing quality and volume lift support re-execution.",
            "Monitor ROI and adjust TPR depth as more data accumulates.",
        ]
    elif grade in ("A", "B") and inventory_risk in ("Moderate", "High"):
        primary = "Repeat only with tighter inventory controls."
        rationale = [
            "Promo economics are acceptable but pipeline management needs guardrails.",
            "Consider capping pre-load or shortening duration.",
        ]
    elif grade == "B" and sourcing_label == "Pantry-Loaded":
        primary = "Repeat only with tighter funding guardrails."
        rationale = [
            "Volume responded but most lift is existing buyers buying early.",
            "Test a shallower discount to see if response holds.",
        ]
    elif grade == "B" and margin_delta < 0:
        primary = "Test a shallower discount."
        rationale = [
            "Volume lifted but margin erosion exceeded the gain.",
            "The TPR is too deep for the lift it generates.",
        ]
    elif grade == "C" and inventory_risk == "High":
        primary = "Do not repeat; resolve inventory overhang first."
        rationale = [
            "Elevated pipeline fill and returns indicate operational drag.",
            "Inventory must clear before re-promoting.",
        ]
    elif grade == "C" and net_incr_volume <= 0:
        primary = "Do not repeat."
        rationale = [
            "The promotion failed to generate net incremental volume after accounting for post-promo pull-forward.",
        ]
    elif grade == "C" and net_incr_volume > 0 and roi < 0.5:
        primary = "Do not repeat at current depth."
        rationale = [
            "The promo moved volume but destroyed value.",
            "Incrementality does not justify the investment.",
        ]
    else:
        # Fallback for unmatched combinations
        if grade == "A":
            primary = "Repeat with similar mechanics."
            rationale = ["Overall results support re-execution."]
        elif grade == "B":
            primary = "Repeat with modifications."
            rationale = ["Review the weakest dimension before re-executing."]
        else:
            primary = "Do not repeat at current mechanics."
            rationale = ["Results do not justify the investment at this configuration."]

    return {"primary": primary, "rationale": rationale}
