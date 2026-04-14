"""
generate_fixtures.py

Generates synthetic Excel test fixtures for the Stella post-promotion analysis app.
Produces 3 scenario folders × 3 files = 9 Excel files total.
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
COMPETITORS    = ["RiverBrand", "CrestLine"]
ALL_BRANDS     = [PROMOTED_BRAND] + COMPETITORS

SKUS = {
    "Summit Foods": ["SF-Original 12ct", "SF-Variety 12ct"],
    "RiverBrand":   ["RB-Classic 12ct"],
    "CrestLine":    ["CL-Premium 12ct"],
}

# Baseline prices
BASE_PRICE = {
    "Summit Foods": 6.25,
    "RiverBrand":   6.00,
    "CrestLine":    6.50,
}

# IRI market multiplier (~6× retailer)
IRI_MULT = 6.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def noise(shape, pct=0.04):
    """Return multiplicative noise array centred at 1.0 ± pct."""
    return 1.0 + RNG.uniform(-pct, pct, size=shape)


def week_to_date(w):
    return WEEK_ENDINGS[w - 1]


# ---------------------------------------------------------------------------
# IRI data builder
# ---------------------------------------------------------------------------

def build_iri(scenario: str) -> pd.DataFrame:
    """Build IRI rows for all brands, all SKUs, all 16 weeks."""
    rows = []

    for w in WEEKS:
        date = week_to_date(w)
        phase = ("pre" if w in PRE_WEEKS else
                 "promo" if w in PROMO_WEEKS else "post")

        # --- Determine per-SKU unit sales for each brand ---
        brand_units = {}  # brand -> {sku: units}

        for brand in ALL_BRANDS:
            brand_units[brand] = {}
            for sku in SKUS[brand]:
                # Baseline: Summit ~400/SKU/week, RiverBrand ~450, CrestLine ~350
                if brand == "Summit Foods":
                    base = 400.0
                elif brand == "RiverBrand":
                    base = 450.0
                else:
                    base = 350.0

                if phase == "pre":
                    mult = 1.0

                elif phase == "promo":
                    if brand == "Summit Foods":
                        if scenario == "strong_promo":
                            mult = 2.4
                        elif scenario == "pantry_loaded":
                            mult = 2.2
                        else:  # inventory_risk
                            mult = 2.0
                    elif brand == "RiverBrand":
                        if scenario == "strong_promo":
                            mult = 0.88
                        elif scenario == "pantry_loaded":
                            mult = 0.98
                        else:
                            mult = 0.95
                    else:  # CrestLine
                        if scenario == "strong_promo":
                            mult = 0.94
                        elif scenario == "pantry_loaded":
                            mult = 0.98
                        else:
                            mult = 0.95

                else:  # post
                    if brand == "Summit Foods":
                        post_offset = w - 8  # 1..8
                        if scenario == "strong_promo":
                            # Early post: typical pantry payback dip.
                            # Late post: slightly above baseline — switchers who stayed loyal.
                            factors = {1: 0.85, 2: 0.85, 3: 0.90, 4: 0.95,
                                       5: 1.05, 6: 1.05, 7: 1.05, 8: 1.05}
                        elif scenario == "pantry_loaded":
                            factors = {1: 0.68, 2: 0.68, 3: 0.68, 4: 0.68,
                                       5: 0.80, 6: 0.80, 7: 0.90, 8: 0.90}
                        else:  # inventory_risk
                            factors = {1: 0.80, 2: 0.80, 3: 0.80, 4: 0.80,
                                       5: 0.80, 6: 0.80, 7: 0.80, 8: 0.80}
                        mult = factors[post_offset]
                    else:
                        # Competitors: for strong_promo, some buyers permanently switched
                        # to Summit in late post — show modest persistent share loss.
                        if scenario == "strong_promo":
                            post_offset = w - 8
                            comp_mult = 0.94 if post_offset >= 5 else 1.0
                        else:
                            comp_mult = 1.0
                        mult = comp_mult

                units = base * mult * float(noise(1)[0])
                brand_units[brand][sku] = units

        # Compute category total for market share
        cat_units  = sum(u for bskus in brand_units.values() for u in bskus.values())
        # Dollar totals per sku
        cat_dollars = 0.0
        sku_dollars = {}
        for brand in ALL_BRANDS:
            for sku in SKUS[brand]:
                price = BASE_PRICE[brand]
                if phase == "promo" and brand == "Summit Foods":
                    price -= 1.25
                d = brand_units[brand][sku] * price * IRI_MULT
                sku_dollars[(brand, sku)] = d
                cat_dollars += d

        for brand in ALL_BRANDS:
            for sku in SKUS[brand]:
                price = BASE_PRICE[brand]
                if phase == "promo" and brand == "Summit Foods":
                    price -= 1.25

                units  = brand_units[brand][sku]
                d_sales = sku_dollars[(brand, sku)]
                ms_d    = d_sales / cat_dollars if cat_dollars > 0 else 0.0
                ms_u    = units / cat_units if cat_units > 0 else 0.0

                # TDP: Summit goes up during promo
                if brand == "Summit Foods" and phase == "promo":
                    tdp = round(float(noise(1)[0]) * 85 + 5)
                else:
                    tdp = round(float(noise(1)[0]) * 60 + 30)
                tdp = max(1, min(100, tdp))

                any_promo = 1 if (brand == "Summit Foods" and phase == "promo") else 0

                rows.append({
                    "week_ending":           date,
                    "brand":                 brand,
                    "sku":                   sku,
                    "dollar_sales":          round(d_sales, 2),
                    "unit_sales":            round(units, 1),
                    "avg_net_price":         round(price, 2),
                    "market_share_dollars":  round(ms_d, 4),
                    "market_share_units":    round(ms_u, 4),
                    "tdp":                   tdp,
                    "any_promo_flag":        any_promo,
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

        for brand in ALL_BRANDS:
            for sku in SKUS[brand]:
                # Baseline
                if brand == "Summit Foods":
                    base_units = 400.0
                elif brand == "RiverBrand":
                    base_units = 450.0
                else:
                    base_units = 350.0

                price = BASE_PRICE[brand]

                if phase == "pre":
                    unit_mult = 1.0
                elif phase == "promo":
                    if brand == "Summit Foods":
                        unit_mult = (2.4 if scenario == "strong_promo" else
                                     2.2 if scenario == "pantry_loaded" else 2.0)
                        price -= 1.25
                    elif brand == "RiverBrand":
                        unit_mult = (0.88 if scenario == "strong_promo" else
                                     0.98 if scenario == "pantry_loaded" else 0.95)
                    else:
                        unit_mult = (0.94 if scenario == "strong_promo" else
                                     0.98 if scenario == "pantry_loaded" else 0.95)
                else:  # post
                    if brand == "Summit Foods":
                        post_offset = w - 8
                        if scenario == "strong_promo":
                            # Late post above baseline: retained switchers buy again.
                            factors = {1: 0.85, 2: 0.85, 3: 0.90, 4: 0.95,
                                       5: 1.05, 6: 1.05, 7: 1.05, 8: 1.05}
                        elif scenario == "pantry_loaded":
                            factors = {1: 0.68, 2: 0.68, 3: 0.68, 4: 0.68,
                                       5: 0.80, 6: 0.80, 7: 0.90, 8: 0.90}
                        else:
                            factors = {1: 0.80, 2: 0.80, 3: 0.80, 4: 0.80,
                                       5: 0.80, 6: 0.80, 7: 0.80, 8: 0.80}
                        unit_mult = factors[post_offset]
                    else:
                        unit_mult = 1.0

                units = base_units * unit_mult * float(noise(1)[0])
                dollars = units * price

                # scan_deal_dollars: only SF during promo
                if brand == "Summit Foods" and phase == "promo":
                    scan_deal = 1.25 * units
                else:
                    scan_deal = 0.0

                # loyalty columns: only Summit Foods
                if brand == "Summit Foods":
                    post_offset = w - 8 if phase == "post" else None
                    if phase == "pre":
                        loyalist, switcher, expander = 0.55, 0.28, 0.17
                    elif phase == "promo":
                        if scenario == "strong_promo":
                            loyalist, switcher, expander = 0.47, 0.33, 0.20
                        elif scenario == "pantry_loaded":
                            loyalist, switcher, expander = 0.65, 0.22, 0.13
                        else:
                            loyalist, switcher, expander = 0.50, 0.30, 0.20
                    else:  # post
                        if scenario == "strong_promo":
                            loyalist, switcher, expander = 0.55, 0.28, 0.17
                        elif scenario == "pantry_loaded":
                            # slowly recovers
                            if post_offset <= 4:
                                loyalist, switcher, expander = 0.60, 0.24, 0.16
                            else:
                                loyalist, switcher, expander = 0.58, 0.25, 0.17
                        else:
                            loyalist, switcher, expander = 0.55, 0.28, 0.17
                    # Normalise to exactly 1.0
                    total = loyalist + switcher + expander
                    loyalist /= total
                    switcher /= total
                    expander /= total
                    loy_col = round(loyalist, 4)
                    swi_col = round(switcher, 4)
                    exp_col = round(1.0 - loy_col - swi_col, 4)  # ensure sum = 1
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
# STAR data builder  (Summit Foods only)
# ---------------------------------------------------------------------------

def build_stars(scenario: str) -> pd.DataFrame:
    rows = []
    UNITS_PER_CASE = 12

    # Baseline POS units/week per SKU for Summit Foods
    base_pos = 400.0
    # baseline cases shipped ~ (base_pos * 1.02) / 12
    base_cases = (base_pos * 1.02) / UNITS_PER_CASE

    # Running retail on-hand (carry across weeks)
    retail_oh = 2000.0

    for w in WEEKS:
        date = week_to_date(w)
        phase = ("pre" if w in PRE_WEEKS else
                 "promo" if w in PROMO_WEEKS else "post")

        for sku in SKUS["Summit Foods"]:
            # ----- POS sell-through this week -----
            if phase == "pre":
                pos_mult = 1.0
            elif phase == "promo":
                pos_mult = (2.4 if scenario == "strong_promo" else
                            2.2 if scenario == "pantry_loaded" else 2.0)
            else:
                post_offset = w - 8
                if scenario == "strong_promo":
                    fm = {1: 0.85, 2: 0.85, 3: 0.90, 4: 0.95,
                          5: 1.05, 6: 1.05, 7: 1.05, 8: 1.05}
                elif scenario == "pantry_loaded":
                    fm = {1: 0.68, 2: 0.68, 3: 0.68, 4: 0.68,
                          5: 0.80, 6: 0.80, 7: 0.90, 8: 0.90}
                else:
                    fm = {1: 0.80, 2: 0.80, 3: 0.80, 4: 0.80,
                          5: 0.80, 6: 0.80, 7: 0.80, 8: 0.80}
                pos_mult = fm[post_offset]

            pos_units = base_pos * pos_mult * float(noise(1)[0])

            # ----- Cases shipped -----
            if scenario == "strong_promo":
                if w in [1, 2]:
                    cases_mult = 1.02
                elif w in [3, 4]:   # pre-load
                    cases_mult = 1.8
                elif phase == "promo":
                    cases_mult = 1.1
                elif phase == "post":
                    cases_mult = 1.0
                else:
                    cases_mult = 1.02

            elif scenario == "pantry_loaded":
                if w in [1, 2]:
                    cases_mult = 1.02
                elif w in [3, 4]:
                    cases_mult = 1.09
                elif phase == "promo":
                    cases_mult = 1.05
                elif phase == "post":
                    post_offset = w - 8
                    if post_offset <= 3:
                        cases_mult = 0.75
                    else:
                        cases_mult = 0.95
                else:
                    cases_mult = 1.02

            else:  # inventory_risk
                if w in [1, 2]:
                    cases_mult = 1.02
                elif w in [3, 4]:   # MASSIVE pre-load
                    cases_mult = 4.0
                elif phase == "promo":
                    cases_mult = 2.0
                elif phase == "post":
                    post_offset = w - 8
                    if post_offset <= 4:
                        cases_mult = 0.30
                    else:
                        cases_mult = 0.70
                else:
                    cases_mult = 1.02

            cases_shipped = base_cases * cases_mult * float(noise(1)[0])
            cases_shipped = max(0.0, cases_shipped)
            units_shipped  = cases_shipped * UNITS_PER_CASE

            # ----- Returns -----
            if scenario == "inventory_risk":
                ret_pct = 0.05
            elif scenario == "pantry_loaded":
                ret_pct = 0.02
            else:
                ret_pct = 0.015
            returns_units = units_shipped * ret_pct * float(noise(1, pct=0.02)[0])

            # ----- Estimated retail on-hand -----
            # Δ = shipped - sold - returns
            net_shipped = units_shipped - returns_units
            retail_oh = retail_oh + net_shipped - pos_units
            # Clamp to scenario-specific floor
            if scenario == "inventory_risk":
                floor = 1000.0
            else:
                floor = 200.0
            retail_oh = max(floor, retail_oh)

            # Cap to scenario ceiling in post for inventory_risk
            if scenario == "inventory_risk" and phase in ["promo", "post"]:
                retail_oh = max(retail_oh, 3000.0)

            rows.append({
                "week_ending":              date,
                "brand":                    "Summit Foods",
                "sku":                      sku,
                "cases_shipped":            round(cases_shipped, 2),
                "units_per_case":           UNITS_PER_CASE,
                "units_shipped":            round(units_shipped, 2),
                "returns_units":            round(returns_units, 2),
                "estimated_retail_on_hand": round(retail_oh, 1),
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
# Main
# ---------------------------------------------------------------------------

def main():
    for scenario in SCENARIOS:
        print(f"\n=== Scenario: {scenario} ===")
        out_dir = BASE_DIR / scenario

        iri   = build_iri(scenario)
        pos   = build_pos(scenario)
        stars = build_stars(scenario)

        write_excel(iri,   out_dir / "iri_data.xlsx")
        write_excel(pos,   out_dir / "pos_data.xlsx")
        write_excel(stars, out_dir / "stars_data.xlsx")

    print("\nAll fixtures generated successfully.")


if __name__ == "__main__":
    main()
