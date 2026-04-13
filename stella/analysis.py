"""
analysis.py — Counterfactual baseline, KPI engine, grading, recommendation engine.
"""

import pandas as pd
import numpy as np
from config import (
    roi_score, share_score, volume_score, inventory_health_score,
    grade_from_score, inventory_risk_level, sourcing_quality_label,
    compute_recommendation,
)


# ─── Financial Inputs ──────────────────────────────────────────────────────────

def compute_financials(
    list_price: float,
    cogs: float,
    standard_trade_rate: float,
    tpr_per_unit: float,
) -> dict:
    standard_trade_dollar = list_price * standard_trade_rate / 100.0
    gross_margin = list_price - cogs
    standard_cm = gross_margin - standard_trade_dollar
    standard_cm_pct = standard_cm / list_price * 100.0
    promo_cm = standard_cm - tpr_per_unit
    promo_cm_pct = promo_cm / list_price * 100.0
    cm_erosion = tpr_per_unit

    if promo_cm > 0:
        breakeven_multiplier = standard_cm / promo_cm
    else:
        breakeven_multiplier = None  # N/A — cannot break even

    return {
        "list_price": list_price,
        "cogs": cogs,
        "standard_trade_rate": standard_trade_rate,
        "standard_trade_dollar": standard_trade_dollar,
        "tpr_per_unit": tpr_per_unit,
        "gross_margin": gross_margin,
        "standard_cm": standard_cm,
        "standard_cm_pct": standard_cm_pct,
        "promo_cm": promo_cm,
        "promo_cm_pct": promo_cm_pct,
        "cm_erosion": cm_erosion,
        "breakeven_multiplier": breakeven_multiplier,
    }


# ─── Counterfactual Baseline ───────────────────────────────────────────────────

def compute_baseline(
    pos: pd.DataFrame,
    iri: pd.DataFrame,
    promoted_brand: str,
    pre_weeks: list,
) -> dict:
    """
    Baseline weekly unit velocity = avg POS pos_unit_sales per week for promoted brand, pre-promo.
    Baseline weekly dollar share = avg IRI market_share_dollars for promoted brand, pre-promo.
    """
    pb_pos = pos[pos["brand"] == promoted_brand]
    pb_iri = iri[iri["brand"] == promoted_brand]

    # Brand-level weekly units (sum all SKUs per week)
    pre_pos = pb_pos[pb_pos["week_ending"].isin(pre_weeks)]
    weekly_units = pre_pos.groupby("week_ending")["pos_unit_sales"].sum()
    baseline_weekly_units = weekly_units.mean() if not weekly_units.empty else 0.0

    pre_iri = pb_iri[pb_iri["week_ending"].isin(pre_weeks)]
    weekly_share = pre_iri.groupby("week_ending")["market_share_dollars"].sum()
    baseline_weekly_share = weekly_share.mean() if not weekly_share.empty else 0.0

    return {
        "baseline_weekly_units": baseline_weekly_units,
        "baseline_weekly_share": baseline_weekly_share,
    }


# ─── Core KPI Calculations ─────────────────────────────────────────────────────

def normalize_loyalty(pos: pd.DataFrame, promoted_brand: str) -> pd.DataFrame:
    """Normalize loyalty_pct_* to sum to 1.0 for promoted brand where needed."""
    lid_cols = [
        "loyalty_pct_brand_loyalist",
        "loyalty_pct_competitor_switch",
        "loyalty_pct_category_expander",
    ]
    pos = pos.copy()
    mask = pos["brand"] == promoted_brand
    pb = pos.loc[mask, lid_cols]
    row_sums = pb.sum(axis=1)
    bad = abs(row_sums - 1.0) > 0.02
    if bad.any():
        # Normalize
        for col in lid_cols:
            pos.loc[mask & bad, col] = pos.loc[mask & bad, col] / row_sums[mask & bad]
    return pos


