"""
narrative.py — Rules-based + LLM narrative generation.
"""

import json
import os


# ─── Rules-Based Narrative ─────────────────────────────────────────────────────

def generate_narrative(
    kpis: dict,
    grade: str,
    scores: dict,
    norm_weights: dict,
    composite_score: float,
    recommendation: dict,
    financials: dict,
    context: dict,
) -> str:
    """
    Returns a 4-paragraph narrative string (Markdown).
    """
    brand = kpis["promoted_brand"]
    retailer = context.get("retailer_name", "").strip()
    at_retailer = f" at {retailer}" if retailer else ""

    # Paragraph 1 — Verdict
    if grade == "A":
        para1 = (
            f"This promotion worked. The **{brand}** TPR{at_retailer} earned an **A** grade "
            f"(score: {composite_score}/100), generating **{kpis['net_incr_pct']:.1f}%** net incremental volume "
            f"and **{kpis['dollar_share_change_pp']:+.2f} pp** of dollar share gain "
            f"with an Incremental Promo ROI of **{kpis['incr_promo_roi']:.2f}**."
        )
    elif grade == "B":
        # Find strongest and weakest
        dim_scores = {
            "ROI": kpis["score_roi"],
            "Share Impact": kpis["score_share"],
            "Volume Quality": kpis["score_volume"],
            "Inventory Health": kpis["score_inventory"],
        }
        strongest = max(dim_scores, key=dim_scores.get)
        weakest = min(dim_scores, key=dim_scores.get)
        para1 = (
            f"This promotion delivered mixed results. The **{brand}** TPR{at_retailer} earned a **B** grade "
            f"(score: {composite_score}/100). **{strongest}** was solid, but **{weakest}** "
            f"limits the case for repeating without changes."
        )
    else:  # C
        # Primary failure reason
        if kpis["net_incr_volume"] <= 0:
            failure = "The promotion failed to generate net incremental volume after accounting for post-promo pull-forward"
        elif kpis["incr_promo_roi"] < 0:
            failure = f"The promotion generated a negative ROI of {kpis['incr_promo_roi']:.2f} — margin erosion exceeded incremental gains"
        else:
            failure = f"Economics and sourcing quality combined to produce a below-threshold composite score"
        para1 = (
            f"This promotion underperformed. The **{brand}** TPR{at_retailer} earned a **C** grade "
            f"(score: {composite_score}/100). {failure}."
        )

    # Paragraph 2 — Economics
    f = financials
    if f["promo_cm"] > 0:
        be_sentence = (
            f"The promo needed a **{f['breakeven_multiplier']:.1f}×** volume lift to break even on total "
            f"contribution margin; it achieved **{kpis['actual_volume_multiplier']:.1f}×**."
        )
    else:
        be_sentence = (
            "At this TPR depth, the event **cannot break even on contribution margin through volume alone** — "
            "every incremental promo unit sold loses money."
        )

    delta = kpis["all_in_margin_delta"]
    if delta > 0:
        margin_sentence = (
            f"The volume lift more than offset the per-unit erosion, generating **${delta:,.0f}** "
            f"in incremental contribution margin."
        )
    else:
        margin_sentence = (
            f"The volume lift was insufficient to offset margin erosion, resulting in "
            f"**${abs(delta):,.0f} less** total contribution margin than a no-promo scenario."
        )

    para2 = (
        f"At a list price of **${f['list_price']:.2f}** and a TPR of **${f['tpr_per_unit']:.2f}/unit**, "
        f"contribution margin dropped from **${f['standard_cm']:.2f} ({f['standard_cm_pct']:.1f}%)** "
        f"to **${f['promo_cm']:.2f} ({f['promo_cm_pct']:.1f}%)** per unit. "
        f"{be_sentence} {margin_sentence}"
    )

    # Paragraph 3 — Sourcing
    sourcing = kpis["sourcing_label"]
    if sourcing == "High Quality":
        sourcing_detail = (
            "The TPR drew meaningful volume from competitors and/or expanded the buyer base — "
            "this is real market growth, not just acceleration of existing demand."
        )
    elif sourcing == "Mixed":
        sourcing_detail = (
            "The promo attracted some new buyers but a significant share of the lift came from "
            "existing loyalists buying earlier or stocking up."
        )
    elif sourcing == "Pantry-Loaded":
        sourcing_detail = (
            "The majority of incremental volume came from existing buyers pulling purchases forward. "
            "This limits true incrementality and contributes to the post-promo volume dip."
        )
    else:
        sourcing_detail = "No loyalty data was available to assess sourcing dynamics."

    if kpis["true_growth_pct"] is not None:
        tg_str = f" True Growth (Switchers + Expanders) was **{kpis['true_growth_pct']:.0f}%** of promo volume."
    else:
        tg_str = ""

    para3 = (
        f"Sourcing quality is **{sourcing}**. {sourcing_detail}{tg_str}"
    )

    # Paragraph 4 — Operational Risk
    fill = kpis["pipeline_fill"]
    risk = kpis["inventory_risk"]
    risk_detail = kpis["inventory_explanation"]
    rr = kpis["returns_rate"] * 100.0
    if rr < 2.0:
        returns_assessment = "within normal range"
    elif rr <= 4.0:
        returns_assessment = "elevated"
    else:
        returns_assessment = "high"

    para4 = (
        f"Pipeline fill ratio is **{fill:.2f}** (**{risk}** risk). {risk_detail} "
        f"Returns rate is **{rr:.1f}%**, which is {returns_assessment}."
    )

    return "\n\n".join([para1, para2, para3, para4])


