# STELLA — Post-Promotion Analysis Engine

**Named for Stella Cosans, born April 2026.**
*See your KPIs in the stars.*

> Stella is a Streamlit application that ingests three spreadsheets — syndicated market data, retail POS scan data, and wholesale shipment data — reconciles them against user-entered product economics, and produces a graded assessment of a trade promotion's effectiveness. It answers three questions: Did the promo work? Why or why not? What should we do next?

---

## 1. WHAT THIS IS — AND WHAT IT ISN'T

### 1.1 Scope

Stella is a **single-event, single-retailer, single-promoted-brand** post-promotion review tool. That narrow scope is intentional. It mirrors how most CPG post-promo reviews are actually conducted: one brand team sits down with one retailer's data and asks whether a specific promotion was worth the money.

The goal is not to solve every promotional architecture problem. The goal is to prove that agentic coding can quickly build a serious analytic application with real business logic — one that triangulates multiple data sources, applies nontrivial economics, and produces actionable recommendations.

### 1.2 Core Thesis

1. **Triangulates IRI + POS + STAR** rather than pretending one source is enough.
2. Combines uploaded external data with transparent, user-entered economics.
3. Computes nontrivial KPIs with visible logic and a clearly stated counterfactual.
4. Assigns a configurable grade.
5. Explains the result with a judgment-first narrative and optional AI deep dive.
6. Surfaces the hidden stories: **inventory risk** and **whether the promo bought real growth or just pantry loading**.
7. **Recommends an action**, not just a diagnosis.

### 1.3 What This Is Not (v1 Boundaries)

Do not add any of the following. They would make the demo less sharp:

- Multi-retailer comparison in one run
- Multiple simultaneous promoted brands
- Support for promo mechanics beyond TPR (BOGO, feature ads, displays)
- Data editing or synthetic data generation inside the app
- Causal inference, elasticity estimation, or advanced modeling
- Backend database, user accounts, or session persistence
- A "scenario selector" or any UI that presents pre-bundled promo stories

### 1.4 Tech Stack

| Layer | Tool |
|-------|------|
| Language | Python 3.11+ |
| UI Framework | Streamlit |
| Data | Pandas, NumPy |
| Visualization | Plotly |
| LLM (optional) | Anthropic Claude API (`claude-sonnet-4-20250514`) |

### 1.5 File Structure

```
stella/
├── app.py                    # Streamlit entry point
├── ingestion.py              # File upload, schema validation, promo detection
├── analysis.py               # Counterfactual baseline, KPI engine, grading, recommendation
├── narrative.py              # Rules-based + LLM narrative generation
├── visualizations.py         # All Plotly chart builders
├── config.py                 # Schemas, defaults, color palette, grading thresholds
├── requirements.txt
├── test_fixtures/            # Dev/QA only — not exposed in UI
│   ├── strong_promo/
│   │   ├── iri_data.xlsx
│   │   ├── pos_data.xlsx
│   │   └── stars_data.xlsx
│   ├── pantry_loaded/
│   │   ├── iri_data.xlsx
│   │   ├── pos_data.xlsx
│   │   └── stars_data.xlsx
│   └── inventory_risk/
│       ├── iri_data.xlsx
│       ├── pos_data.xlsx
│       └── stars_data.xlsx
└── README.md
```

---

## 2. USER WORKFLOW

The live experience is always:

**Upload → Validate → Configure → Analyze → Recommend**

There is no scenario picker. There is no demo mode button. The user uploads three `.xlsx` files, enters their product economics, and the app derives the story from the data.

If a demo requires pre-loaded data for reliability, the presenter uploads the files manually from `test_fixtures/` — same experience the user would have. The app does not know or care whether the files are "demo" or "real."

---

## 3. DATA SOURCES — EXACT SCHEMAS

Column names must match exactly. The app validates on upload and rejects files with missing or misnamed columns.

### 3.1 IRI Data (`iri_data.xlsx`)

Syndicated scanner data — a **panel sample** of retailers. One row per brand/SKU per week.

| Column | Type | Description |
|--------|------|-------------|
| `week_ending` | date | Saturday end-of-week, YYYY-MM-DD |
| `brand` | str | Brand name |
| `sku` | str | SKU descriptor |
| `dollar_sales` | float | Estimated total market dollar sales |
| `unit_sales` | float | Estimated total market unit sales |
| `avg_net_price` | float | Average net price per unit (post-deal) |
| `market_share_dollars` | float | Dollar share of total category (0–1) |
| `market_share_units` | float | Unit share of total category (0–1) |
| `tdp` | float | Total distribution points |
| `any_promo_flag` | bool | Whether any promo was active |

**Constraints:**
- All brands × all SKUs × all weeks present. No gaps.
- `market_share_dollars` across all brands must sum to ≤ 1.0 per week (tolerance ±0.05; remainder is "all other" brands).

### 3.2 POS Data (`pos_data.xlsx`)

