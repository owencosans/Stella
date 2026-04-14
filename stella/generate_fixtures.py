"""
generate_fixtures.py

Generates synthetic Excel test fixtures for the Stella post-promotion analysis app.
5-brand toothpaste market. 3 scenarios × 3 files = 9 Excel files total.
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Seed and constants
# ---------------------------------------------------------------------------
RNG = np.random.default_rng(42)

BASE_DIR = Path(r"C:\Stella\stella\test_fixtures")

SCENARIOS = ["strong_promo", "pantry_loaded", "inventory_risk"]

# Weeks 1-16; week endings are Saturdays starting 2025-01-04
WEEK_ENDINGS = pd.date_range(start="2025-01-04", periods=16, freq="7D")
WEEKS = list(range(1, 17))  # 1..16

PRE_WEEKS   = list(range(1, 5))   # 1-4
PROMO_WEEKS = list(range(5, 9))   # 5-8
POST_WEEKS  = list(range(9, 17))  # 9-16

PROMOTED_BRAND = "Summit Foods"
COMPETITORS    = ["PearlCare", "CleanPro", "DailyShine", "SmartChoice"]
ALL_BRANDS     = [PROMOTED_BRAND] + COMPETITORS

SKUS = {
    "Summit Foods": ["SF-Whitening 6oz", "SF-Sensitivity 4oz", "SF-Complete 6oz"],
    "PearlCare":    ["PC-Deep Clean 6oz", "PC-Gentle 4oz", "PC-Total 6oz"],
    "CleanPro":     ["CP-Fresh 6oz", "CP-Cavity Shield 4oz", "CP-Mint Blast 6oz"],
    "DailyShine":   ["DS-Original 6oz", "DS-Whitening 4oz", "DS-Cool Mint 6oz"],
    "SmartChoice":  ["SC-Basic Clean 6oz", "SC-Whitening 4oz", "SC-Fresh 6oz"],
}

BASE_PRICE = {
    "Summit Foods": 6.29,   # Premium
    "PearlCare":    6.49,   # Premium
    "CleanPro":     4.29,   # Mainstream
    "DailyShine":   4.09,   # Mainstream
    "SmartChoice":  2.79,   # Value/PL
}

# Baseline POS units/SKU/week
BASELINE_UNITS_PER_SKU = {
    "Summit Foods": 500,    # 3 SKUs × 500 = 1,500 units/wk
    "PearlCare":    450,    # 3 × 450 = 1,350
    "CleanPro":     700,    # 3 × 700 = 2,100
    "DailyShine":   650,    # 3 × 650 = 1,950
    "SmartChoice":  800,    # 3 × 800 = 2,400
}
# Total category ≈ 9,300 units/wk

IRI_MULT = 5.5  # IRI total market ≈ 5.5× this retailer

# Promo lift multipliers (promoted brand during promo weeks)
PROMO_LIFT = {
    "strong_promo":   2.4,
    "pantry_loaded":  2.2,
    "inventory_risk": 2.0,
}

# Competitor impact during promo (multiplier vs. baseline)
COMP_PROMO_MULT = {
    "strong_promo":   {"PearlCare": 0.88, "CleanPro": 0.95, "DailyShine": 0.96, "SmartChoice": 0.99},
    "pantry_loaded":  {"PearlCare": 0.95, "CleanPro": 0.98, "DailyShine": 0.98, "SmartChoice": 1.00},
    "inventory_risk": {"PearlCare": 0.90, "CleanPro": 0.96, "DailyShine": 0.97, "SmartChoice": 0.99},
}

# Post-promo recovery factors for promoted brand (W9=offset1 .. W16=offset8).
# Calibrated so that scenario ROI and volume score produce correct A/B/C grades:
#   strong_promo: mild dip, fast recovery → large net incr, high ROI (A)
#   pantry_loaded: moderate dip, slow recovery → pantry hangover but positive ROI (B)
#   inventory_risk: moderate POS dip (demand recovers OK), but BAD inventory → C via inv score=0
POST_FACTORS = {
    "strong_promo":   {1: 0.82, 2: 0.85, 3: 0.90, 4: 0.95, 5: 1.00, 6: 1.02, 7: 1.03, 8: 1.03},
    "pantry_loaded":  {1: 0.77, 2: 0.80, 3: 0.84, 4: 0.87, 5: 0.90, 6: 0.93, 7: 0.96, 8: 1.00},
    "inventory_risk": {1: 0.80, 2: 0.82, 3: 0.84, 4: 0.86, 5: 0.90, 6: 0.93, 7: 0.95, 8: 1.00},
}

# Competitor post-promo: strong_promo PearlCare loses some share permanently
COMP_POST_MULT = {
    "strong_promo":   {"PearlCare": {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.96, 6: 0.96, 7: 0.96, 8: 0.96},
                       "CleanPro":  {i: 1.0 for i in range(1, 9)},
                       "DailyShine":{i: 1.0 for i in range(1, 9)},
                       "SmartChoice":{i: 1.0 for i in range(1, 9)}},
    "pantry_loaded":  {b: {i: 1.0 for i in range(1, 9)} for b in COMPETITORS},
    "inventory_risk": {b: {i: 1.0 for i in range(1, 9)} for b in COMPETITORS},
}

# LID sourcing (promo weeks)
LID_PROMO = {
    "strong_promo":   (0.47, 0.33, 0.20),
    "pantry_loaded":  (0.65, 0.22, 0.13),
    "inventory_risk": (0.50, 0.30, 0.20),
}
LID_PRE = (0.70, 0.18, 0.12)
LID_POST = {
    "strong_promo":   (0.60, 0.25, 0.15),
    "pantry_loaded":  (0.75, 0.15, 0.10),
    "inventory_risk": (0.62, 0.23, 0.15),
}

# STARS shipment multipliers vs. baseline cases.
# Calibrated so:
#   - Pipeline fill lands in target range (strong ~1.05-1.08, pantry ~1.08-1.12, inventory ~1.22-1.28)
#   - Pre-load multiplier for strong_promo is modest (1.3×) so it doesn't inflate the
#     pre-period baseline_weekly_shipped, which would otherwise make W9-10 dips
#     look like a shipment collapse and incorrectly flag Moderate inventory risk.
STARS_MULT = {
    "strong_promo":   {1: 1.0, 2: 1.0, 3: 1.3, 4: 1.3, 5: 2.6, 6: 2.6, 7: 2.6, 8: 2.6,
                       9: 0.85, 10: 0.85, 11: 0.90, 12: 0.90, 13: 1.0, 14: 1.0, 15: 1.0, 16: 1.0},
    "pantry_loaded":  {1: 1.0, 2: 1.0, 3: 2.1, 4: 2.1, 5: 2.1, 6: 2.1, 7: 2.1, 8: 2.1,
                       9: 0.70, 10: 0.70, 11: 0.80, 12: 0.80, 13: 0.95, 14: 0.95, 15: 0.95, 16: 0.95},
    "inventory_risk": {1: 1.0, 2: 1.0, 3: 4.5, 4: 4.5, 5: 2.2, 6: 2.2, 7: 2.2, 8: 2.2,
                       9: 0.30, 10: 0.30, 11: 0.40, 12: 0.40, 13: 0.65, 14: 0.65, 15: 0.65, 16: 0.65},
}

# Returns rates
RETURNS_RATE = {
    "strong_promo":   0.015,
    "pantry_loaded":  0.020,
    "inventory_risk": 0.045,
}

UNITS_PER_CASE = 12
TPR_PER_UNIT = 1.25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def noise(shape, pct=0.04):
    """Multiplicative noise centred at 1.0 ± pct."""
    return 1.0 + RNG.uniform(-pct, pct, size=shape)


def week_to_date(w):
    return WEEK_ENDINGS[w - 1]


def normalize_lid(loyalist, switcher, expander):
    total = loyalist + switcher + expander
    l = round(loyalist / total, 4)
    s = round(switcher / total, 4)
    e = round(1.0 - l - s, 4)
    return l, s, e


# ---------------------------------------------------------------------------
# IRI data builder
# ---------------------------------------------------------------------------

def build_iri(scenario: str) -> pd.DataFrame:
    rows = []

    for w in WEEKS:
        date = week_to_date(w)
        phase = ("pre" if w in PRE_WEEKS else
                 "promo" if w in PROMO_WEEKS else "post")
        post_offset = w - 8 if phase == "post" else None

        # --- Determine per-SKU unit sales for each brand ---
        brand_sku_units = {}
        for brand in ALL_BRANDS:
            base = float(BASELINE_UNITS_PER_SKU[brand])
            for sku in SKUS[brand]:
                if phase == "pre":
                    mult = 1.0
                elif phase == "promo":
                    if brand == PROMOTED_BRAND:
                        mult = PROMO_LIFT[scenario]
                    else:
                        mult = COMP_PROMO_MULT[scenario][brand]
                else:  # post
                    if brand == PROMOTED_BRAND:
                        mult = POST_FACTORS[scenario][post_offset]
                    else:
                        mult = COMP_POST_MULT[scenario][brand][post_offset]

                units = base * mult * float(noise(1)[0])
                brand_sku_units[(brand, sku)] = units

        # Compute category totals
        cat_units = sum(brand_sku_units.values())

        # Compute market shares (IRI_MULT cancels in the ratio, so computed at retailer scale)
        sku_dollar = {}
        cat_dollars = 0.0
        for brand in ALL_BRANDS:
            price = BASE_PRICE[brand]
            if phase == "promo" and brand == PROMOTED_BRAND:
                price -= TPR_PER_UNIT
            for sku in SKUS[brand]:
                u = brand_sku_units[(brand, sku)]
                d = u * price
                sku_dollar[(brand, sku)] = d
                cat_dollars += d

        for brand in ALL_BRANDS:
            price = BASE_PRICE[brand]
            if phase == "promo" and brand == PROMOTED_BRAND:
                price -= TPR_PER_UNIT
            for sku in SKUS[brand]:
                units = brand_sku_units[(brand, sku)]
                d_sales = sku_dollar[(brand, sku)]
                ms_d = d_sales / cat_dollars if cat_dollars > 0 else 0.0
                ms_u = units / cat_units if cat_units > 0 else 0.0

                if brand == PROMOTED_BRAND and phase == "promo":
                    tdp = round(float(noise(1)[0]) * 85 + 5)
                else:
                    tdp = round(float(noise(1)[0]) * 60 + 30)
                tdp = max(1, min(100, tdp))

                any_promo = 1 if (brand == PROMOTED_BRAND and phase == "promo") else 0

                # Store dollar_sales and unit_sales at retailer scale (not IRI total market).
                # market_share_* are pre-computed correctly above; avg_net_price is stored
                # directly as price. The cross-source volume check in ingestion.py compares
                # IRI unit_sales to POS unit_sales, so both must be at the same scale.
                rows.append({
                    "week_ending":          date,
                    "brand":                brand,
                    "sku":                  sku,
                    "dollar_sales":         round(d_sales, 2),
                    "unit_sales":           round(units, 1),
                    "avg_net_price":        round(price, 2),
                    "market_share_dollars": round(ms_d, 4),
                    "market_share_units":   round(ms_u, 4),
                    "tdp":                  tdp,
                    "any_promo_flag":       any_promo,
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# POS data builder
# ---------------------------------------------------------------------------

def build_pos(scenario: str) -> pd.DataFrame:
    rows = []

    for w in WEEKS:
        date = week_to_date(w)
        phase = ("pre" if w in PRE_WEEKS else
                 "promo" if w in PROMO_WEEKS else "post")
        post_offset = w - 8 if phase == "post" else None

        for brand in ALL_BRANDS:
            base_units = float(BASELINE_UNITS_PER_SKU[brand])
            for sku in SKUS[brand]:
                price = BASE_PRICE[brand]

                if phase == "pre":
                    unit_mult = 1.0
                elif phase == "promo":
                    if brand == PROMOTED_BRAND:
                        unit_mult = PROMO_LIFT[scenario]
                        price -= TPR_PER_UNIT
                    else:
                        unit_mult = COMP_PROMO_MULT[scenario][brand]
                else:  # post
                    if brand == PROMOTED_BRAND:
                        unit_mult = POST_FACTORS[scenario][post_offset]
                    else:
                        unit_mult = COMP_POST_MULT[scenario][brand][post_offset]

                units = base_units * unit_mult * float(noise(1)[0])
                dollars = units * price

                scan_deal = TPR_PER_UNIT * units if (brand == PROMOTED_BRAND and phase == "promo") else 0.0

                # LID columns: only Summit Foods
                if brand == PROMOTED_BRAND:
                    if phase == "pre":
                        l, s, e = normalize_lid(*LID_PRE)
                    elif phase == "promo":
                        l, s, e = normalize_lid(*LID_PROMO[scenario])
                    else:
                        l, s, e = normalize_lid(*LID_POST[scenario])
                    loy_col = l
                    swi_col = s
                    exp_col = e
                else:
                    loy_col = None
                    swi_col = None
                    exp_col = None

                rows.append({
                    "week_ending":                    date,
                    "brand":                          brand,
                    "sku":                            sku,
                    "pos_dollar_sales":               round(dollars, 2),
                    "pos_unit_sales":                 round(units, 1),
                    "pos_price":                      round(price, 2),
                    "scan_deal_dollars":              round(scan_deal, 2),
                    "loyalty_pct_brand_loyalist":     loy_col,
                    "loyalty_pct_competitor_switch":  swi_col,
                    "loyalty_pct_category_expander":  exp_col,
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# STARS data builder (Summit Foods only)
# ---------------------------------------------------------------------------

def build_stars(scenario: str) -> pd.DataFrame:
    rows = []

    # Baseline cases shipped ≈ baseline POS units per SKU × 1.02 / units_per_case
    base_pos_per_sku = float(BASELINE_UNITS_PER_SKU[PROMOTED_BRAND])
    base_cases = (base_pos_per_sku * 1.02) / UNITS_PER_CASE
    ret_pct = RETURNS_RATE[scenario]

    # Per-SKU on-hand tracking
    sku_oh = {sku: base_pos_per_sku * 2.0 for sku in SKUS[PROMOTED_BRAND]}

    # Determine sell-through per SKU per week (consistent with POS)
    for w in WEEKS:
        date = week_to_date(w)
        phase = ("pre" if w in PRE_WEEKS else
                 "promo" if w in PROMO_WEEKS else "post")
        post_offset = w - 8 if phase == "post" else None

        if phase == "pre":
            pos_mult = 1.0
        elif phase == "promo":
            pos_mult = PROMO_LIFT[scenario]
        else:
            pos_mult = POST_FACTORS[scenario][post_offset]

        cases_mult = STARS_MULT[scenario][w]

        for sku in SKUS[PROMOTED_BRAND]:
            pos_units = base_pos_per_sku * pos_mult * float(noise(1)[0])
            cases_shipped = max(0.0, base_cases * cases_mult * float(noise(1)[0]))
            units_shipped = cases_shipped * UNITS_PER_CASE
            returns_units = units_shipped * ret_pct * float(noise(1, pct=0.02)[0])

            # Accumulate on-hand: prior + shipped - sold - returns
            sku_oh[sku] = max(100.0, sku_oh[sku] + units_shipped - pos_units - returns_units)

            rows.append({
                "week_ending":               date,
                "brand":                     PROMOTED_BRAND,
                "sku":                       sku,
                "cases_shipped":             round(cases_shipped, 2),
                "units_per_case":            UNITS_PER_CASE,
                "units_shipped":             round(units_shipped, 2),
                "returns_units":             round(returns_units, 2),
                "estimated_retail_on_hand":  round(sku_oh[sku], 1),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_excel(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl", date_format="YYYY-MM-DD",
                        datetime_format="YYYY-MM-DD") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    print(f"  Written: {path}")


# ---------------------------------------------------------------------------
# Pipeline fill diagnostic
# ---------------------------------------------------------------------------

def check_pipeline_fill(stars: pd.DataFrame, pos: pd.DataFrame, scenario: str):
    total_shipped = stars["units_shipped"].sum()
    total_sold = pos[pos["brand"] == PROMOTED_BRAND]["pos_unit_sales"].sum()
    fill = total_shipped / total_sold if total_sold > 0 else 0.0
    print(f"  Pipeline fill ({scenario}): {fill:.3f}×  "
          f"[target: strong~1.06, pantry~1.10, inventory~1.24]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    for scenario in SCENARIOS:
        print(f"\n=== Scenario: {scenario} ===")
        out_dir = BASE_DIR / scenario

        iri   = build_iri(scenario)
        pos   = build_pos(scenario)
        stars = build_stars(scenario)

        check_pipeline_fill(stars, pos, scenario)

        write_excel(iri,   out_dir / "iri_data.xlsx")
        write_excel(pos,   out_dir / "pos_data.xlsx")
        write_excel(stars, out_dir / "stars_data.xlsx")

    print("\nAll fixtures generated successfully.")


if __name__ == "__main__":
    main()