# ─── LLM Narrative (Optional) ─────────────────────────────────────────────────

def generate_llm_narrative(
    kpis: dict,
    financials: dict,
    context: dict,
    grade: str,
    composite_score: float,
) -> str:
    """
    Calls Claude API. Returns narrative string or error message.
    """
    try:
        import anthropic
    except ImportError:
        return "**AI analysis unavailable** — `anthropic` package not installed."

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "**AI analysis unavailable** — set `ANTHROPIC_API_KEY` environment variable to enable."

    try:
        client = anthropic.Anthropic(api_key=api_key)

        brand = kpis["promoted_brand"]
        retailer = context.get("retailer_name") or "Not specified"
        f = financials

        kpi_summary = {
            "grade": grade,
            "composite_score": composite_score,
            "net_incr_volume_units": round(kpis["net_incr_volume"], 0),
            "net_incr_volume_pct": round(kpis["net_incr_pct"], 1),
            "gross_incr_volume": round(kpis["gross_incr_volume"], 0),
            "post_promo_deficit": round(kpis["post_promo_deficit"], 0),
            "actual_volume_multiplier": round(kpis["actual_volume_multiplier"], 2),
            "incr_promo_roi": round(kpis["incr_promo_roi"], 2),
            "all_in_margin_delta": round(kpis["all_in_margin_delta"], 0),
            "dollar_share_change_pp": round(kpis["dollar_share_change_pp"], 2),
            "share_retention": round(kpis["share_retention"], 2) if kpis["share_retention"] is not None else "N/A",
            "sourcing_quality": kpis["sourcing_label"],
            "true_growth_pct": round(kpis["true_growth_pct"], 1) if kpis["true_growth_pct"] is not None else "N/A",
            "pantry_loading_index_pct": round(kpis["pantry_loading_index"] * 100, 1),
            "pipeline_fill_ratio": round(kpis["pipeline_fill"], 2),
            "returns_rate_pct": round(kpis["returns_rate"] * 100, 1),
            "inventory_risk": kpis["inventory_risk"],
        }

        be_mult = f["breakeven_multiplier"]
        be_str = f"{be_mult:.1f}×" if be_mult else "N/A (promo CM ≤ 0)"

        prompt = f"""Write a 4–5 paragraph executive assessment of this promotion.

PROMOTION CONTEXT:
- Brand: {brand}
- Retailer: {retailer}
- Type: TPR of ${f['tpr_per_unit']:.2f}/unit for {kpis['n_promo']} weeks
- Window: {kpis['n_total']} weeks ({kpis['n_pre']} pre / {kpis['n_promo']} promo / {kpis['n_post']} post)

PRODUCT ECONOMICS:
- List Price: ${f['list_price']:.2f}  |  COGS: ${f['cogs']:.2f}  |  Std Trade: {f['standard_trade_rate']:.0f}%
- Standard CM: ${f['standard_cm']:.2f} ({f['standard_cm_pct']:.1f}%)  |  Promo CM: ${f['promo_cm']:.2f} ({f['promo_cm_pct']:.1f}%)
- Breakeven volume multiplier: {be_str}

KPI SUMMARY:
{json.dumps(kpi_summary, indent=2)}

Cover: (1) verdict and grade justification, (2) margin decomposition, (3) sourcing quality, (4) competitive dynamics, (5) inventory risk and next steps."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=(
                "You are a senior CPG trade analyst writing a post-promotion review for internal stakeholders. "
                "Be direct, analytical, and specific. Lead with conclusions. "
                "Use the data provided — do not invent numbers."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except Exception as e:
        return f"**AI analysis unavailable** — API error: {str(e)}"