Point-of-sale scan data — **census-level** from the retailer. One row per brand/SKU per week. Includes loyalty ID (LID) sourcing for the promoted brand only.

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
| `loyalty_pct_competitor_switch` | float | % of volume from buyers switching from competitors (0–1) |
| `loyalty_pct_category_expander` | float | % of volume from buyers new to category or lapsed 6mo+ (0–1) |

**Constraints:**
- `loyalty_pct_*` columns sum to 1.0 (±0.02) for the promoted brand's SKUs. Null/blank for all other brands.
- `scan_deal_dollars` = 0 for non-promoted brands and non-promo weeks.

### 3.3 STAR Data (`stars_data.xlsx`)

Shipment data — **wholesale-to-retail** pipeline. Tracks physical inventory flow. One row per SKU per week. **Contains only the promoted brand** (manufacturers see only their own shipments through STAR).

| Column | Type | Description |
|--------|------|-------------|
| `week_ending` | date | Saturday end-of-week, YYYY-MM-DD |
| `brand` | str | Brand name (promoted brand only) |
| `sku` | str | SKU descriptor |
| `cases_shipped` | int | Cases shipped from distributor to retailer DCs |
| `units_per_case` | int | Units per case (e.g. 12) |
| `units_shipped` | int | = cases_shipped × units_per_case |
| `returns_units` | int | Units returned or destroyed |
| `estimated_retail_on_hand` | int | Estimated ending retail inventory in units |

**What is NOT in STAR:** No revenue, no trade spend, no cost data. STAR is a third-party inventory tracking service. It sees boxes moving, not dollars. All financial calculations come from user-configured inputs.

---

## 4. DATA PREP GUIDE — FOR EXTERNAL DATA CREATION

This section is for whoever creates the spreadsheet files externally (using ChatGPT, Claude, or manual Excel work). The app does not generate data. It reads what it receives.

### 4.1 Structural Rules

1. Column names must be character-for-character identical to Section 3 schemas.
2. Dates must be Saturdays in YYYY-MM-DD format. Minimum 8 weeks, recommended 16.
3. Brand and SKU strings must be identical across all three files for the promoted brand.
4. IRI and POS must have all brands × SKUs × weeks. STAR has only the promoted brand.
5. Use `.xlsx` format, not `.csv`.

### 4.2 Realistic Commercial Behaviors to Encode

When creating synthetic data, build in these dynamics so the app has a real story to find:

**Baseline period (pre-promo):**
- Stable weekly velocities with ±5% noise
- Prices at normal shelf levels, no deal activity

**Promo period (promoted brand only):**
- Volume lift: 2.0–2.8× baseline
- Price: drops by TPR amount
- LID sourcing: Loyalists 45–55%, Switchers 25–35%, Expanders 15–25%
- Competitors lose volume: closest rival −8–15%, others −3–7%

**Post-promo:**
- Promoted brand velocity drops to 75–85% of baseline (pantry hangover), recovers over 4–8 weeks
- Competitors recover gradually
- LID sourcing shifts: loyalist % rises, switcher % falls

**Shipment timing (STAR):**
- Pre-load: shipments spike 1–2 weeks before promo starts
- During promo: elevated but below pre-load peak
- Post-promo: shipments drop below baseline as pipeline drains
- Returns: small (1–3% of shipped), concentrated in post-promo period

**Cross-source consistency:**
- POS units ≈ IRI units × retailer share-of-market (~15–20%)
- STAR total units shipped should exceed POS total units sold by 5–12%
- IRI `avg_net_price` and POS `pos_price` within 2–4% of each other

### 4.3 Three Test Fixture Scenarios (Dev/QA Only)

Create these three datasets during development to harden the app. They are not product features.

| Fixture | Story | Key Characteristics |
|---------|-------|---------------------|
| `strong_promo/` | Good promo — healthy economics, real growth | High switcher %, strong share retention, pipeline fill 1.05–1.10, positive total margin delta |
| `pantry_loaded/` | Misleading lift — mostly loyalist pantry loading | Loyalist % > 60%, poor share retention (<30%), post-promo deficit nearly cancels gross lift, ROI borderline |
| `inventory_risk/` | Operational danger — overfill and returns | Pipeline fill > 1.20, returns > 3%, shipment collapse post-promo, estimated_retail_on_hand stays elevated through W16 |

Use these to test: KPI correctness, narrative branching, scoring edge cases, chart readability, and recommendation logic. The app must produce sensible, differentiated output for all three.

---

## 5. USER-CONFIGURED INPUTS (Sidebar)

### 5.1 Promotion Context (Optional Metadata)

These fields label the analysis but do not affect calculations. All are optional text inputs with sensible defaults.

| Input | Default | Purpose |
|-------|---------|---------|
| Retailer Name | (blank) | Labels charts and narrative; if blank, app uses "Retailer" |
| Promotion Type | "TPR" (read-only in v1) | Labels narrative; fixed to TPR — do not expose as editable |
| Funding Type | "Manufacturer-funded scan-back" | Context for narrative |
| Analysis Notes | (blank) | Free-text; displayed in Executive Summary |

