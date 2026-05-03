# Liquor Inventory & Vendor Performance Analytics
### End-to-End Data Analytics + Machine Learning Pipeline
**Python · SQLite · Scikit-learn · Power BI**

---

## Problem Statement

A liquor distribution business operating across 80 stores and 126 vendors had no centralized system to evaluate vendor performance, identify underperforming products, or detect overstock risk. Raw transactional data was spread across six disconnected CSV files totalling 15 million+ records and 1.6GB — far too large for manual analysis. Business decisions around purchasing, vendor negotiation and inventory planning were being made without data-driven insights.

**The core business problems were:**
- No visibility into which vendors and products were generating losses
- No system to detect overstock risk before capital was already tied up
- Freight costs were being incorrectly allocated, making per-product margin analysis unreliable
- No way to predict which new products were at risk of underperformance

**Primary dashboard audience:** Procurement managers and senior leadership who need to make vendor negotiation, purchasing volume and inventory planning decisions on a monthly basis.

**The goal** was to build a production-grade analytics pipeline that ingested, cleaned and aggregated all raw data, surfaced actionable business insights through rigorous analysis, and delivered a machine learning model capable of predicting underperformance risk for any vendor-brand combination — all presented through an interactive Power BI dashboard.

---

## Approach

The project was executed in five structured stages:

### Stage 1 — Data Ingestion & Engineering
Built a custom Python pipeline (`ingestion_db.py`) to load all six CSV files into a SQLite database. Large files (1.4GB sales, 150MB purchases) were processed in 100,000-row chunks to prevent memory overflow. A centralized cleaning function handled null removal, type conversions, whitespace stripping and column drops uniformly across all tables. The pipeline completed full ingestion of 15M+ rows in under 4 minutes with dual logging (file + console) for live monitoring.

**Critical fix:** The original codebase assigned the full vendor-level freight cost to every brand row for that vendor — a fundamental accounting error that inflated per-product costs for high-volume vendors and understated them for low-volume ones. This was replaced with a proportional freight allocation model:

```
AllocatedFreight = (Brand Purchase Dollars / Vendor Total Purchase Dollars) × Vendor Total Freight
```

### Stage 2 — Vendor Summary Pipeline
Built a SQL CTE pipeline (`get_vendor_summary.py`) that pre-aggregated all metrics at the database layer before pulling into Python. Four CTEs handled purchase aggregation, sales aggregation, freight allocation and vendor totals respectively. Strategic indexes on VendorNumber and Brand columns across the purchases and sales tables cut query runtime from 60 seconds to 31 seconds — a 48% improvement. The output was a clean 10,514-row vendor-brand summary table with 27 engineered features.

### Stage 3 — Exploratory Data Analysis
A structured EDA notebook (`01_EDA.ipynb`) profiled all six raw tables individually before any aggregation. Every data quality finding was investigated and documented with a business justification before being implemented in the pipeline — creating a fully auditable trail.

**Key EDA findings that drove decisions:**

**Monthly Revenue Seasonality:**
| Month | Sales Revenue | Profit Margin % |
|---|---|---|
| January | ~$31M | 35.89% (drawing down Dec stock) |
| July | $49.7M (summer peak) | ~29% |
| October | ~$38M | 12.62% (lowest — over-purchasing flagged) |
| December | $52.3M (holiday peak) | 49.63% (highest) |

Decision driven: October margin warning was flagged for procurement review — purchasing volumes were not aligned with seasonal demand.

**Monthly Purchase Seasonality:**
- Peak purchasing in July at $32.2M — aligned with summer sales ramp
- December 2023 purchases of $6.9M included in dataset — validated as legitimate carry-over, not an error
- January 2025 invoice dates identified and retained after confirming normal procurement lag

**Vendor Concentration (discovered in EDA, confirmed in analysis):**
- Top 10 vendors by purchase spend account for over 60% of total purchasing
- DIAGEO identified early as dominant vendor requiring special attention

**Inventory Growth Analysis:**
- Total units increased by 666,501 across all stores during 2024
- Total inventory value grew from $68M to $79.7M (+17.1%)
- Finding: purchasing is outpacing sales across most of the portfolio — overstock risk flagged before stock turnover analysis confirmed it

**Negative Profit Discovery:**
- 18.5% of vendor-brand combinations showed negative profit margin totalling -$4.07M
- Investigation revealed this was real business data (overstock, geopolitical impact) not data errors
- Decision: retain all records and create `IsUnderperforming` flag rather than filtering — this became the ML target variable