def calculate_kpis(
    iri: pd.DataFrame,
    pos: pd.DataFrame,
    stars: pd.DataFrame,
    promoted_brand: str,
    pre_weeks: list,
    promo_weeks: list,
    post_weeks: list,
    financials: dict,
) -> dict:
    """Main KPI calculation function. Returns full kpi dict."""

    pos = normalize_loyalty(pos, promoted_brand)

    baseline = compute_baseline(pos, iri, promoted_brand, pre_weeks)
    bwu = baseline["baseline_weekly_units"]  # baseline weekly units
    bws = baseline["baseline_weekly_share"]  # baseline weekly share

    pb_pos = pos[pos["brand"] == promoted_brand]
    pb_iri = iri[iri["brand"] == promoted_brand]
    n_promo = len(promo_weeks)
    n_post = len(post_weeks)
    n_pre = len(pre_weeks)
    n_total = n_pre + n_promo + n_post

    # ── Volume KPIs ──
    promo_pos = pb_pos[pb_pos["week_ending"].isin(promo_weeks)]
    promo_units_total = promo_pos.groupby("week_ending")["pos_unit_sales"].sum().sum()
    baseline_equiv_units = bwu * n_promo

    gross_incr_volume = promo_units_total - baseline_equiv_units

    # Post-promo deficit
    post_pos = pb_pos[pb_pos["week_ending"].isin(post_weeks)]
    post_weekly_units = post_pos.groupby("week_ending")["pos_unit_sales"].sum()
    weekly_deficits = (bwu - post_weekly_units).clip(lower=0)
    post_promo_deficit = weekly_deficits.sum()
    post_promo_incomplete = n_post < 4

    net_incr_volume = gross_incr_volume - post_promo_deficit

    # Baseline window total for volume score denominator
    # = baseline weekly units × total window weeks
    baseline_window_total = bwu * n_total
    net_incr_pct = (net_incr_volume / baseline_window_total * 100.0) if baseline_window_total > 0 else 0.0

    actual_volume_multiplier = (promo_units_total / baseline_equiv_units) if baseline_equiv_units > 0 else 0.0

    # ── Economic KPIs ──
    f = financials
    promo_period_total_cm = promo_units_total * f["promo_cm"]
    baseline_equiv_cm = baseline_equiv_units * f["standard_cm"]
    incr_promo_period_cm = promo_period_total_cm - baseline_equiv_cm
    post_promo_cm_loss = post_promo_deficit * f["standard_cm"]
    net_incr_cm = incr_promo_period_cm - post_promo_cm_loss

    # Incremental TPR investment
    incr_tpr_investment = f["tpr_per_unit"] * promo_units_total

    # ROI
    if incr_tpr_investment > 0:
        incr_promo_roi = net_incr_cm / incr_tpr_investment
    else:
        incr_promo_roi = 0.0

    # ── Share KPIs ──
    promo_iri = pb_iri[pb_iri["week_ending"].isin(promo_weeks)]
    promo_avg_share = promo_iri.groupby("week_ending")["market_share_dollars"].sum().mean()
    if promo_avg_share is None or pd.isna(promo_avg_share):
        promo_avg_share = 0.0

    dollar_share_change = promo_avg_share - bws  # in decimal (pp = *100)

    # Share retention: (late-post avg share − baseline) / (promo avg − baseline)
    late_post_weeks = post_weeks[-4:] if len(post_weeks) >= 4 else post_weeks
    late_post_iri = pb_iri[pb_iri["week_ending"].isin(late_post_weeks)]
    if late_post_iri.empty:
        late_post_avg_share = bws
    else:
        late_post_avg_share = late_post_iri.groupby("week_ending")["market_share_dollars"].sum().mean()

    share_gain = promo_avg_share - bws
    if abs(share_gain) < 0.001:  # < 0.1 pp
        share_retention = None  # N/A
    elif share_gain > 0:
        share_retention = (late_post_avg_share - bws) / share_gain
    else:
        share_retention = 0.0

    # ── Sourcing / LID KPIs ──
    lid_cols = [
        "loyalty_pct_brand_loyalist",
        "loyalty_pct_competitor_switch",
        "loyalty_pct_category_expander",
    ]
    promo_pb_pos = pb_pos[pb_pos["week_ending"].isin(promo_weeks)]
    has_lid = all(c in promo_pb_pos.columns for c in lid_cols) and not promo_pb_pos[lid_cols].isna().all().all()

    if has_lid:
        # Weight by units sold
        promo_pb_pos_lid = promo_pb_pos.dropna(subset=lid_cols)
        if not promo_pb_pos_lid.empty:
            avg_loyalist = np.average(
                promo_pb_pos_lid["loyalty_pct_brand_loyalist"],
                weights=promo_pb_pos_lid["pos_unit_sales"].clip(lower=0) + 1e-9,
            )
            avg_switcher = np.average(
                promo_pb_pos_lid["loyalty_pct_competitor_switch"],
                weights=promo_pb_pos_lid["pos_unit_sales"].clip(lower=0) + 1e-9,
            )
            avg_expander = np.average(
                promo_pb_pos_lid["loyalty_pct_category_expander"],
                weights=promo_pb_pos_lid["pos_unit_sales"].clip(lower=0) + 1e-9,
            )
        else:
            avg_loyalist = avg_switcher = avg_expander = None
            has_lid = False
    else:
        avg_loyalist = avg_switcher = avg_expander = None

    if has_lid and avg_loyalist is not None:
        pantry_loading_index = avg_loyalist
        sourcing_label = sourcing_quality_label(avg_loyalist, avg_switcher, avg_expander)
        true_growth_pct = (avg_switcher + avg_expander) * 100.0
    else:
        pantry_loading_index = 0.0
        sourcing_label = "Unavailable"
        true_growth_pct = None

    # ── LID weekly data for charts ──
    if has_lid:
        all_pb_pos = pb_pos.copy()
        all_pb_pos_lid = all_pb_pos.dropna(subset=lid_cols)
        lid_weekly = all_pb_pos_lid.groupby("week_ending")[lid_cols + ["pos_unit_sales"]].mean().reset_index()
    else:
        lid_weekly = pd.DataFrame()

    # ── Inventory / STAR KPIs ──
    pb_stars = stars[stars["brand"] == promoted_brand]
    total_shipped = pb_stars["units_shipped"].sum()
    total_returns = pb_stars["returns_units"].sum()
    total_pos_units = pb_pos["pos_unit_sales"].sum()

    pipeline_fill = total_shipped / total_pos_units if total_pos_units > 0 else 1.0
    returns_rate = total_returns / total_shipped if total_shipped > 0 else 0.0

    # Post-promo shipment collapse
    post_stars = pb_stars[pb_stars["week_ending"].isin(post_weeks)]
    post_weekly_shipped = post_stars.groupby("week_ending")["units_shipped"].sum()
    baseline_weekly_shipped = (
        pb_stars[pb_stars["week_ending"].isin(pre_weeks)]
        .groupby("week_ending")["units_shipped"].sum().mean()
    ) if pre_weeks else 0

    if baseline_weekly_shipped > 0:
        collapse_60 = int((post_weekly_shipped < 0.60 * baseline_weekly_shipped).sum())
        collapse_50 = int((post_weekly_shipped < 0.50 * baseline_weekly_shipped).sum())
    else:
        collapse_60 = collapse_50 = 0

    inv_risk, inv_explanation = inventory_risk_level(
        pipeline_fill, returns_rate, collapse_60, collapse_50
    )

    # Under-shipped flag
    under_shipped = pipeline_fill < 0.85

    # ── Scoring ──
    s_roi = roi_score(incr_promo_roi)
    s_share = share_score(dollar_share_change * 100.0, share_retention)
    s_volume = volume_score(net_incr_pct, pantry_loading_index)
    s_inventory = inventory_health_score(pipeline_fill, inv_risk)

    # ── Competitive Share (for charts) ──
    all_brands = iri["brand"].unique().tolist()
    competitor_brands = [b for b in all_brands if b != promoted_brand]

    # ── Assemble KPI dict ──
    kpis = {
        # Periods
        "n_pre": n_pre,
        "n_promo": n_promo,
        "n_post": n_post,
        "n_total": n_total,
        "pre_weeks": pre_weeks,
        "promo_weeks": promo_weeks,
        "post_weeks": post_weeks,
        "post_promo_incomplete": post_promo_incomplete,

        # Volume
        "baseline_weekly_units": bwu,
        "baseline_equiv_units": baseline_equiv_units,
        "promo_units_total": promo_units_total,
        "gross_incr_volume": gross_incr_volume,
        "post_promo_deficit": post_promo_deficit,
        "net_incr_volume": net_incr_volume,
        "net_incr_pct": net_incr_pct,
        "actual_volume_multiplier": actual_volume_multiplier,

        # Economics
        "promo_period_total_cm": promo_period_total_cm,
        "baseline_equiv_cm": baseline_equiv_cm,
        "incr_promo_period_cm": incr_promo_period_cm,
        "post_promo_cm_loss": post_promo_cm_loss,
        "net_incr_cm": net_incr_cm,
        "incr_tpr_investment": incr_tpr_investment,
        "incr_promo_roi": incr_promo_roi,
        "all_in_margin_delta": net_incr_cm,  # canonical display label

        # Share
        "baseline_weekly_share": bws,
        "promo_avg_share": promo_avg_share,
        "dollar_share_change_pp": dollar_share_change * 100.0,
        "share_retention": share_retention,
        "late_post_avg_share": late_post_avg_share,

        # Sourcing
        "has_lid": has_lid,
        "avg_loyalist_pct": avg_loyalist,
        "avg_switcher_pct": avg_switcher,
        "avg_expander_pct": avg_expander,
        "pantry_loading_index": pantry_loading_index,
        "sourcing_label": sourcing_label,
        "true_growth_pct": true_growth_pct,
        "lid_weekly": lid_weekly,

        # Inventory
        "total_shipped": total_shipped,
        "total_returns": total_returns,
        "pipeline_fill": pipeline_fill,
        "returns_rate": returns_rate,
        "inventory_risk": inv_risk,
        "inventory_explanation": inv_explanation,
        "under_shipped": under_shipped,

        # Sub-scores (pre-weight)
        "score_roi": s_roi,
        "score_share": s_share,
        "score_volume": s_volume,
        "score_inventory": s_inventory,

        # Meta
        "promoted_brand": promoted_brand,
        "competitor_brands": competitor_brands,
        "all_brands": all_brands,
    }

    return kpis


# ─── Grading Engine ────────────────────────────────────────────────────────────

def compute_grade(kpis: dict, weights: dict) -> tuple[str, dict, float]:
    """
    weights: dict with keys roi, share, volume, inventory (sum should be 100).
    Returns (grade, normalized_weights, composite_score).
    """
    total_w = sum(weights.values())
    if total_w == 0:
        total_w = 100
    norm_w = {k: v / total_w for k, v in weights.items()}

    composite = (
        norm_w["roi"] * kpis["score_roi"]
        + norm_w["share"] * kpis["score_share"]
        + norm_w["volume"] * kpis["score_volume"]
        + norm_w["inventory"] * kpis["score_inventory"]
    )
    grade = grade_from_score(composite)
    return grade, norm_w, round(composite, 1)