### 5.2 Product Economics — Three Financial Inputs + TPR

| Input | Label | Default | Description |
|-------|-------|---------|-------------|
| `list_price` | List Price ($/unit) | 6.29 | Manufacturer list price — top-line revenue per unit before any deductions |
| `cogs` | COGS ($/unit) | 2.10 | Variable cost per unit (manufacturing + packaging + freight) |
| `standard_trade_rate` | Standard Trade Rate (%) | 18% | Ongoing trade spend as % of list price — everyday terms, slotting, MDF. Independent of this specific promotion |
| `tpr_per_unit` | TPR Amount ($/unit) | 1.25 | The incremental per-unit discount funded for this specific promotion. On top of standard trade |

**Input validation:** `list_price > cogs > 0`, `0 ≤ standard_trade_rate < 100`, `tpr_per_unit ≥ 0`, and `tpr_per_unit < list_price - cogs - standard_trade_dollar`. If promo CM would be negative, show `st.warning` but allow it (a negative-CM promo is a real business outcome worth diagnosing).

**Derived economics (displayed as read-only metrics in sidebar):**

| Metric | Formula | Example |
|--------|---------|---------|
| Standard Trade $/unit | `list_price × standard_trade_rate / 100` | $1.13 |
| **Gross Margin/unit** | `list_price − cogs` | $4.19 |
| **Standard Contribution Margin/unit** | `list_price − cogs − standard_trade` | $3.06 |
| Standard CM % | `standard_CM / list_price` | 48.6% |
| **Promo Contribution Margin/unit** | `standard_CM − tpr_per_unit` | $1.81 |
| Promo CM % | `promo_CM / list_price` | 28.8% |
| CM Erosion/unit | `tpr_per_unit` | $1.25 |

Note: "Contribution Margin" in this app means list price minus COGS minus trade (standard or standard + TPR). It does not include fixed costs, SG&A, or other below-the-line items.

### 5.3 Grading Weight Sliders

Four sliders, must sum to 100%:

| Slider | Default |
|--------|---------|
| Incremental Promo ROI | 40% |
| Share Impact | 25% |
| Volume Quality | 20% |
| Inventory Health | 15% |

If sum ≠ 100%, auto-normalize and display `st.info` showing the normalized weights.

---

## 6. INGESTION & VALIDATION (`ingestion.py`)

### 6.1 Schema Validation

On upload, check each file against its column schema (Section 3). Report missing, extra, or misnamed columns. **Critical failure — blocks analysis.**

### 6.2 Structural Validation

| Check | Severity | Behavior |
|--------|----------|----------|
| Date column not parseable as dates | Critical | Block |
| STAR brand not found in IRI or POS | Critical | Block |
| Fewer than 8 weeks of data | Critical | Block |
| Duplicate rows (same brand + SKU + week_ending) | Critical | Block with count of duplicates |
| Missing weeks in any brand/SKU series (non-contiguous dates) | Critical | Block with list of gaps |
| Brand/SKU strings differ between files for promoted brand | Warning | No fuzzy matching in v1. Strip leading/trailing whitespace, normalize to title case, then exact match only. If still unmatched, warn with list of mismatched strings and exclude unmatched rows from all cross-source calculations |
| Date ranges don't fully align across files | Warning | Show differences, analyze intersection only |
| `loyalty_pct_*` don't sum to 1.0 for promoted brand (±0.02) | Warning | Flag, proceed |
| Negative values in volume or price columns | Warning | Flag rows |
| Shares sum > 1.05 in any week | Warning | Flag weeks |
| POS total units vs. IRI implied retailer units differ > 25% | Warning | Flag, note in narrative |

### 6.3 Promoted Brand Detection

The promoted brand = the brand that appears in STAR data. Validate it exists in IRI and POS. Display: `st.success(f"Promoted brand detected: {brand_name}")`.

### 6.4 Promo Period Detection

Auto-detect from POS data: promo weeks are weeks where `scan_deal_dollars > 0` for the promoted brand (summed across SKUs).

**Validation:** promo weeks must be contiguous. If not, `st.warning("Non-contiguous promo weeks detected: {list}. Using full range as promo period.")` and treat the entire span (first to last promo week) as the promo period.

**Period definitions derived from detection:**
- Pre-promo: all weeks before first promo week
- Promo: first through last promo week (inclusive)
- Post-promo: all weeks after last promo week

If pre-promo period has fewer than 2 weeks, `st.warning("Limited baseline period. KPIs may be unreliable.")`

---

## 7. COUNTERFACTUAL BASELINE — DEFINED ONCE

All incrementality calculations depend on a counterfactual: what would have happened without the promotion. Stella defines this in one place and applies it consistently.

### 7.1 Baseline Definition

