"""
app.py — Stella: Post-Promotion Analysis Engine.
Named for Stella Cosans, born April 2026. See your KPIs in the stars.
"""

import streamlit as st
import pandas as pd
import numpy as np

from config import DEFAULTS, DEFAULT_WEIGHTS, GRADE_COLORS, GRADE_BG_COLORS, compute_recommendation
from ingestion import load_and_validate
from analysis import compute_financials, calculate_kpis, compute_grade
from narrative import generate_narrative, generate_llm_narrative
from visualizations import (
    assign_brand_colors,
    chart_price_ladders,
    chart_market_share,
    chart_lid_sourcing,
    chart_volume_returns,
    chart_margin_waterfall,
    chart_shipments_vs_pull,
)

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Stella", layout="wide", page_icon="⭐")

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
.grade-badge {
    display: inline-block;
    font-size: 4rem;
    font-weight: 800;
    padding: 0.2em 0.6em;
    border-radius: 12px;
    line-height: 1.1;
    margin-bottom: 0.3em;
}
.kpi-card {
    background: #F8F9FA;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
    border-left: 4px solid #1E88E5;
}
.kpi-label {
    font-size: 0.78rem;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.kpi-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1A1A2E;
}
.kpi-sub {
    font-size: 0.82rem;
    color: #888;
}
.rec-card {
    background: #EBF5FB;
    border-left: 5px solid #1E88E5;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
}
.traffic-light-low { color: #2E7D32; font-weight: 700; }
.traffic-light-moderate { color: #F57F17; font-weight: 700; }
.traffic-light-high { color: #C62828; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("⭐ STELLA — Post-Promotion Analysis")
st.caption("See your KPIs in the stars")

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("📁 Data Input")
    iri_file = st.file_uploader("IRI Data (syndicated)", type="xlsx", key="iri")
    pos_file = st.file_uploader("POS Data (retail scan)", type="xlsx", key="pos")
    stars_file = st.file_uploader("STARS Data (shipments)", type="xlsx", key="stars")

    st.divider()
    st.header("📋 Promotion Context")
    retailer_name = st.text_input("Retailer Name", value=DEFAULTS["retailer_name"],
                                   placeholder="e.g. Kroger")
    st.markdown("**Promotion Type:** TPR *(fixed in v1)*")
    funding_type = st.text_input("Funding Type", value=DEFAULTS["funding_type"])
    analysis_notes = st.text_area("Analysis Notes", value=DEFAULTS["analysis_notes"],
                                   height=80)

    st.divider()
    st.header("💰 Product Economics")
    list_price = st.number_input("List Price ($/unit)", value=DEFAULTS["list_price"],
                                  step=0.01, format="%.2f", min_value=0.01)
    cogs = st.number_input("COGS ($/unit)", value=DEFAULTS["cogs"],
                            step=0.01, format="%.2f", min_value=0.01)
    trade_rate = st.slider("Standard Trade Rate (%)", 0, 50,
                            int(DEFAULTS["standard_trade_rate"]))
    tpr_amount = st.number_input("TPR Amount ($/unit)", value=DEFAULTS["tpr_per_unit"],
                                  step=0.01, format="%.2f", min_value=0.0)

    # ── Validate economics ──
    fin = compute_financials(list_price, cogs, float(trade_rate), tpr_amount)
    std_trade_dollar = fin["standard_trade_dollar"]
    if list_price <= cogs:
        st.error("⚠️ List Price must be greater than COGS.")
    elif tpr_amount >= list_price - cogs - std_trade_dollar and tpr_amount > 0:
        st.warning("⚠️ TPR exceeds Standard CM. Promo CM is ≤ 0 — this event cannot break even on CM through volume alone.")

    # ── Derived metrics (read-only) ──
    st.markdown("---")
    st.markdown("**Derived Economics**")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Gross Margin/unit", f"${fin['gross_margin']:.2f}")
        st.metric("Standard CM/unit", f"${fin['standard_cm']:.2f}")
        st.metric("Standard CM %", f"{fin['standard_cm_pct']:.1f}%")
    with col2:
        st.metric("Promo CM/unit", f"${fin['promo_cm']:.2f}")
        st.metric("Promo CM %", f"{fin['promo_cm_pct']:.1f}%")
        if fin["breakeven_multiplier"]:
            st.metric("Breakeven Mult.", f"{fin['breakeven_multiplier']:.1f}×")
        else:
            st.metric("Breakeven Mult.", "N/A")

    st.divider()
    st.header("⚖️ Grading Weights")
    w_roi = st.slider("Incremental Promo ROI", 0, 100, DEFAULT_WEIGHTS["roi"])
    w_share = st.slider("Share Impact", 0, 100, DEFAULT_WEIGHTS["share"])
    w_volume = st.slider("Volume Quality", 0, 100, DEFAULT_WEIGHTS["volume"])
    w_inventory = st.slider("Inventory Health", 0, 100, DEFAULT_WEIGHTS["inventory"])

    weights_raw = {"roi": w_roi, "share": w_share, "volume": w_volume, "inventory": w_inventory}
    weight_sum = sum(weights_raw.values())
    if weight_sum != 100:
        st.info(
            f"Weights sum to {weight_sum}. Auto-normalizing to 100%.\n\n"
            + " | ".join([f"{k}: {v/weight_sum*100:.1f}%" for k, v in weights_raw.items()])
        )


# ─── Main Content ─────────────────────────────────────────────────────────────

all_uploaded = iri_file and pos_file and stars_file

if not all_uploaded:
    st.markdown("""
    ### How to use Stella

    1. **Prepare three Excel files** matching the required schemas (see README for column definitions)
    2. **Upload IRI, POS, and STAR files** in the sidebar
    3. **Configure your product economics** and TPR amount
    4. **Adjust grading weights** to reflect your priorities

    Stella will validate your data, calculate KPIs across all three sources, and produce a graded
    assessment with a clear recommendation.

    ---

    **Data required:**
    - `iri_data.xlsx` — Syndicated scanner data (IRI/Circana), all brands, all weeks
    - `pos_data.xlsx` — Retailer point-of-sale scan data with loyalty sourcing (LID)
    - `stars_data.xlsx` — Wholesale shipment data (STARS), promoted brand only
    """)
    st.stop()

# ─── Load and Validate ────────────────────────────────────────────────────────

with st.spinner("Validating data..."):
    validated = load_and_validate(iri_file, pos_file, stars_file)

# Critical errors — block
if validated["critical_errors"]:
    st.error("### Data Validation Failed")
    for err in validated["critical_errors"]:
        st.error(err)
    st.stop()

# Warnings — tucked into an expander so they don't dominate the first view
if validated["warnings"]:
    with st.expander(f"Data Validation Notes ({len(validated['warnings'])} notice(s))", expanded=False):
        for w in validated["warnings"]:
            st.warning(w)

iri = validated["iri"]
pos = validated["pos"]
stars = validated["stars"]
promoted_brand = validated["promoted_brand"]
promo_weeks = validated["promo_weeks"]
pre_weeks = validated["pre_weeks"]
post_weeks = validated["post_weeks"]

st.success(f"Promoted brand detected: **{promoted_brand}**")
st.caption(
    f"Period: {len(pre_weeks)} pre / {len(promo_weeks)} promo / {len(post_weeks)} post weeks  |  "
    f"Promo: {promo_weeks[0].date()} → {promo_weeks[-1].date()}"
)

# ─── Compute KPIs ─────────────────────────────────────────────────────────────

with st.spinner("Computing KPIs..."):
    kpis = calculate_kpis(
        iri, pos, stars,
        promoted_brand, pre_weeks, promo_weeks, post_weeks,
        fin,
    )

grade, norm_weights, composite_score = compute_grade(kpis, weights_raw)
recommendation = compute_recommendation(
    grade,
    kpis["sourcing_label"],
    kpis["inventory_risk"],
    kpis["net_incr_volume"],
    kpis["incr_promo_roi"],
    kpis["all_in_margin_delta"],
)
context = {
    "retailer_name": retailer_name,
    "funding_type": funding_type,
    "analysis_notes": analysis_notes,
}
narrative_text = generate_narrative(
    kpis, grade, kpis, norm_weights, composite_score, recommendation, fin, context
)

color_map = assign_brand_colors(kpis["all_brands"], promoted_brand)

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tabs = st.tabs([
    "⭐ Executive Summary",
    "💲 Price Ladders",
    "📊 Market Share",
    "👥 LID Sourcing",
    "📦 Volume & Returns",
    "💰 Margin Waterfall",
    "🚚 Shipments vs. Pull",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Executive Summary
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    # Grade Badge
    grade_color = GRADE_COLORS[grade]
    grade_bg = GRADE_BG_COLORS[grade]
    col_grade, col_rec = st.columns([1, 3])
    with col_grade:
        st.markdown(
            f'<div class="grade-badge" style="background:{grade_bg}; color:{grade_color};">'
            f'{grade}<br><span style="font-size:1.1rem; font-weight:400;">{composite_score}/100</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_rec:
        st.markdown(
            f'<div class="rec-card">'
            f'<strong>Recommendation: {recommendation["primary"]}</strong><br>'
            + "<br>".join(f"• {r}" for r in recommendation["rationale"])
            + "</div>",
            unsafe_allow_html=True,
        )

    if analysis_notes.strip():
        st.info(f"📝 **Analysis Notes:** {analysis_notes}")

    st.divider()

    # KPI Cards — Row 1
    c1, c2, c3 = st.columns(3)
    with c1:
        roi = kpis["incr_promo_roi"]
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Incremental Promo ROI</div>'
            f'<div class="kpi-value">{roi:.2f}</div>'
            f'<div class="kpi-sub">Net Incr. CM / TPR Investment</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        niv = kpis["net_incr_volume"]
        niv_pct = kpis["net_incr_pct"]
        color_niv = GRADE_COLORS["A"] if niv > 0 else GRADE_COLORS["C"]
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Net Incremental Volume</div>'
            f'<div class="kpi-value" style="color:{color_niv}">{niv:+,.0f} units</div>'
            f'<div class="kpi-sub">{niv_pct:+.1f}% vs. counterfactual baseline</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c3:
        sc = kpis["dollar_share_change_pp"]
        color_sc = GRADE_COLORS["A"] if sc > 0 else GRADE_COLORS["C"]
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Dollar Share Change</div>'
            f'<div class="kpi-value" style="color:{color_sc}">{sc:+.2f} pp</div>'
            f'<div class="kpi-sub">Promo period avg vs. pre-promo baseline (IRI)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # KPI Cards — Row 2
    c4, c5, c6 = st.columns(3)
    with c4:
        sq = kpis["sourcing_label"]
        tg = kpis["true_growth_pct"]
        tg_str = f"{tg:.0f}% true growth" if tg is not None else "LID unavailable"
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Sourcing Quality</div>'
            f'<div class="kpi-value" style="font-size:1.2rem">{sq}</div>'
            f'<div class="kpi-sub">{tg_str}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c5:
        pcm = fin["promo_cm"]
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Promo CM/unit</div>'
            f'<div class="kpi-value">${pcm:.2f}</div>'
            f'<div class="kpi-sub">{fin["promo_cm_pct"]:.1f}% — erodes ${fin["cm_erosion"]:.2f} vs. standard</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c6:
        delta = kpis["all_in_margin_delta"]
        color_delta = GRADE_COLORS["A"] if delta >= 0 else GRADE_COLORS["C"]
        sign = "+" if delta >= 0 else ""
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">All-In Event Margin Delta</div>'
            f'<div class="kpi-value" style="color:{color_delta}">{sign}${delta:,.0f}</div>'
            f'<div class="kpi-sub">Net Incremental CM vs. no-promo scenario</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Sub-scores breakdown
    st.markdown("#### Score Breakdown")
    sc_col1, sc_col2, sc_col3, sc_col4 = st.columns(4)
    score_data = [
        ("ROI", kpis["score_roi"], norm_weights["roi"]),
        ("Share", kpis["score_share"], norm_weights["share"]),
        ("Volume", kpis["score_volume"], norm_weights["volume"]),
        ("Inventory", kpis["score_inventory"], norm_weights["inventory"]),
    ]
    for col, (label, score, wt) in zip([sc_col1, sc_col2, sc_col3, sc_col4], score_data):
        with col:
            color = GRADE_COLORS["A"] if score >= 75 else (GRADE_COLORS["B"] if score >= 50 else GRADE_COLORS["C"])
            st.metric(
                label=f"{label} ({wt*100:.0f}%)",
                value=f"{score:.0f}/100",
            )

    st.divider()

    # Narrative — escape $ to prevent Streamlit/KaTeX treating them as LaTeX delimiters
    st.markdown("#### Analysis")
    st.markdown(narrative_text.replace("$", r"\$"))

    # LLM expander
    with st.expander("🤖 Generate AI Deep Dive"):
        if st.button("Generate AI Analysis"):
            with st.spinner("Calling Claude API..."):
                llm_text = generate_llm_narrative(kpis, fin, context, grade, composite_score)
            st.markdown(llm_text)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Price Ladders
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Price Ladders")
    fig_price_a, fig_price_b = chart_price_ladders(
        pos, iri, promoted_brand, promo_weeks, pre_weeks, color_map
    )
    st.plotly_chart(fig_price_a, use_container_width=True)
    st.plotly_chart(fig_price_b, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Market Share
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Market Share")
    share_type = st.radio("Share metric", ["Dollar Share", "Volume Share"], horizontal=True)
    share_col = "market_share_dollars" if share_type == "Dollar Share" else "market_share_units"
    fig_share_a, fig_share_b = chart_market_share(
        iri, promoted_brand, promo_weeks, pre_weeks, post_weeks, color_map, share_col=share_col
    )
    st.plotly_chart(fig_share_a, use_container_width=True)
    st.plotly_chart(fig_share_b, use_container_width=True)

    # Share retention metric
    sr = kpis["share_retention"]
    if sr is None:
        st.info("Share Retention: N/A — share change too small to measure retention.")
    else:
        color = GRADE_COLORS["A"] if sr >= 0.5 else GRADE_COLORS["C"]
        st.metric(
            "Share Retention",
            f"{sr*100:.1f}%",
            help="(Late-post avg share − baseline) / (promo avg − baseline). "
                 "Measures how much of the promo share gain held in the post-promo period.",
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: LID Sourcing
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Loyalty / Sourcing (LID)")

    with st.expander("What do these segments mean?", expanded=False):
        st.markdown("""
**Brand Loyalists** — Shoppers who purchased this brand in the prior 12 weeks.
Promo volume from loyalists typically represents pantry loading (buying earlier
or more than usual) rather than true market growth.

**Competitor Switchers** — Shoppers whose most recent category purchase was a
competing brand. This is the most valuable source of promo volume — it represents
genuine share capture.

**Category Expanders** — Shoppers with no category purchase in the prior 26 weeks
(new to category or lapsed buyers returning). This represents true demand creation
and category growth.
        """)

    if not kpis["has_lid"]:
        st.info("No loyalty sourcing data available for the promoted brand.")
    else:
        fig_lid_a, fig_lid_b = chart_lid_sourcing(pos, promoted_brand, promo_weeks, kpis)
        if fig_lid_a:
            st.plotly_chart(fig_lid_a, use_container_width=True, key="lid_stacked")

        # Metric cards row
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric("Sourcing Quality", kpis["sourcing_label"])
        with mc2:
            if kpis["true_growth_pct"] is not None:
                st.metric(
                    "True Growth %",
                    f"{kpis['true_growth_pct']:.0f}%",
                    help="Switcher % + Expander % — share of promo volume from genuine new demand",
                )
        with mc3:
            if kpis["avg_loyalist_pct"] is not None:
                st.metric(
                    "Pantry Loading Index",
                    f"{kpis['pantry_loading_index']*100:.0f}%",
                    help="Avg % of promo volume from existing brand loyalists",
                )

        if fig_lid_b:
            st.plotly_chart(fig_lid_b, use_container_width=True, key="lid_donut")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: Volume & Returns
# ─────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Volume & Returns")
    fig_vol_a, fig_vol_b = chart_volume_returns(
        pos, stars, promoted_brand, promo_weeks,
        kpis["baseline_weekly_units"], color_map
    )
    st.plotly_chart(fig_vol_a, use_container_width=True)
    st.plotly_chart(fig_vol_b, use_container_width=True)

    # Volume metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Gross Incremental Volume", f"{kpis['gross_incr_volume']:+,.0f} units")
    c2.metric(
        "Post-Promo Deficit",
        f"{kpis['post_promo_deficit']:,.0f} units"
        + (" *(incomplete)*" if kpis["post_promo_incomplete"] else ""),
        help=(
            "Volume lost in post-promo weeks when sales dip below baseline. "
            "Represents purchases pulled forward into the promo period — shoppers "
            "stocked up during the deal and bought less afterward. Subtracted from "
            "gross incremental to get net incremental volume."
        ),
    )
    c3.metric("Net Incremental Volume", f"{kpis['net_incr_volume']:+,.0f} units")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6: Margin Waterfall
# ─────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Margin Waterfall")
    fig_wf_a, fig_wf_b = chart_margin_waterfall(fin, kpis)
    st.plotly_chart(fig_wf_a, use_container_width=True)
    st.plotly_chart(fig_wf_b, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CM Erosion/unit", f"${fin['cm_erosion']:.2f}")
    if fin["breakeven_multiplier"]:
        c2.metric("Breakeven Multiplier", f"{fin['breakeven_multiplier']:.1f}×")
    else:
        c2.metric("Breakeven Multiplier", "N/A")
    c3.metric("Actual Multiplier", f"{kpis['actual_volume_multiplier']:.1f}×")
    delta = kpis["all_in_margin_delta"]
    sign = "+" if delta >= 0 else ""
    c4.metric("All-In Margin Delta", f"{sign}${delta:,.0f}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 7: Shipments vs. Pull
# ─────────────────────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("Shipments vs. Retail Pull")
    fig_ship_a, fig_ship_b, fig_ship_c = chart_shipments_vs_pull(
        pos, stars, promoted_brand, promo_weeks, color_map
    )
    st.plotly_chart(fig_ship_a, use_container_width=True)

    col_oh, col_cum = st.columns(2)
    with col_oh:
        st.plotly_chart(fig_ship_b, use_container_width=True)
    with col_cum:
        st.plotly_chart(fig_ship_c, use_container_width=True)

    # Traffic light inventory metrics
    risk = kpis["inventory_risk"]
    risk_class = {"Low": "traffic-light-low", "Moderate": "traffic-light-moderate", "High": "traffic-light-high"}
    c1, c2, c3 = st.columns(3)
    with c1:
        fill = kpis["pipeline_fill"]
        c1.metric("Pipeline Fill Ratio", f"{fill:.2f}×",
                  help="Total STAR units shipped / Total POS units sold")
    with c2:
        st.markdown(
            f'<div style="padding:14px 0">'
            f'<div class="kpi-label">Inventory Risk</div>'
            f'<div class="{risk_class.get(risk, "")}" style="font-size:1.3rem">{risk}</div>'
            f'<div class="kpi-sub">{kpis["inventory_explanation"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c3:
        rr = kpis["returns_rate"] * 100
        c3.metric("Returns Rate", f"{rr:.1f}%",
                  help="Total STAR returns / Total STAR shipped")

    if kpis["under_shipped"]:
        st.warning(
            f"Pipeline fill is {kpis['pipeline_fill']:.2f}× — **Under-shipped**. "
            "Possible stockout risk during promo period."
        )
