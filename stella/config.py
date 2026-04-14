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
    """
    Industry reality: 72% of CPG promos are ROI-negative.
    Breakeven is top-quartile. 20%+ return is exceptional.

    ROI >= 0.20  → 100  (exceptional — well above cost of capital)
    ROI =  0.06  → 70   (good — above typical WACC)
    ROI =  0.00  → 55   (breakeven — better than ~72% of promos)
    ROI = -0.15  → 25   (typical underperformer)
    ROI <= -0.30 → 0    (clear value destruction)
    """
    if roi >= 0.20:
        return 100.0
    elif roi >= 0.0:
        return 55.0 + (roi / 0.20) * 45.0
    elif roi >= -0.30:
        return (roi + 0.30) / 0.30 * 55.0
    else:
        return 0.0


def share_score(share_change_pp: float, share_retention: float | None) -> float:
    """
    Realistic share gains from a single-retailer TPR measured in
    total market (IRI): 0.5–3 pp is the realistic range.

    Share gain >= 1.5 pp → 100 (strong competitive capture)
    Share gain =  0.5 pp → 33  (modest but real)
    Share gain <= 0      → 0   (promo failed to move share)

    Multiply by share retention to reward durability.
    """
    if share_change_pp <= 0:
        return 0.0
    base = min(share_change_pp / 1.5, 1.0) * 100.0
    if share_retention is None:
        return base * 0.5
    return base * min(max(share_retention, 0.0), 1.0)


def volume_score(net_incr_pct: float, pantry_loading_index: float) -> float:
    """
    net_incr_pct = Net Incremental Volume / (baseline_weekly × promo_weeks) × 100

    Net incr >= 80%  → 100
    Net incr =  40%  → 50
    Net incr <= 0%   → 0
    Linear between.

    Pantry loading penalty: if > 55% loyalist, multiply score by 0.8.
    """
    if net_incr_pct <= 0:
        raw = 0.0
    elif net_incr_pct >= 80:
        raw = 100.0
    else:
        raw = (net_incr_pct / 80.0) * 100.0

    if pantry_loading_index > 0.55:
        raw *= 0.8

    return min(raw, 100.0)


def inventory_health_score(pipeline_fill: float, inventory_risk: str) -> float:
    """
    Pipeline fill around a promo: some pre-loading is normal.
    Fill 0.90–1.08 → 100  (healthy — includes slight under/over)
    Fill 1.08–1.15 → linear 100 → 50
    Fill 1.15–1.25 → linear 50 → 0
    Fill > 1.25    → 0
    Fill < 0.85    → 60   (under-shipped — stockout risk)

    Deduct 15 if inventory risk = "High".
    """
    if pipeline_fill < 0.85:
        raw = 60.0
    elif pipeline_fill <= 1.08:
        raw = 100.0
    elif pipeline_fill <= 1.15:
        raw = 100.0 - (pipeline_fill - 1.08) / 0.07 * 50.0
    elif pipeline_fill <= 1.25:
        raw = 50.0 - (pipeline_fill - 1.15) / 0.10 * 50.0
    else:
        raw = 0.0

    if inventory_risk == "High":
        raw = max(0.0, raw - 15.0)

    return raw


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
    elif grade == "B" and sourcing_label == "Pantry-Loaded":
        primary = "Repeat only with tighter funding guardrails."
        rationale = [
            "Volume responded but most lift is existing buyers buying early.",
            "Test a shallower discount to see if response holds.",
        ]
    elif grade in ("A", "B") and inventory_risk in ("Moderate", "High"):
        primary = "Repeat only with tighter inventory controls."
        rationale = [
            "Promo economics are acceptable but pipeline management needs guardrails.",
            "Consider capping pre-load or shortening duration.",
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