**Data Quality Decisions Driven by EDA:**
- Store 46 (TYWARDREATH) had 1,284 null City values in end_inventory — recovered via begin_inventory cross-table lookup rather than dropping
- `Approval` column in vendor_invoice was 93% null — dropped at ingestion after EDA confirmed no analytical value
- Mean profit margin (-15.89%) confirmed as misleading — median (30.78%) adopted as standard for all reporting

### Stage 4 — Vendor Performance Analysis
A comprehensive analysis notebook (`02_Vendor_Analysis.ipynb`) examined vendor performance across five dimensions: revenue concentration (Pareto analysis), profitability efficiency (margin vs revenue quadrant), stock turnover efficiency, freight cost impact and statistical significance testing. A Mann-Whitney U test was used instead of a t-test because profit margins were heavily non-normal (std=447%), making parametric tests inappropriate.

### Stage 5 — Machine Learning Models
Built a two-model pipeline (`03_ML_Models.ipynb`) combining unsupervised and supervised learning:

**K-Means Clustering** discovered four natural vendor segments from the data without predefined labels. The optimal k=4 was determined using the Elbow Method. StandardScaler was applied before clustering since K-Means is distance-based and unscaled features like TotalPurchaseDollars would dominate the distance calculations.

**Random Forest Classifier** was then trained to predict underperformance risk. An initial model achieved 100% accuracy — immediately identified as data leakage since GrossProfit and ProfitMargin% directly determine the target variable. After removing the leaking features and retraining on causally valid features only (purchase volume, stock turnover, pricing and sales velocity), the model achieved 98% accuracy and 0.987 ROC-AUC.

Predictions and risk scores were exported back to the master dataset and served to Power BI for predictive visualizations.

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

## Data Quality Issues Resolved

| Issue | Table | Resolution |
|---|---|---|
| 1,284 null City values | end_inventory | Recovered via cross-table store-city mapping from begin_inventory |
| 153 zero purchase price records | purchases | Filtered — cannot allocate cost to zero-price items |
| 2 zero retail price records | purchase_prices | Filtered — cannot calculate margin |
| 55 zero dollar sales | sales | Filtered — likely voids or returns |
| Approval column 93% null | vendor_invoice | Dropped at ingestion — no analytical value |
| Volume column stored as object | purchase_prices | Converted to numeric at ingestion |
| Freight repeated at vendor level | vendor_invoice | Replaced with proportional allocation by purchase dollars |
| Indentation error in original script | get_vendor_summary.py | Fixed — caused silent logic failure |
| Variable name mismatch in original | get_vendor_summary.py | Fixed — caused KeyError at runtime |

---

## Key Results & Metrics

### Headline Metrics

| Metric | Value |
|---|---|
| Total Revenue | $451.62M |
| Total Gross Profit | $130M |
| Total Net Profit (after freight) | $128.36M |
| Profit Margin % (Median) | 30.78% |
| Total Purchase Spend | $321.62M |
| Total Excise Tax | $19M (4.2% of revenue) |
| Freight as % of Revenue | 0.362% |
| Underperforming SKUs | 1,949 (18.5% of portfolio) |
| Total Inventory Value Growth | +$11.6M (17.1% YoY increase) |

> **Note on margin terminology:** The column `ProfitMargin%` in the dataset represents `(SalesDollars - PurchaseDollars) / SalesDollars` — this is the gross profit margin before excise tax and freight deductions. Net profit margin accounts for allocated freight. All Power BI KPI cards are labelled explicitly to match this distinction and avoid stakeholder confusion.

### Pipeline Performance Highlights
- ⚡ Ingested 15M+ rows in **under 4 minutes** using chunked processing
- ⚡ Query runtime reduced by **48%** (60s → 31s) via strategic indexing
- ⚡ Python-side processing reduced by **60%+** via SQL pre-aggregation
- ⚡ Recovered **1,284 missing city values** via cross-table lookup (100% recovery rate)

### Vendor Concentration (Pareto Analysis)
- **17 of 126 vendors (13.5%) drive 80% of total revenue** — more concentrated than classic 80/20
- DIAGEO NORTH AMERICA alone: **15.22% of total revenue** — single vendor dependency risk
- Top 4 vendors account for **38.5% of total revenue**
- Remaining 109 vendors share only **20% of revenue** — procurement should prioritize top 17

### Top 5 Vendors by Revenue
| Rank | Vendor | Revenue | Profit Margin % |
|---|---|---|---|
| 1 | DIAGEO NORTH AMERICA | $67.99M | 27.4% |
| 2 | MARTIGNETTI COMPANIES | $39.33M | 36.1% |
| 3 | PERNOD RICARD USA | $32.06M | 28.8% |
| 4 | JIM BEAM BRANDS | $31.42M | 26.8% |
| 5 | BACARDI USA | $24.85M | 31.2% |