**Baseline weekly unit velocity** = average POS `pos_unit_sales` per week for the promoted brand, across all pre-promo weeks. Calculated at the brand level (sum of all SKUs per week, then averaged across pre-promo weeks).

**Baseline weekly dollar share** = average IRI `market_share_dollars` for the promoted brand across pre-promo weeks.

### 7.2 Counterfactual Projection

The "no-promo scenario" assumes the promoted brand would have continued at baseline velocity and baseline share for the entire promo + post-promo period. This is a simplification — it ignores seasonality, competitive launches, and secular trends. That's acceptable for v1 and is standard practice in most CPG post-promo reviews.

### 7.3 How the Counterfactual Feeds KPIs

| Calculation | Uses Counterfactual As |
|-------------|----------------------|
| Incremental Volume (Gross) | Promo-period actual units − (baseline weekly units × promo weeks) |
| Post-Promo Volume Deficit | Σ max(0, baseline weekly units − actual weekly units) for each post-promo week |
| Net Incremental Volume | Gross Incremental − Post-Promo Deficit |
| Share Change | promo-period avg share − baseline share |

**Canonical economic outcome:** Use **Net Incremental CM** (defined in Section 8.2) as the single all-in economic measure. It accounts for promo-period margin erosion, volume lift, and post-promo pull-forward loss. Do not separately compute a full-analysis-window baseline metric — that would double-count and conflict. All-In Event Margin Delta is simply a display label for Net Incremental CM, not a separate calculation.

---

## 8. ANALYSIS ENGINE (`analysis.py`)

### 8.1 Core KPIs

| KPI | Formula | Sources | Notes |
|-----|---------|---------|-------|
| **Incremental Volume (Gross)** | Σ promo-period units − (baseline × promo weeks) | POS | Can be negative if promo underperformed |
| **Post-Promo Deficit** | Σ max(0, baseline − actual) for each post-promo week | POS | Interpreted as pull-forward / pantry depletion effect |
| **Net Incremental Volume** | Gross − Deficit | POS | The real volume gain after accounting for pull-forward |
| **Incremental TPR Investment** | `tpr_per_unit × Σ promo-period units` | POS × input | The promo-specific cost — not total trade |
| **Incremental Promo ROI** | Net Incremental CM / Incremental TPR Investment | Derived | See 8.2 for Net Incremental CM definition |
| **Dollar Share Change** | Promo-period avg share − baseline share | IRI | In percentage points |
| **Share Retention** | (Late-post avg share − baseline share) / (promo avg share − baseline share) | IRI | Late-post = last 4 post-promo weeks, or all available post-promo weeks if fewer than 4. See edge cases below |
| **Pantry Loading Index** | Avg `loyalty_pct_brand_loyalist` during promo weeks | POS LID | Higher = more pantry loading |
| **Sourcing Quality** | Qualitative label (see 8.3) | POS LID | Not a composite score |
| **Pipeline Fill Ratio** | Total STAR units shipped / Total POS units sold (full window) | STAR + POS | 1.0 = perfect alignment |
| **Returns Rate** | Total STAR returns / Total STAR shipped | STAR | As percentage |
| **Inventory Risk** | Flag (see 8.4) | STAR + POS | Boolean with explanation |

### 8.2 Economic Calculations — Margin Waterfall

**Per-unit waterfall (two scenarios displayed side by side):**

```
                              No Promo        With TPR
                              --------        --------
List Price                     $6.29           $6.29
− COGS                        ($2.10)         ($2.10)
─────────────────────────────────────────────────────
Gross Margin                   $4.19           $4.19
− Standard Trade (18%)        ($1.13)         ($1.13)
─────────────────────────────────────────────────────
Standard CM                    $3.06           $3.06
− TPR                          $0.00          ($1.25)
─────────────────────────────────────────────────────
Contribution Margin            $3.06           $1.81
CM %                           48.6%           28.8%
```

**Total event economics:**

| Metric | Formula |
|--------|---------|
| Promo-Period Total CM | Σ promo-period units × promo_CM/unit |
| Baseline-Equivalent CM | (baseline weekly units × promo weeks) × standard_CM/unit |
| Incremental Promo-Period CM | Promo-Period Total CM − Baseline-Equivalent CM |
| Post-Promo CM Loss | Post-Promo Deficit units × standard_CM/unit |
| **Net Incremental CM** | Incremental Promo-Period CM − Post-Promo CM Loss |
| **All-In Event Margin Delta** | = Net Incremental CM. This is a display label, not a separate calculation. It is the canonical single number answering "did we make or lose money vs. doing nothing?" |
| **Volume Multiplier to Break Even** | standard_CM / promo_CM. The lift multiple needed for promo-period total CM to equal baseline-equivalent CM. Only meaningful when promo_CM > 0 (see edge cases) |
| Actual Volume Multiplier | promo-period actual units / (baseline × promo weeks) |

### 8.3 Sourcing Quality — Qualitative Labels

Instead of a pseudo-precise composite score, classify sourcing quality using thresholds on the promo-period average LID mix:

| Label | Condition | Interpretation |
|-------|-----------|----------------|
| **High Quality** | Competitor Switcher % ≥ 30% OR Category Expander % ≥ 20% | Promo is attracting new buyers — real market growth |
| **Mixed** | Loyalist % 45–60% AND Switcher + Expander combined ≥ 30% | Some real growth, some pantry loading |
| **Pantry-Loaded** | Loyalist % > 60% | Majority of lift is existing buyers buying earlier/more — limited true incrementality |

Also compute and display: **True Growth %** = (Switcher % + Expander %) as a single number. This is the percentage of promo volume that represents genuine new demand.

### 8.4 Inventory Risk Assessment

| Condition | Risk Level |
|-----------|-----------|
| Pipeline Fill 1.00–1.10 AND no shipment collapse | **Low** — healthy alignment |
| Pipeline Fill 1.10–1.20 OR post-promo shipments < 60% of baseline for 2+ weeks | **Moderate** — watch for overhang |
| Pipeline Fill > 1.20 OR returns > 3% OR post-promo shipments < 50% of baseline for 3+ weeks | **High** — likely inventory overfill |

Display as a traffic-light indicator with a one-sentence explanation.

### 8.5 Edge Case Handling

| Situation | Behavior |
|-----------|----------|
| Promo-period share gain ≤ 0 | Share Score = 0. Narrative notes the promo failed to move share |
| Share Retention denominator near zero (share gain < 0.1 pp) | Share Retention = N/A. Display "Share change too small to measure retention" |
| `loyalty_pct_*` missing or null for promoted brand | Sourcing Quality = "Unavailable." Sourcing-dependent KPIs skipped. Tab shows "No LID data available" |
| `loyalty_pct_*` sum outside 0.95–1.05 for promoted brand | `st.warning`. Normalize to 1.0 before calculating |
| Pipeline Fill < 0.85 | Flag as "Under-shipped — possible stockout risk during promo" |
| Net Incremental Volume ≤ 0 | ROI = negative. Narrative leads with this as the dominant finding |
| Fewer than 4 post-promo weeks | Post-Promo Deficit marked as "Incomplete — limited post-promo data" |
| `promo_CM <= 0` (TPR exceeds standard CM) | Breakeven Multiplier = N/A. Narrative states: "At this TPR depth, the event cannot break even on contribution margin through volume alone — every incremental unit sold during the promo loses money." ROI Score = 0. All-In Event Margin Delta will be negative by construction |

### 8.6 Promo Grading

Four sub-scores, each 0–100:

| Dimension | Scoring Logic |
|-----------|---------------|
| **ROI Score** | ROI ≥ 1.5 → 100; ≤ 0 → 0; linear between |
| **Share Score** | Share gain ≥ 2 pp → 100; ≤ 0 → 0; linear. Multiply by min(Share Retention, 1.0). If Share Retention = N/A, multiply by 0.5 |
| **Volume Score** | Net Incremental as % of baseline-window total: ≥ 20% → 100; ≤ 0 → 0; linear. If Pantry Loading Index > 55%, multiply by 0.8 |
| **Inventory Health** | Pipeline Fill 1.00–1.05 → 100; 1.05–1.10 → 80; 1.10–1.15 → 50; 1.15–1.20 → 25; > 1.20 → 0. Deduct 20 if Inventory Risk = High |

Composite Score = Σ(normalized_weight_i × score_i).

| Grade | Score | Color |
|-------|-------|-------|
| **A** | ≥ 75 | Green `#2E7D32` |
| **B** | 50–74 | Amber `#F57F17` |
| **C** | < 50 | Red `#C62828` |

### 8.7 Recommendation Engine

Rules-based recommendation derived from grade, KPIs, and sourcing. Returns a **primary recommendation** and up to two **supporting rationale points**.

| Condition | Recommendation |
|-----------|---------------|
| Grade A, Sourcing ≠ Pantry-Loaded, Inventory Risk = Low | **Repeat with similar mechanics.** Volume, economics, and sourcing all support re-execution |
| Grade A or B, but Inventory Risk = Moderate or High | **Repeat only with tighter inventory controls.** Promo economics are acceptable but pipeline management needs guardrails — consider capping pre-load or shortening duration |
| Grade B, Sourcing = Pantry-Loaded | **Repeat only with tighter funding guardrails.** Volume responded but most lift is existing buyers buying early — test a shallower discount to see if response holds |
| Grade B, All-In Margin Delta < 0 | **Test a shallower discount.** Volume lifted but margin erosion exceeded the gain — the TPR is too deep for the lift it generates |
| Grade C, Net Incremental Volume > 0 but ROI < 0.5 | **Do not repeat at current depth.** The promo moved volume but destroyed value — incrementality does not justify the investment |
| Grade C, Net Incremental Volume ≤ 0 | **Do not repeat.** The promotion failed to generate net incremental volume after accounting for post-promo pull-forward |
| Grade C, Inventory Risk = High | **Do not repeat; resolve inventory overhang first.** Elevated pipeline fill and returns indicate the event created operational drag that must clear before re-promoting |

