# Liquor Inventory & Vendor Performance Analytics
### End-to-End Data Analytics + Machine Learning Pipeline
**Python · SQLite · Scikit-learn · Power BI**

---

## One-Line Summary

> Built an end-to-end analytics pipeline on 15M+ liquor distribution records — engineering a proportional freight allocation model, surfacing that 17 vendors drive 80% of revenue and 83% of vendors overpurchased in 2024, and training a Random Forest classifier that identifies underperforming products with **94% recall and 0.987 ROC-AUC** using stock turnover as the dominant risk signal.

---

## Dashboard Preview

📊 **Power BI Dashboard** — [Download .pbix](outputs/Vendor_Performance_Dashboard.pbix)
📄 **PDF Preview** — [View Dashboard PDF](outputs/Vendor_Performance_Dashboard.pdf)

---

## Problem Statement

A liquor distribution business operating across **80 stores and 126 vendors** had no centralized system to evaluate vendor performance, identify underperforming products, or detect overstock risk. Raw transactional data was spread across six disconnected CSV files totalling **15 million+ records and 1.6GB** — far too large for manual analysis.

**Core business problems:**
- No visibility into which vendors and products were generating losses
- No system to detect overstock risk before capital was already tied up
- Freight costs were incorrectly allocated, making per-product margin analysis unreliable
- No way to predict which products were at risk of underperformance

---

## Repository Structure

```
vendor-analysis-end-to-end/
│
├── scripts/
│   ├── ingestion_db.py           # Raw CSV → SQLite ingestion pipeline
│   └── get_vendor_summary.py    # SQL aggregation → vendor summary table
│
├── notebooks/
│   ├── 01_EDA.ipynb              # Exploratory data analysis
│   ├── 02_Vendor_Analysis.ipynb  # Vendor performance analysis
│   └── 03_ML_Models.ipynb       # K-Means + Random Forest
│
├── outputs/
│   ├── vendor_sales_summary.csv
│   ├── vendor_sales_summary_ml.csv
│   ├── Vendor_Performance_Dashboard.pbix
│   └── Vendor_Performance_Dashboard.pdf
│
├── logs/
│   └── ingestion.log
│
├── requirements.txt
└── README.md
```

---

## Data Description

| File | Rows | Size | Description |
|---|---|---|---|
| sales.csv | 12,837,981 | 1.4GB | Daily sales transactions across all stores |
| purchases.csv | 2,372,474 | ~150MB | Purchase orders from all vendors |
| begin_inventory.csv | 206,529 | ~15MB | Opening inventory snapshot Jan 1 2024 |
| end_inventory.csv | 224,489 | ~17MB | Closing inventory snapshot Dec 31 2024 |
| purchase_prices.csv | 12,261 | ~1MB | Product master with retail and purchase prices |
| vendor_invoice.csv | 5,500 | ~500KB | Vendor freight invoices |

---

## Methodology

### Stage 1 — Data Ingestion (`ingestion_db.py`)
- Chunked loading at 100,000 rows per batch to prevent memory overflow on 1.4GB files
- Dual logging to file and console for live progress monitoring
- Centralized cleaning pipeline applied uniformly across all six tables
- **Runtime: 3 minutes 46 seconds for 15M+ rows**

**Critical fix:** The original codebase assigned full vendor-level freight cost to every brand row — a fundamental accounting error. Replaced with proportional freight allocation:

```
AllocatedFreight = (BrandPurchaseDollars / VendorTotalPurchaseDollars) × VendorTotalFreight
```

### Stage 2 — Vendor Summary Pipeline (`get_vendor_summary.py`)
- SQL CTEs pre-aggregate all metrics at the database layer before pulling into Python
- Strategic indexes on VendorNumber and Brand reduced query runtime from **60s → 31s (48% improvement)**
- Output: **10,514 rows × 27 engineered features**

### Stage 3 — Exploratory Data Analysis (`01_EDA.ipynb`)
- Full profiling of all 6 raw tables before aggregation
- Cross-table null recovery — 1,284 missing city values recovered via store-city mapping (100% recovery)
- Monthly seasonality analysis, vendor concentration, negative profit investigation

### Stage 4 — Vendor Performance Analysis (`02_Vendor_Analysis.ipynb`)
- Pareto concentration analysis (17 vendors drive 80% of revenue)
- Profitability quadrant scatter analysis (margin vs revenue)
- Mann-Whitney U test instead of t-test — non-parametric choice justified by std=447% in margin distribution

### Stage 5 — Machine Learning (`03_ML_Models.ipynb`)

**K-Means Clustering (unsupervised):**
- StandardScaler applied before clustering (distance-based algorithm)
- Optimal k=4 via Elbow Method
- PCA visualization — 72% variance captured in 2 dimensions

**Random Forest Classifier (supervised):**
- Initial model: 100% accuracy — detected and resolved as **data leakage** (GrossProfit directly determines target)
- Retrained on causally valid features only
- Final model: **98% accuracy, 0.987 ROC-AUC**

---

## Key Results

### Headline Metrics

| Metric | Value |
|---|---|
| Total Revenue | $451.62M |
| Total Gross Profit | $130M |
| Total Net Profit | $128.36M |
| Gross Profit Margin (Median) | 30.78% |
| Total Purchase Spend | $321.62M |
| Underperforming SKUs | 1,949 (18.5% of portfolio) |
| Freight as % of Revenue | 0.362% |