### Top 5 Vendors by Profit Margin % (Revenue > $1M)
| Rank | Vendor | Margin | Revenue |
|---|---|---|---|
| 1 | KOBRAND CORPORATION | 42.3% | $2.79M |
| 2 | TREASURY WINE ESTATES | 39.7% | $4.69M |
| 3 | SOUTHERN WINE & SPIRITS NE | 38.9% | $5.54M |
| 4 | CONSTELLATION BRANDS | 36.7% | $24.22M |
| 5 | MARTIGNETTI COMPANIES | 36.1% | $39.33M |

### Inventory Health (Stock Turnover)
- **83% of vendors (34 of 41) have stock turnover below 1.0** — purchased more than they sold in 2024
- STOLI GROUP worst performer at **0.866 turnover** — geopolitical consumer sentiment impact
- JIM BEAM largest absolute overstock — **107,000 units unsold**
- BACARDI most efficient large vendor at **1.021 turnover**

### Negative Profit Analysis
- **1,949 SKUs with negative profit margin** totalling -$4.07M loss
- MARTIGNETTI leads with **279 negative SKU records**
- Worst single product: Kilbeggan Irish Whiskey **-$52,002** (severe overstock)
- Russian Standard Vodka **-$29,280** (geopolitical consumer impact)

### Statistical Hypothesis Testing
| Parameter | Value |
|---|---|
| Test Used | Mann-Whitney U (non-parametric) |
| Reason | Non-normal distribution, std=447% |
| U-Statistic | 710,991 |
| P-Value | 0.000505 |
| Result | H₀ Rejected — significant difference confirmed |
| Top Vendor Median Margin | 30.92% |
| Low Vendor Median Margin | 25.54% |
| Difference | ~5.4 percentage points |

---

## Machine Learning Results

### K-Means Clustering

| Cluster | Label | Records | Underperforming Rate |
|---|---|---|---|
| 0 | Standard Portfolio | 10,090 | 19.3% |
| 1 | High Volume Giants | 33 | 0.0% |
| 2 | Mid Tier Performers | 364 | 0.0% |
| 3 | Niche High Margin | 27 | 0.0% |

- Optimal k=4 determined by Elbow Method
- PCA visualization: **72% of variance captured in 2 dimensions**
- Key insight: **100% of underperformance risk is concentrated in Cluster 0** — scale is a protective factor against losses

### Random Forest Classifier

| Metric | Performing | Underperforming |
|---|---|---|
| Precision | 99% | 95% |
| Recall | 99% | **94%** |
| F1-Score | 99% | 94% |
| Overall Accuracy | **98%** | — |
| ROC-AUC Score | **0.9873** | — |
| Naive Baseline Accuracy | 81.5% | — |
| Improvement Over Baseline | **+16.5 percentage points** | — |

> **Baseline accuracy context:** A naive model that predicts "Performing" for every record would achieve 81.5% accuracy given the class distribution (81.5% performing, 18.5% underperforming). The Random Forest achieves 98% accuracy — a **16.5 percentage point improvement over the naive baseline**. The ROC-AUC of 0.987 further confirms the model is genuinely discriminating between classes and not simply exploiting class imbalance.

**The model correctly identifies 94% of all underperforming products** with a false positive rate of only 5% — meaning procurement teams can act on model flags with high confidence.

### Feature Importance
| Feature | Importance | Business Meaning |
|---|---|---|
| StockTurnover | **75.58%** | Primary signal — over-purchasing drives losses |
| AvgUnitsSoldPerDay | 11.10% | Slow movers are high risk |
| TotalPurchaseDollars | 4.73% | Purchase scale matters |
| PriceMarkup% | 4.61% | Pricing power provides margin cushion |
| AllocatedFreightCost | 3.95% | High freight erodes margins |
| Cluster | 0.03% | Segment membership minimal incremental value |

**Headline finding: StockTurnover alone drives 75.6% of predictive power** — making inventory turnover monitoring the single most actionable early warning metric for underperformance risk in this business.

### Model Limitations & Production Considerations

> This section should be read by any team considering deploying this model in a production environment.

- **Training data scope:** The model is trained exclusively on 2024 data. Buying patterns, consumer preferences and macroeconomic conditions in 2025 may differ — particularly for vendors sensitive to geopolitical events (e.g. STOLI GROUP) or economic downturns affecting premium spirits.
- **Concept drift risk:** If purchasing strategy changes significantly (e.g. the business deliberately reduces stock turnover to build safety stock), the model's primary feature loses its predictive validity. The model should be retrained on fresh data at minimum annually, ideally quarterly.
- **Seasonal retraining:** Given the strong seasonality in this business (December margin 49.63%, October margin 12.62%), a model trained on full-year data may underperform if used to predict risk during a specific season. Seasonal sub-models could improve precision for quarterly procurement reviews.
- **Cluster stability:** K-Means clusters are not guaranteed to be stable as new vendors and products are added. Re-running clustering annually alongside model retraining is recommended.
- **Causality vs correlation:** High StockTurnover predicts underperformance but does not cause it. The underlying cause is demand planning failure. The model flags risk — root cause investigation still requires human judgment.