Display as a styled card in the Executive Summary with the recommendation in bold and rationale below.

---

## 9. NARRATIVE GENERATION (`narrative.py`)

### 9.1 Rules-Based Narrative (Default)

The narrative leads with judgment, not summary. It answers the three questions in order: Did it work? Why? What next?

All brand names, retailer names, and metrics are derived from data and inputs — nothing is hardcoded.

**Paragraph 1 — Verdict (Did it work?):**

Choose one of three opening patterns based on grade:

- Grade A: "This promotion worked. The {brand} TPR{at_retailer} earned an **A** grade (score: {score}/100), generating {net_incr_vol_pct}% net incremental volume and {share_change} pp of dollar share gain with an Incremental Promo ROI of {roi}."
- Grade B: "This promotion delivered mixed results. The {brand} TPR{at_retailer} earned a **B** grade (score: {score}/100). {strongest_dimension} was solid, but {weakest_dimension} limits the case for repeating without changes."
- Grade C: "This promotion underperformed. The {brand} TPR{at_retailer} earned a **C** grade (score: {score}/100). {primary_failure_reason}."

`{at_retailer}` = " at {retailer_name}" if retailer name is provided, else "".

**Paragraph 2 — Economics (Why?):**

"At a list price of ${list_price} and a TPR of ${tpr}/unit, contribution margin dropped from ${std_cm} ({std_cm_pct}%) to ${promo_cm} ({promo_cm_pct}%) per unit. {breakeven_sentence} {margin_delta_sentence}"

Where `{breakeven_sentence}` is:
- If promo_CM > 0: "The promo needed a {breakeven_mult:.1f}× volume lift to break even on total contribution margin; it achieved {actual_mult:.1f}×."
- If promo_CM ≤ 0: "At this TPR depth, the event cannot break even on contribution margin through volume alone — every incremental promo unit sold loses money."

Where `{margin_delta_sentence}` is:
- If All-In Margin Delta > 0: "The volume lift more than offset the per-unit erosion, generating ${delta:,.0f} in incremental contribution margin."
- If All-In Margin Delta ≤ 0: "The volume lift was insufficient to offset margin erosion, resulting in ${abs(delta):,.0f} less total contribution margin than a no-promo scenario."

**Paragraph 3 — Sourcing (Why? continued):**

"Sourcing quality is **{sourcing_label}**. {sourcing_detail_sentence} True Growth (Switchers + Expanders) was {true_growth_pct:.0f}% of promo volume."

Where `{sourcing_detail_sentence}` is:
- High Quality: "The TPR drew meaningful volume from competitors and/or expanded the buyer base — this is real market growth, not just acceleration of existing demand."
- Mixed: "The promo attracted some new buyers but a significant share of the lift came from existing loyalists buying earlier or stocking up."
- Pantry-Loaded: "The majority of incremental volume came from existing buyers pulling purchases forward. This limits true incrementality and contributes to the post-promo volume dip."
- Unavailable: "No loyalty data was available to assess sourcing dynamics."

**Paragraph 4 — Operational Risk:**

"Pipeline fill ratio is {fill:.2f} ({risk_level} risk). {risk_detail_sentence} Returns rate is {returns_pct:.1f}%, which is {returns_assessment}."

Where `{returns_assessment}` = "within normal range" if <2%, "elevated" if 2–4%, "high" if >4%.

### 9.2 LLM Narrative (Optional — "Generate AI Analysis" Button)

When clicked, call the Claude API:

```python
system = "You are a senior CPG trade analyst writing a post-promotion review for internal stakeholders. Be direct, analytical, and specific. Lead with conclusions. Use the data provided — do not invent numbers."

prompt = f"""Write a 4–5 paragraph executive assessment of this promotion.

PROMOTION CONTEXT:
- Brand: {brand}
- Retailer: {retailer or 'Not specified'}
- Type: TPR of ${tpr}/unit for {n_promo_weeks} weeks
- Window: {n_total_weeks} weeks ({n_pre} pre / {n_promo} promo / {n_post} post)

PRODUCT ECONOMICS:
- List Price: ${list_price}  |  COGS: ${cogs}  |  Std Trade: {rate}%
- Standard CM: ${std_cm} ({std_cm_pct}%)  |  Promo CM: ${promo_cm} ({promo_cm_pct}%)
- Breakeven volume multiplier: {breakeven_mult:.1f}×

KPI SUMMARY:
{json.dumps(kpi_dict, indent=2)}

Cover: (1) verdict and grade justification, (2) margin decomposition, (3) sourcing quality, (4) competitive dynamics, (5) inventory risk and next steps.
"""
```

Display in `st.expander("AI-Generated Deep Dive")`.

