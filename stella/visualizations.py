"""
visualizations.py — All Plotly chart builders for Stella's 7 tabs.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from config import BRAND_COLORS, GRADE_COLORS, GRADE_BG_COLORS


# ─── Color Helpers ─────────────────────────────────────────────────────────────

def assign_brand_colors(all_brands: list, promoted_brand: str) -> dict:
    """Promoted brand = blue. Others assigned in order."""
    color_map = {promoted_brand: BRAND_COLORS[0]}
    others = [b for b in all_brands if b != promoted_brand]
    for i, brand in enumerate(others):
        color_map[brand] = BRAND_COLORS[1 + (i % (len(BRAND_COLORS) - 1))]
    return color_map


def period_shapes(promo_weeks, color="rgba(255,235,59,0.15)"):
    """Return plotly shape dict to shade the promo period."""
    if not promo_weeks:
        return []
    return [
        dict(
            type="rect",
            xref="x",
            yref="paper",
            x0=promo_weeks[0] - pd.Timedelta(days=3),
            x1=promo_weeks[-1] + pd.Timedelta(days=3),
            y0=0,
            y1=1,
            fillcolor=color,
            opacity=1,
            layer="below",
            line_width=0,
        )
    ]


LAYOUT_DEFAULTS = dict(
    template="plotly_white",
    font=dict(family="Inter, sans-serif", size=12),
    margin=dict(l=50, r=20, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


# ─── Tab 2: Price Ladders ──────────────────────────────────────────────────────

def chart_price_ladders(
    pos: pd.DataFrame,
    iri: pd.DataFrame,
    promoted_brand: str,
    promo_weeks: list,
    pre_weeks: list,
    color_map: dict,
) -> tuple:
    """Returns (fig_grouped_bar, fig_line)."""

    # Chart A: Pre vs. Promo avg price per brand/SKU
    all_weeks_set = set(promo_weeks) | set(pre_weeks)
    pos_sub = pos[pos["week_ending"].isin(all_weeks_set)].copy()

    pre_avg = (
        pos[pos["week_ending"].isin(pre_weeks)]
        .groupby(["brand", "sku"])["pos_price"]
        .mean()
        .reset_index()
        .rename(columns={"pos_price": "Pre-Promo Avg"})
    )
    promo_avg = (
        pos[pos["week_ending"].isin(promo_weeks)]
        .groupby(["brand", "sku"])["pos_price"]
        .mean()
        .reset_index()
        .rename(columns={"pos_price": "Promo-Period Avg"})
    )
    merged = pre_avg.merge(promo_avg, on=["brand", "sku"], how="outer")
    merged["label"] = merged["brand"] + " — " + merged["sku"]

    fig_a = go.Figure()
    for period, col in [("Pre-Promo Avg", "Pre-Promo Avg"), ("Promo-Period Avg", "Promo-Period Avg")]:
        colors = [
            color_map.get(b, BRAND_COLORS[0]) if period == "Pre-Promo Avg"
            else (color_map.get(b, BRAND_COLORS[0]) if b != promoted_brand else "#FF6B6B")
            for b in merged["brand"]
        ]
        fig_a.add_trace(go.Bar(
            name=period,
            x=merged["label"],
            y=merged[col],
            marker_color=(
                [color_map.get(b, BRAND_COLORS[1]) for b in merged["brand"]]
                if period == "Pre-Promo Avg"
                else ["#FF7043" if b == promoted_brand else color_map.get(b, BRAND_COLORS[1])
                      for b in merged["brand"]]
            ),
            opacity=0.9 if period == "Pre-Promo Avg" else 1.0,
        ))
    fig_a.update_layout(
        barmode="group",
        title="Pre-Promo vs. Promo Period Avg Price by Brand/SKU",
        yaxis_title="Price ($/unit)",
        xaxis_title="",
        **LAYOUT_DEFAULTS,
    )

    # Chart B: Line chart — avg net price by brand over time (IRI)
    iri_price = iri.groupby(["week_ending", "brand"])["avg_net_price"].mean().reset_index()
    fig_b = go.Figure()
    for brand in iri_price["brand"].unique():
        brand_data = iri_price[iri_price["brand"] == brand].sort_values("week_ending")
        fig_b.add_trace(go.Scatter(
            x=brand_data["week_ending"],
            y=brand_data["avg_net_price"],
            mode="lines+markers",
            name=brand,
            line=dict(color=color_map.get(brand, BRAND_COLORS[1]), width=2.5 if brand == promoted_brand else 1.5),
            marker=dict(size=5 if brand == promoted_brand else 3),
        ))
    fig_b.update_layout(
        shapes=period_shapes(promo_weeks),
        title="Avg Net Price by Brand (IRI) — Weekly",
        yaxis_title="Avg Net Price ($/unit)",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )
    return fig_a, fig_b


# ─── Tab 3: Market Share ───────────────────────────────────────────────────────

def chart_market_share(
    iri: pd.DataFrame,
    promoted_brand: str,
    promo_weeks: list,
    pre_weeks: list,
    post_weeks: list,
    color_map: dict,
    share_col: str = "market_share_dollars",
) -> tuple:
    """Returns (fig_stacked_area, fig_share_change). share_col: 'market_share_dollars' or 'market_share_units'."""

    share_label = "Dollar Share (%)" if share_col == "market_share_dollars" else "Volume Share (%)"
    share_title_prefix = "Dollar" if share_col == "market_share_dollars" else "Volume"

    weekly_share = iri.groupby(["week_ending", "brand"])[share_col].sum().reset_index()

    # Chart A: Stacked area
    fig_a = go.Figure()
    brands_ordered = [promoted_brand] + [b for b in iri["brand"].unique() if b != promoted_brand]
    for brand in brands_ordered:
        bdata = weekly_share[weekly_share["brand"] == brand].sort_values("week_ending")
        fig_a.add_trace(go.Scatter(
            x=bdata["week_ending"],
            y=bdata[share_col] * 100,
            name=brand,
            mode="lines",
            stackgroup="one",
            line=dict(color=color_map.get(brand, BRAND_COLORS[1])),
            fillcolor=color_map.get(brand, BRAND_COLORS[1]),
        ))
    fig_a.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{share_title_prefix} Share by Brand — Weekly (IRI)",
        yaxis_title=share_label,
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )

    # Chart B: Share change bar
    pre_share = (
        iri[iri["week_ending"].isin(pre_weeks)]
        .groupby("brand")[share_col].mean()
    )
    promo_share = (
        iri[iri["week_ending"].isin(promo_weeks)]
        .groupby("brand")[share_col].mean()
    )
    share_chg = ((promo_share - pre_share) * 100).reset_index()
    share_chg.columns = ["brand", "share_change_pp"]
    share_chg["color"] = share_chg["brand"].map(
        lambda b: color_map.get(b, BRAND_COLORS[1])
    )

    fig_b = go.Figure(go.Bar(
        x=share_chg["brand"],
        y=share_chg["share_change_pp"],
        marker_color=share_chg["color"],
        text=share_chg["share_change_pp"].apply(lambda x: f"{x:+.2f} pp"),
        textposition="outside",
    ))
    fig_b.update_layout(
        title=f"{share_title_prefix} Share Change: Promo Period vs. Pre-Promo Baseline",
        yaxis_title="Share Change (pp)",
        xaxis_title="Brand",
        **LAYOUT_DEFAULTS,
    )
    return fig_a, fig_b


# ─── Tab 4: LID Sourcing ──────────────────────────────────────────────────────

def chart_lid_sourcing(
    pos: pd.DataFrame,
    promoted_brand: str,
    promo_weeks: list,
    kpis: dict,
) -> tuple:
    """Returns (fig_stacked_bar, fig_donut). Both None if no LID data."""
    lid_cols = [
        "loyalty_pct_brand_loyalist",
        "loyalty_pct_competitor_switch",
        "loyalty_pct_category_expander",
    ]
    pb = pos[pos["brand"] == promoted_brand].copy()
    has_lid = all(c in pb.columns for c in lid_cols) and not pb[lid_cols].isna().all().all()

    if not has_lid:
        return None, None

    pb_lid = pb.dropna(subset=lid_cols).copy()
    if pb_lid.empty:
        return None, None

    weekly = pb_lid.groupby("week_ending")[lid_cols].mean().reset_index()
    weekly.columns = ["week_ending", "Loyalists", "Switchers", "Expanders"]

    # Chart A: Stacked bar
    fig_a = go.Figure()
    colors = {"Loyalists": "#E53935", "Switchers": "#43A047", "Expanders": "#1E88E5"}
    for seg in ["Loyalists", "Switchers", "Expanders"]:
        fig_a.add_trace(go.Bar(
            name=seg,
            x=weekly["week_ending"],
            y=weekly[seg] * 100,
            marker_color=colors[seg],
        ))
    fig_a.update_layout(
        barmode="stack",
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — LID Sourcing Mix by Week",
        yaxis_title="% of Volume",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )

    # Chart B: Donut (promo period only)
    promo_pb = pb_lid[pb_lid["week_ending"].isin(promo_weeks)]
    if promo_pb.empty:
        fig_b = None
    else:
        avg_loy = kpis.get("avg_loyalist_pct", 0) or 0
        avg_sw = kpis.get("avg_switcher_pct", 0) or 0
        avg_ex = kpis.get("avg_expander_pct", 0) or 0

        fig_b = go.Figure(go.Pie(
            labels=["Loyalists", "Switchers", "Expanders"],
            values=[avg_loy * 100, avg_sw * 100, avg_ex * 100],
            hole=0.5,
            marker_colors=[colors["Loyalists"], colors["Switchers"], colors["Expanders"]],
            textinfo="label+percent",
        ))
        fig_b.update_layout(
            title=f"{promoted_brand} — Promo Period Sourcing Split",
            **LAYOUT_DEFAULTS,
        )

    return fig_a, fig_b


# ─── Tab 5: Volume & Returns ──────────────────────────────────────────────────

def chart_volume_returns(
    pos: pd.DataFrame,
    stars: pd.DataFrame,
    promoted_brand: str,
    promo_weeks: list,
    baseline_weekly_units: float,
    color_map: dict,
) -> tuple:
    """Returns (fig_dual_axis, fig_incremental)."""

    pb_pos = pos[pos["brand"] == promoted_brand].groupby("week_ending")["pos_unit_sales"].sum().reset_index()
    pb_pos = pb_pos.sort_values("week_ending")

    pb_stars = stars[stars["brand"] == promoted_brand].groupby("week_ending")["returns_units"].sum().reset_index()

    # Chart A: Dual-axis
    fig_a = make_subplots(specs=[[{"secondary_y": True}]])
    fig_a.add_trace(
        go.Scatter(
            x=pb_pos["week_ending"],
            y=pb_pos["pos_unit_sales"],
            name="POS Units Sold",
            line=dict(color=BRAND_COLORS[0], width=2.5),
            mode="lines+markers",
        ),
        secondary_y=False,
    )
    fig_a.add_trace(
        go.Scatter(
            x=pb_pos["week_ending"],
            y=[baseline_weekly_units] * len(pb_pos),
            name="Baseline (Counterfactual)",
            line=dict(color="gray", width=1.5, dash="dash"),
            mode="lines",
        ),
        secondary_y=False,
    )
    fig_a.add_trace(
        go.Bar(
            x=pb_stars["week_ending"],
            y=pb_stars["returns_units"],
            name="STARS Returns",
            marker_color="rgba(229,57,53,0.5)",
        ),
        secondary_y=True,
    )
    fig_a.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — POS Volume vs. STARS Returns",
        **LAYOUT_DEFAULTS,
    )
    fig_a.update_yaxes(title_text="Units Sold (POS)", secondary_y=False)
    fig_a.update_yaxes(title_text="Returns (STARS)", secondary_y=True)

    # Chart B: Weekly incremental vs baseline
    merged = pb_pos.copy()
    merged["incremental"] = merged["pos_unit_sales"] - baseline_weekly_units
    merged["color"] = merged["incremental"].apply(
        lambda x: BRAND_COLORS[0] if x >= 0 else "#C62828"
    )

    fig_b = go.Figure(go.Bar(
        x=merged["week_ending"],
        y=merged["incremental"],
        marker_color=merged["color"],
        name="Incremental vs. Baseline",
    ))
    fig_b.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_b.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — Weekly Volume vs. Baseline",
        yaxis_title="Units Above/Below Baseline",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )
    return fig_a, fig_b


# ─── Tab 6: Margin Waterfall ──────────────────────────────────────────────────

def chart_margin_waterfall(
    financials: dict,
    kpis: dict,
) -> tuple:
    """Returns (fig_waterfall, fig_total_cm)."""

    f = financials

    # Chart A: Per-unit waterfall (two side by side)
    fig_a = make_subplots(rows=1, cols=2, subplot_titles=["Standard (No TPR)", "With TPR"])

    def waterfall_trace(tpr_included: bool):
        steps = [
            ("List Price", f["list_price"], "absolute"),
            ("− COGS", -f["cogs"], "relative"),
            ("Gross Margin", None, "total"),
            ("− Standard Trade", -f["standard_trade_dollar"], "relative"),
            ("Standard CM", None, "total"),
        ]
        if tpr_included:
            steps += [
                ("− TPR", -f["tpr_per_unit"], "relative"),
                ("Promo CM", None, "total"),
            ]
        else:
            steps += [
                ("− TPR", 0, "relative"),
                ("Contribution Margin", None, "total"),
            ]
        labels = [s[0] for s in steps]
        vals = []
        for label, val, measure in steps:
            if measure == "absolute":
                vals.append(val)
            elif measure == "relative":
                vals.append(val)
            else:
                vals.append(0)  # totals handled by plotly

        measures = [s[2] for s in steps]
        y_vals = [s[1] if s[1] is not None else 0 for s in steps]

        return go.Waterfall(
            orientation="v",
            measure=measures,
            x=labels,
            y=y_vals,
            connector=dict(line=dict(color="rgb(63, 63, 63)")),
            increasing=dict(marker_color="#43A047"),
            decreasing=dict(marker_color="#C62828"),
            totals=dict(marker_color="#1E88E5"),
            texttemplate="%{y:.2f}",
            textposition="outside",
        )

    fig_a.add_trace(waterfall_trace(False), row=1, col=1)
    fig_a.add_trace(waterfall_trace(True), row=1, col=2)
    fig_a.update_layout(
        title="Per-Unit Margin Waterfall",
        yaxis_title="$/unit",
        showlegend=False,
        **LAYOUT_DEFAULTS,
    )

    # Chart B: Total CM comparison
    baseline_cm = kpis["baseline_equiv_cm"]
    promo_cm_total = kpis["promo_period_total_cm"] - kpis["post_promo_cm_loss"]
    delta = kpis["all_in_margin_delta"]

    fig_b = go.Figure()
    fig_b.add_trace(go.Bar(
        x=["Baseline Scenario", "Promo Scenario\n(incl. post-promo)"],
        y=[baseline_cm, promo_cm_total],
        marker_color=["gray", BRAND_COLORS[0] if delta >= 0 else "#C62828"],
        text=[f"${baseline_cm:,.0f}", f"${promo_cm_total:,.0f}"],
        textposition="outside",
    ))
    sign = "+" if delta >= 0 else ""
    fig_b.add_annotation(
        x=1, y=max(baseline_cm, promo_cm_total) * 1.1,
        text=f"Delta: {sign}${delta:,.0f}",
        showarrow=False,
        font=dict(size=13, color=BRAND_COLORS[0] if delta >= 0 else "#C62828"),
    )
    fig_b.update_layout(
        title="Total Contribution Margin: Baseline vs. Promo Scenario",
        yaxis_title="Total CM ($)",
        **LAYOUT_DEFAULTS,
    )
    return fig_a, fig_b


# ─── Tab 7: Shipments vs. Retail Pull ─────────────────────────────────────────

def chart_shipments_vs_pull(
    pos: pd.DataFrame,
    stars: pd.DataFrame,
    promoted_brand: str,
    promo_weeks: list,
    color_map: dict,
) -> tuple:
    """Returns (fig_dual_line, fig_onhand, fig_cumulative)."""

    pb_pos = pos[pos["brand"] == promoted_brand].groupby("week_ending")["pos_unit_sales"].sum().reset_index()
    pb_pos = pb_pos.sort_values("week_ending")

    pb_stars = stars[stars["brand"] == promoted_brand].groupby("week_ending").agg(
        units_shipped=("units_shipped", "sum"),
        estimated_retail_on_hand=("estimated_retail_on_hand", "sum"),
    ).reset_index().sort_values("week_ending")

    merged = pb_pos.merge(pb_stars, on="week_ending", how="outer").fillna(0).sort_values("week_ending")
    merged["inv_delta"] = merged["units_shipped"] - merged["pos_unit_sales"]

    # Chart A: Dual line + shaded area
    fig_a = go.Figure()
    fig_a.add_trace(go.Scatter(
        x=merged["week_ending"],
        y=merged["units_shipped"],
        name="STARS Units Shipped",
        line=dict(color="#FB8C00", width=2.5),
        mode="lines+markers",
    ))
    fig_a.add_trace(go.Scatter(
        x=merged["week_ending"],
        y=merged["pos_unit_sales"],
        name="POS Units Sold",
        line=dict(color=BRAND_COLORS[0], width=2.5),
        mode="lines+markers",
        fill=None,
    ))
    # Shaded inventory delta
    fig_a.add_trace(go.Scatter(
        x=pd.concat([merged["week_ending"], merged["week_ending"][::-1]]),
        y=pd.concat([merged["units_shipped"], merged["pos_unit_sales"][::-1]]),
        fill="toself",
        fillcolor="rgba(251,140,0,0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Inventory Delta",
        showlegend=True,
    ))
    fig_a.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — STARS Shipments vs. POS Pull-Through",
        yaxis_title="Units",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )

    # Chart B: Estimated retail on-hand
    fig_b = go.Figure(go.Scatter(
        x=pb_stars["week_ending"],
        y=pb_stars["estimated_retail_on_hand"],
        name="Est. Retail On-Hand",
        line=dict(color="#8E24AA", width=2.5),
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(142,36,170,0.1)",
    ))
    fig_b.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — Estimated Retail On-Hand (STARS)",
        yaxis_title="Units",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )

    # Chart C: Cumulative shipped vs. sold
    merged["cumul_shipped"] = merged["units_shipped"].cumsum()
    merged["cumul_sold"] = merged["pos_unit_sales"].cumsum()

    fig_c = go.Figure()
    fig_c.add_trace(go.Scatter(
        x=merged["week_ending"],
        y=merged["cumul_shipped"],
        name="Cumulative Shipped",
        line=dict(color="#FB8C00", width=2),
    ))
    fig_c.add_trace(go.Scatter(
        x=merged["week_ending"],
        y=merged["cumul_sold"],
        name="Cumulative Sold",
        line=dict(color=BRAND_COLORS[0], width=2),
    ))
    # Annotate final gap
    if not merged.empty:
        final_gap = merged["cumul_shipped"].iloc[-1] - merged["cumul_sold"].iloc[-1]
        fig_c.add_annotation(
            x=merged["week_ending"].iloc[-1],
            y=merged["cumul_shipped"].iloc[-1],
            text=f"Pipeline surplus: {final_gap:,.0f} units",
            showarrow=True, arrowhead=2,
            font=dict(size=11),
        )
    fig_c.update_layout(
        shapes=period_shapes(promo_weeks),
        title=f"{promoted_brand} — Cumulative Shipped vs. Sold",
        yaxis_title="Units (Cumulative)",
        xaxis_title="Week Ending",
        **LAYOUT_DEFAULTS,
    )
    return fig_a, fig_b, fig_c