---

## Enriched Final Output

**File:** `vendor_sales_summary_ml.csv`

| Property | Value |
|---|---|
| Rows | 10,514 |
| Columns | 31 |
| Null values | 0 |
| ML columns added | Cluster, ClusterLabel, PredictedUnderperforming, UnderperformingRiskScore |

---

## Key Architectural Decisions

**Chunked ingestion over full load** — 1.4GB file exceeds typical pandas memory. 100K row chunks reduce peak RAM usage by ~90% and make the pipeline viable on standard hardware.

**SQL pre-aggregation over pandas** — Aggregating 15M rows at the database layer and pulling only 10,514 summary rows into Python reduces processing overhead by 60%+. The database is better at set operations than pandas at this scale.

**Proportional freight over flat assignment** — Flat vendor-level freight repeated on every brand row is a double-counting error. Proportional allocation by purchase dollars is the only financially correct method.

**Mann-Whitney over t-test** — Profit margins have std=447% and extreme outliers. The t-test assumes normality. Mann-Whitney makes no distributional assumption and is the correct choice for this data.

**Median over mean for margin reporting** — Mean profit margin is -15.89% due to extreme outliers. Median of 30.78% accurately represents the typical vendor-brand. Using mean would systematically mislead stakeholders.

**Flag negative profits rather than remove** — These records represent real business failures (overstock, poor demand planning, geopolitical impacts). Removing them hides the most actionable insights in the dataset.

**Leakage detection before model acceptance** — The initial Random Forest achieved 100% accuracy using GrossProfit as a feature. Since IsUnderperforming is defined as GrossProfit < 0, this was trivial pattern memorization. Removing leaking features and validating feature importance against causal logic is mandatory before trusting any model result.

**Notebooks for reasoning, scripts for automation** — All analytical decisions and business justifications live in notebooks with markdown documentation. Scripts are clean, automated pipelines. Every script fix references the notebook where the issue was first discovered.

---

## Repository Structure

```
vendor-analysis-end-to-end/
│
├── scripts/
│   ├── ingestion_db.py           # Raw CSV → SQLite pipeline
│   └── get_vendor_summary.py    # SQL aggregation → vendor summary
│
├── notebooks/
│   ├── 01_EDA.ipynb              # Exploratory data analysis
│   ├── 02_Vendor_Analysis.ipynb  # Vendor performance analysis
│   └── 03_ML_Models.ipynb       # K-Means + Random Forest
│
├── outputs/
│   ├── vendor_sales_summary.csv
│   └── vendor_sales_summary_ml.csv
│
├── logs/
│   └── ingestion.log
│
├── requirements.txt              # Python dependencies
└── README.md
```

---

## Requirements

Save the following as `requirements.txt` in your project root:

```
pandas==2.2.0
numpy==1.26.0
sqlalchemy==2.0.25
scikit-learn==1.4.0
scipy==1.12.0
matplotlib==3.8.0
seaborn==0.13.2
jupyter==1.0.0
ipykernel==6.29.0
```

To reproduce the environment:
```bash
pip install -r requirements.txt
```

Or using conda:
```bash
conda create -n vendor-analysis python=3.11
conda activate vendor-analysis
pip install -r requirements.txt
```

---

## Tech Stack

| Category | Tools |
|---|---|
| Language | Python 3.11 |
| Database | SQLite, SQLAlchemy |
| Data Processing | Pandas, NumPy |
| Visualization | Matplotlib, Seaborn |
| Machine Learning | Scikit-learn (KMeans, RandomForestClassifier, PCA, StandardScaler) |
| Statistical Testing | SciPy (Mann-Whitney U) |
| BI Dashboard | Microsoft Power BI Desktop 2024.3 |
| Environment | Jupyter Notebook, Anaconda |
| Version Control | Git, GitHub |

---

## One-Line Project Summary

> Built an end-to-end analytics pipeline on 15M+ liquor distribution records — engineering a proportional freight allocation model, surfacing that 17 vendors drive 80% of revenue and 83% of vendors overpurchased in 2024, and training a Random Forest classifier that identifies underperforming products with **94% recall and 0.987 ROC-AUC** — a 16.5 percentage point improvement over the naive baseline — using stock turnover as the dominant risk signal.