Error handling: if API call fails → `st.info("AI analysis unavailable — set ANTHROPIC_API_KEY environment variable to enable.")`. Rules-based narrative always works.

---

## 10. VISUALIZATION TABS (`visualizations.py`)

### Color Assignment

Colors are assigned dynamically. The promoted brand always gets blue. Other brands are assigned in order of appearance:

| Position | Color |
|----------|-------|
| Promoted brand | `#1E88E5` (blue) |
| 2nd brand | `#8E24AA` (purple) |
| 3rd brand | `#43A047` (green) |
| 4th brand | `#FB8C00` (orange) |
| 5th brand | `#757575` (gray) |
| 6th+ brands | cycle from purple |

### Tab 1: Executive Summary

**Priority: answer the three questions within seconds.**

Layout:
1. **Grade badge** — large, colored (A/B/C), with composite score
2. **Recommendation card** — styled box with primary recommendation and rationale
3. **KPI cards** — two rows of three:
   - Row 1: Incremental Promo ROI | Net Incremental Volume (units + %) | Dollar Share Change (pp)
   - Row 2: Sourcing Quality (label + True Growth %) | Promo CM/unit | All-In Event Margin Delta ($)
4. **Grading weight sliders** — four sliders, grade updates reactively
5. **Narrative** — rules-based text
6. **AI expander** — "Generate AI Analysis" button and output

### Tab 2: Price Ladders

- **Chart A:** Grouped bar, X = brand/SKU, Y = price. Two bars: "Pre-Promo Avg" vs. "Promo-Period Avg" (POS `pos_price`). Promoted brand shows the gap.
- **Chart B:** Line chart, X = week, Y = avg net price per brand (IRI). Price dip visible during promo.
- **Annotation:** Horizontal lines at tier boundaries if discernible from price clustering.

### Tab 3: Market Share

- **Chart A:** Stacked area, X = week, Y = dollar share by brand (IRI). Promoted brand expands during promo.
- **Chart B:** Bar chart, share change (promo avg − baseline) by brand.
- **Metric:** Share Retention % (or "N/A" with explanation).

### Tab 4: LID Sourcing

- **Chart A:** Stacked bar, X = week (promoted brand only), Y = % of volume. Three segments: Loyalists, Switchers, Expanders. Shows shift from promo mix to post-promo.
- **Chart B:** Donut showing promo-period sourcing split.
- **Metrics:** Sourcing Quality label | True Growth %
- **If no LID data:** Display "No loyalty sourcing data available for the promoted brand" and skip charts.

### Tab 5: Volume & Returns

- **Chart A:** Dual-axis, X = week. Line: POS units (promoted brand). Bars: STAR returns. Dashed horizontal: baseline.
- **Chart B:** Bar chart, weekly incremental vs. baseline (positive = above baseline, negative = below).
- **Metrics:** Gross Incremental | Post-Promo Deficit | Net Incremental Volume

### Tab 6: Margin Waterfall

- **Chart A:** Waterfall chart, per-unit economics. Two side-by-side: "Standard" vs. "With TPR." Steps: List Price → −COGS → Gross Margin → −Standard Trade → Standard CM → −TPR → Promo CM.
- **Chart B:** Two bars comparing total CM: "Baseline Scenario" vs. "Promo Scenario (incl. post-promo deficit)." Delta annotation.
- **Metrics:** CM Erosion/unit | Breakeven Multiplier | Actual Multiplier | All-In Margin Delta

### Tab 7: Shipments vs. Retail Pull

- **Chart A:** Dual-line, X = week. STAR units shipped vs. POS units sold. Shaded area between = inventory delta (green when close, red when diverging).
- **Chart B:** STAR `estimated_retail_on_hand` over time.
- **Chart C:** Cumulative shipped vs. sold. Gap at final week = pipeline surplus.
- **Metrics:** Pipeline Fill Ratio (traffic light) | Inventory Risk (level + explanation) | Returns Rate

---

## 11. STREAMLIT APP STRUCTURE (`app.py`)