### Vendor Concentration
- **17 of 126 vendors (13.5%) drive 80% of total revenue** — more concentrated than classic 80/20
- DIAGEO NORTH AMERICA alone: **15.22% of total revenue** — single vendor dependency risk
- Top 4 vendors account for **38.5% of total revenue**

### Inventory Health
- **83% of vendors have stock turnover below 1.0** — purchased more than they sold in 2024
- JIM BEAM largest absolute overstock — **107,000 units unsold**
- Total inventory value grew **$11.6M (17.1% YoY)**

### Negative Profit Analysis
- **1,949 SKUs with negative gross profit** totalling **-$4.07M loss**
- Worst product: Kilbeggan Irish Whiskey **-$52,002** (severe overstock)
- Russian Standard Vodka **-$29,280** (geopolitical consumer impact)

### Machine Learning Results

**K-Means Clustering:**

| Cluster | Label | Records | Underperforming Rate |
|---|---|---|---|
| 0 | Standard Portfolio | 10,090 | 19.3% |
| 1 | High Volume Giants | 33 | 0.0% |
| 2 | Mid Tier Performers | 364 | 0.0% |
| 3 | Niche High Margin | 27 | 0.0% |

**100% of underperformance risk is concentrated in Cluster 0 — scale is a protective factor.**

**Random Forest Classifier:**

| Metric | Performing | Underperforming |
|---|---|---|
| Precision | 99% | 95% |
| Recall | 99% | 94% |
| F1-Score | 99% | 94% |
| Overall Accuracy | 98% | — |
| ROC-AUC | 0.9873 | — |

**Feature Importance:**

| Feature | Importance |
|---|---|
| StockTurnover | 75.58% |
| AvgUnitsSoldPerDay | 11.10% |
| TotalPurchaseDollars | 4.73% |
| PriceMarkupPct | 4.61% |
| AllocatedFreightCost | 3.95% |

**StockTurnover alone drives 75.6% of predictive power** — inventory turnover monitoring is the single most actionable early warning metric.

---

## Pipeline Performance

| Metric | Value |
|---|---|
| Ingestion runtime | Under 4 minutes for 15M+ rows |
| Query optimization | 48% runtime reduction via strategic indexing |
| Python processing reduction | 60%+ via SQL pre-aggregation |
| Null recovery | 1,284 missing values recovered (100%) |

---

## Key Architectural Decisions

**Chunked ingestion over full load** — 1.4GB file exceeds typical pandas memory. 100K row chunks reduce peak RAM by ~90%.

**SQL pre-aggregation over pandas** — Aggregating 15M rows at the database layer and pulling only 10,514 summary rows into Python reduces overhead by 60%+.

**Proportional freight over flat assignment** — Flat vendor-level freight repeated on every brand row is double-counting. Proportional allocation by purchase dollars is the only financially correct method.

**Mann-Whitney over t-test** — Profit margins have std=447% and extreme outliers. Mann-Whitney makes no normality assumption and is correct for this data.

**Median over mean for margin reporting** — Mean margin is -15.89% due to extreme outliers. Median of 30.78% accurately represents the typical vendor-brand.

**Leakage detection before model acceptance** — Initial Random Forest achieved 100% accuracy using GrossProfit as a feature. Since IsUnderperforming is defined as GrossProfit < 0, this was trivial memorization, not learning.

---

## Tech Stack

| Category | Tools |
|---|---|
| Language | Python 3.11 |
| Database | SQLite, SQLAlchemy |
| Data Processing | Pandas, NumPy |
| Visualization | Matplotlib, Seaborn |
| Machine Learning | Scikit-learn (KMeans, RandomForest, PCA, StandardScaler) |
| Statistical Testing | SciPy (Mann-Whitney U) |
| BI Dashboard | Microsoft Power BI Desktop |
| Environment | Jupyter Notebook, Anaconda |
| Version Control | Git, GitHub |

---

## Setup & Installation

```bash
# 1. Clone the repository
git clone https://github.com/sujaldeb/vendor-analysis-end-to-end.git
cd vendor-analysis-end-to-end

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run ingestion pipeline (requires raw CSV files)
python scripts/ingestion_db.py

# 4. Run vendor summary pipeline
python scripts/get_vendor_summary.py

# 5. Open notebooks in order
jupyter notebook notebooks/01_EDA.ipynb
```

> **Note:** Raw CSV files (1.6GB total) are not included in this repository due to size. The processed output `vendor_sales_summary_ml.csv` is included in `/outputs`.

---

## Dashboard Pages

| Page | Theme | Key Visuals |
|---|---|---|
| Executive Overview | Top-line KPIs | Revenue, Net Profit, Margin, Underperforming SKUs count |
| Vendor Performance | Concentration & margins | Gross margin ranking, Revenue vs Margin quadrant, Freight impact |
| Inventory & Operations | Overstock risk | Stock turnover ranking, Purchase vs Revenue comparison, Volume distribution |
| ML Risk Intelligence | Predictive analytics | Risk score distribution, Cluster segments, High risk vendor table |

---

*Dashboard audience: Procurement Managers & Senior Leadership*
*Data period: Fiscal Year 2024*
*Scope: 80 stores · 126 vendors · 10,514 vendor-brand combinations*
