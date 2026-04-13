# ⭐ STELLA — Post-Promotion Analysis Engine

*Named for Stella Cosans, born April 2026. See your KPIs in the stars.*

Stella is a Streamlit application that triangulates syndicated market data (IRI), retail POS scan data, and wholesale shipment data (STAR) against user-entered product economics to produce a graded assessment of a trade promotion's effectiveness.

**It answers three questions: Did the promo work? Why or why not? What should we do next?**

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Set `ANTHROPIC_API_KEY` in your environment to enable the optional AI deep dive.

---

## Data Files Required

Upload three `.xlsx` files from the sidebar. Column names must match exactly.

### `iri_data.xlsx` — Syndicated Scanner Data

| Column | Type | Description |
|--------|------|-------------|
| `week_ending` | date | Saturday end-of-week, YYYY-MM-DD |
| `brand` | str | Brand name |
| `sku` | str | SKU descriptor |
| `dollar_sales` | float | Estimated total market dollar sales |
| `unit_sales` | float | Estimated total market unit sales |
| `avg_net_price` | float | Average net price per unit |
| `market_share_dollars` | float | Dollar share of total category (0–1) |
| `market_share_units` | float | Unit share of total category (0–1) |
| `tdp` | float | Total distribution points |
| `any_promo_flag` | bool | Whether any promo was active |

### `pos_data.xlsx` — Point-of-Sale Scan Data

| Column | Type | Description |
|--------|------|-------------|
| `week_ending` | date | Saturday end-of-week, YYYY-MM-DD |
| `brand` | str | Brand name |
| `sku` | str | SKU descriptor |
| `pos_dollar_sales` | float | Actual register-ring dollar sales |
| `pos_unit_sales` | float | Actual units sold |
| `pos_price` | float | Average transaction price per unit |
| `scan_deal_dollars` | float | Scan-back deal $ redeemed that week |
| `loyalty_pct_brand_loyalist` | float | % of volume from existing brand buyers (0–1) |
| `loyalty_pct_competitor_switch` | float | % of volume from competitor switchers (0–1) |
| `loyalty_pct_category_expander` | float | % of volume from new/lapsed category buyers (0–1) |

*Loyalty columns: populated for promoted brand only; null for others. Promo week scan_deal_dollars > 0 triggers promo period detection.*

### `stars_data.xlsx` — Wholesale Shipment Data

| Column | Type | Description |
|--------|------|-------------|
| `week_ending` | date | Saturday end-of-week, YYYY-MM-DD |
| `brand` | str | Brand name (promoted brand only) |
| `sku` | str | SKU descriptor |
| `cases_shipped` | int | Cases shipped to retailer DCs |
| `units_per_case` | int | Units per case |
| `units_shipped` | int | = cases_shipped × units_per_case |
| `returns_units` | int | Units returned or destroyed |
| `estimated_retail_on_hand` | int | Estimated ending retail inventory |

---

## Product Economics Inputs

| Input | Default | Notes |
|-------|---------|-------|
| List Price ($/unit) | $6.29 | Manufacturer list price |
| COGS ($/unit) | $2.10 | Variable cost per unit |
| Standard Trade Rate (%) | 18% | Ongoing trade as % of list price |
| TPR Amount ($/unit) | $1.25 | Incremental per-unit promo discount |

---

## How Stella Works

1. **Promoted brand detection** — The brand in STAR data is the promoted brand.
2. **Promo period detection** — Weeks with `scan_deal_dollars > 0` for the promoted brand.
3. **Counterfactual baseline** — Average pre-promo weekly velocity and share.
4. **KPI engine** — Incrementality, margin waterfall, sourcing quality, inventory risk.
5. **Grading** — Weighted composite of ROI, Share, Volume, Inventory (configurable).
6. **Recommendation** — Rules-based, derived from grade + KPIs.
7. **Narrative** — Judgment-first text. Optional AI deep dive via Claude API.

---

## Test Fixtures (Dev/QA)

Three synthetic scenarios in `test_fixtures/`:

| Scenario | Story |
|----------|-------|
| `strong_promo/` | Good promo — healthy economics, real growth, Grade A |
| `pantry_loaded/` | Misleading lift — mostly loyalist pantry loading, Grade B |
| `inventory_risk/` | Operational danger — overfill and returns, Grade C |

Upload these from the sidebar to test the app without real data.

---

## File Structure

```
stella/
├── app.py                    # Streamlit entry point
├── ingestion.py              # File upload, schema validation, promo detection
├── analysis.py               # Counterfactual baseline, KPI engine, grading
├── narrative.py              # Rules-based + LLM narrative generation
├── visualizations.py         # All Plotly chart builders
├── config.py                 # Schemas, defaults, color palette, grading
├── requirements.txt
├── generate_fixtures.py      # Dev/QA — generates test_fixtures/ data
├── test_fixtures/
│   ├── strong_promo/
│   ├── pantry_loaded/
│   └── inventory_risk/
└── README.md
```