```python
st.set_page_config(page_title="Stella", layout="wide", page_icon="⭐")
st.title("⭐ STELLA — Post-Promotion Analysis")
st.caption("See your KPIs in the stars")

# --- Sidebar ---
with st.sidebar:
    st.header("📁 Data Input")
    iri_file = st.file_uploader("IRI Data (syndicated)", type="xlsx")
    pos_file = st.file_uploader("POS Data (retail scan)", type="xlsx")
    stars_file = st.file_uploader("STAR Data (shipments)", type="xlsx")

    st.divider()
    st.header("📋 Promotion Context")
    retailer_name = st.text_input("Retailer Name", value="")
    promo_type = "TPR"  # Fixed in v1
    st.markdown(f"**Promotion Type:** {promo_type}")
    funding_type = st.text_input("Funding Type", value="Manufacturer-funded scan-back")
    analysis_notes = st.text_area("Analysis Notes", value="")

    st.divider()
    st.header("💰 Product Economics")
    list_price = st.number_input("List Price ($/unit)", value=6.29, step=0.01, format="%.2f")
    cogs = st.number_input("COGS ($/unit)", value=2.10, step=0.01, format="%.2f")
    trade_rate = st.slider("Standard Trade Rate (%)", 0, 50, 18)
    tpr_amount = st.number_input("TPR Amount ($/unit)", value=1.25, step=0.01, format="%.2f")
    # Display derived metrics (read-only)

    st.divider()
    st.header("⚖️ Grading Weights")
    w_roi = st.slider("Incremental Promo ROI", 0, 100, 40)
    w_share = st.slider("Share Impact", 0, 100, 25)
    w_volume = st.slider("Volume Quality", 0, 100, 20)
    w_inventory = st.slider("Inventory Health", 0, 100, 15)

# --- Main ---
if all three files uploaded:
    iri, pos, stars = load_and_validate(iri_file, pos_file, stars_file)
    if validation.passed:
        financials = compute_financials(list_price, cogs, trade_rate, tpr_amount)
        context = {retailer_name, promo_type, funding_type, analysis_notes}
        kpis = calculate_kpis(iri, pos, stars, financials)
        grade, scores = compute_grade(kpis, weights)
        recommendation = compute_recommendation(grade, kpis)
        narrative = generate_narrative(kpis, grade, scores, recommendation, financials, context)

        tabs = st.tabs([
            "Executive Summary", "Price Ladders", "Market Share",
            "LID Sourcing", "Volume & Returns", "Margin Waterfall",
            "Shipments vs. Pull"
        ])
else:
    st.markdown("""
    ### How to use Stella
    1. Prepare three Excel files matching the required schemas (see README)
    2. Upload IRI, POS, and STAR files in the sidebar
    3. Configure your product economics and TPR amount
    4. Adjust grading weights to reflect your priorities
    
    Stella will validate the data, calculate KPIs, and produce a graded assessment 
    with a recommendation.
    """)
```

---

## 12. IMPLEMENTATION SEQUENCE FOR CLAUDE CODE

### Step 1: `config.py`
- Column schemas as dicts (for validation)
- Default financial values
- Color palette
- Grading thresholds and scoring functions
- Recommendation rules

### Step 2: `ingestion.py`
- Schema validation
- Date parsing and continuity checks
- Duplicate detection
- Promoted brand detection from STAR
- Promo period auto-detection from POS `scan_deal_dollars`
- All validation rules with severity

### Step 3: `analysis.py`
- Counterfactual baseline calculation
- All KPI calculations (takes financials dict)
- Margin waterfall (per-unit and total)
- Sourcing quality classification
- Inventory risk assessment
- Grading engine
- Recommendation engine
- Edge case handling for all formulas

### Step 4: `narrative.py`
- Judgment-first rules-based narrative (parameterized — no hardcoded names)
- LLM integration with graceful fallback

### Step 5: `visualizations.py`
- Seven tabs of charts
- Dynamic color assignment
- Consistent Plotly theming
- Graceful handling of missing data (e.g., no LID data)

### Step 6: `app.py`
- Wire everything together
- Sidebar with all inputs
- Empty state with instructions
- Tab layout with reactive updates

### Step 7: Polish and test
- Test against all three fixture datasets
- Verify narrative branching produces distinct output per scenario
- Verify recommendation logic covers all grade/KPI combinations
- Edge case testing: missing LID data, minimal weeks, negative ROI
- README with setup and data prep instructions

---

## 13. REQUIREMENTS

```
streamlit>=1.30.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
openpyxl>=3.1.0
anthropic>=0.40.0
```

---

## 14. DESIGN PRINCIPLES

1. **The app is a reader, not a writer.** It ingests externally-prepared data and derives the story. It should gracefully handle imperfect data with clear error messages, not silently produce bad analysis.

2. **Source triangulation is the point.** IRI for market context, POS for ground truth and sourcing, STAR for pipeline reality. Every tab should make you glad you have all three.

3. **Judgment first, evidence second.** The narrative and recommendation tell you what happened and what to do. The tabs let you interrogate why. This is a decision tool, not a dashboard.

4. **Economics are transparent.** The margin waterfall makes the TPR tradeoff viscerally clear. You can see exactly where the margin goes and whether volume compensates. That's the tab that makes executives lean in.

5. **The hidden stories matter most.** Inventory risk and sourcing quality are what separate a good promo review from a superficial one. Most analysis stops at "it sold." Stella asks "but at what cost, and to whom?"

6. **Narrow scope, real depth.** One event, one retailer, one brand. That constraint makes the analysis trustworthy rather than hand-wavy. v1 does one thing well.

7. **The LLM adds, it doesn't replace.** Rules-based output is the backbone. The AI deep dive adds interpretive nuance. The app works perfectly with no API key.

8. **The point is the build method.** Stella exists to show that agentic coding can produce a serious business application quickly. The demo should feel like a real tool, not a curated trick.
