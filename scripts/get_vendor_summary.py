import os
import logging
import time
import sqlite3
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/get_vendor_summary.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding = "utf-8"
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
DB_PATH = "inventory.db"


# ─────────────────────────────────────────────
# STEP 1 — BUILD RAW SUMMARY VIA SQL
# ─────────────────────────────────────────────

def build_raw_summary(conn):
    """
    Merges purchases, sales, purchase_prices and vendor_invoice
    into one vendor-brand level summary table.

    Key design decisions:
    - Filters out PurchasePrice = 0 (invalid transactions)
    - Filters out SalesDollars = 0 (invalid transactions)
    - Freight is aggregated at vendor level then allocated
      proportionally per brand based on purchase dollars
      (fixes the flat freight bug from the original project)
    """
    logging.info("Building raw summary via SQL...")

    query = """
    WITH

    -- ── Purchase Summary ──────────────────────────────────────────
    -- Aggregates purchases to vendor-brand level
    -- Joins purchase_prices to get the retail price and volume info
    PurchaseSummary AS (
        SELECT
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.Classification,
            pp.Price          AS RetailPrice,
            pp.PurchasePrice  AS UnitPurchasePrice,
            pp.Volume,
            SUM(p.Quantity)   AS TotalPurchaseQuantity,
            SUM(p.Dollars)    AS TotalPurchaseDollars
        FROM purchases p
        JOIN purchase_prices pp
            ON p.Brand = pp.Brand
        WHERE p.PurchasePrice > 0
          AND p.Dollars > 0
        GROUP BY
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.Classification,
            pp.Price,
            pp.PurchasePrice,
            pp.Volume
    ),

    -- ── Sales Summary ─────────────────────────────────────────────
    -- Aggregates sales to vendor-brand level
    SalesSummary AS (
        SELECT
            VendorNo                    AS VendorNumber,
            Brand,
            SUM(SalesQuantity)          AS TotalSalesQuantity,
            SUM(SalesDollars)           AS TotalSalesDollars,
            AVG(SalesPrice)             AS AvgSalesPrice,
            SUM(ExciseTax)              AS TotalExciseTax
        FROM sales
        WHERE SalesDollars > 0
        GROUP BY VendorNo, Brand
    ),

    -- ── Freight Summary ───────────────────────────────────────────
    -- Total freight cost per vendor from vendor_invoice
    FreightSummary AS (
        SELECT
            VendorNumber,
            SUM(Freight) AS TotalFreightCost
        FROM vendor_invoice
        GROUP BY VendorNumber
    ),

    -- ── Vendor Purchase Totals ────────────────────────────────────
    -- Used for proportional freight allocation per brand
    -- (avoids the flat freight bug — every brand gets its fair share)
    VendorPurchaseTotals AS (
        SELECT
            VendorNumber,
            SUM(TotalPurchaseDollars) AS VendorTotalPurchaseDollars
        FROM PurchaseSummary
        GROUP BY VendorNumber
    )

    -- ── Final Join ────────────────────────────────────────────────
    SELECT
        ps.VendorNumber,
        ps.VendorName,
        ps.Brand,
        ps.Description,
        ps.Classification,
        ps.RetailPrice,
        ps.UnitPurchasePrice,
        ps.Volume,
        ps.TotalPurchaseQuantity,
        ps.TotalPurchaseDollars,
        ss.TotalSalesQuantity,
        ss.TotalSalesDollars,
        ss.AvgSalesPrice,
        ss.TotalExciseTax,
        fs.TotalFreightCost                             AS VendorFreightCost,

        -- Proportional freight allocation per brand
        -- Brand's share of vendor's total purchase dollars * vendor's total freight
        ROUND(
            (ps.TotalPurchaseDollars / vpt.VendorTotalPurchaseDollars)
            * fs.TotalFreightCost,
        2) AS AllocatedFreightCost

    FROM PurchaseSummary ps

    LEFT JOIN SalesSummary ss
        ON  ps.VendorNumber = ss.VendorNumber
        AND ps.Brand        = ss.Brand

    LEFT JOIN FreightSummary fs
        ON ps.VendorNumber = fs.VendorNumber

    LEFT JOIN VendorPurchaseTotals vpt
        ON ps.VendorNumber = vpt.VendorNumber

    ORDER BY ps.TotalPurchaseDollars DESC
    """

    df = pd.read_sql_query(query, conn)
    logging.info(f"Raw summary shape: {df.shape}")
    return df


# ─────────────────────────────────────────────
# STEP 2 — CLEAN THE SUMMARY
# ─────────────────────────────────────────────

def clean_summary(df):
    """
    Cleans the raw summary dataframe:
    - Fills nulls appropriately
    - Fixes data types
    - Strips whitespace from string columns
    - Removes records with no sales at all
    """
    logging.info("Cleaning summary data...")

    initial_rows = len(df)

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

    # Convert Volume to numeric (was object type in source data)
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    # Fill nulls — vendors with no sales data get 0
    sales_cols = [
        "TotalSalesQuantity", "TotalSalesDollars",
        "AvgSalesPrice", "TotalExciseTax"
    ]
    df[sales_cols] = df[sales_cols].fillna(0)

    # Fill freight nulls with 0 (vendors not in vendor_invoice)
    df["VendorFreightCost"]    = df["VendorFreightCost"].fillna(0)
    df["AllocatedFreightCost"] = df["AllocatedFreightCost"].fillna(0)

    # Remove rows where both purchase and sales are zero
    df = df[~((df["TotalPurchaseDollars"] == 0) & (df["TotalSalesDollars"] == 0))]

    # Remove rows where sales quantity is zero
    # (products purchased but never sold — not useful for margin analysis)
    df = df[df["TotalSalesQuantity"] > 0]

    removed = initial_rows - len(df)
    logging.info(f"Removed {removed:,} invalid/unsold records")
    logging.info(f"Clean shape: {df.shape}")

    return df


# ─────────────────────────────────────────────
# STEP 3 — FEATURE ENGINEERING
# ─────────────────────────────────────────────

def add_features(df):
    """
    Creates derived metrics for analysis and Power BI dashboard:

    - GrossProfit          : Sales - Purchase cost
    - ProfitMargin %       : Gross profit as % of sales
    - StockTurnover        : How efficiently inventory is being sold
    - SalesPurchaseRatio   : Revenue generated per dollar purchased
    - NetProfit            : Gross profit minus allocated freight
    - NetProfitMargin %    : Net profit as % of sales
    - PriceMarkup %        : How much retail price exceeds purchase price
    - AvgUnitsSoldPerDay   : Average daily sales velocity (full year = 366 days, 2024 was leap year)
    - VolumeCategory       : Groups products by bottle size for segmentation
    - PerformanceTier      : Classifies vendors as High/Mid/Low based on sales
    """
    logging.info("Engineering features...")

    # ── Profitability ──
    df["GrossProfit"] = df["TotalSalesDollars"] - df["TotalPurchaseDollars"]

    df["ProfitMargin%"] = np.where(
        df["TotalSalesDollars"] > 0,
        (df["GrossProfit"] / df["TotalSalesDollars"]) * 100,
        0
    )

    df["NetProfit"] = df["GrossProfit"] - df["AllocatedFreightCost"]

    df["NetProfitMargin%"] = np.where(
        df["TotalSalesDollars"] > 0,
        (df["NetProfit"] / df["TotalSalesDollars"]) * 100,
        0
    )

    # ── Efficiency ──
    df["StockTurnover"] = np.where(
        df["TotalPurchaseQuantity"] > 0,
        df["TotalSalesQuantity"] / df["TotalPurchaseQuantity"],
        0
    )

    df["SalesPurchaseRatio"] = np.where(
        df["TotalPurchaseDollars"] > 0,
        df["TotalSalesDollars"] / df["TotalPurchaseDollars"],
        0
    )

    # ── Pricing ──
    df["PriceMarkup%"] = np.where(
        df["UnitPurchasePrice"] > 0,
        ((df["RetailPrice"] - df["UnitPurchasePrice"]) / df["UnitPurchasePrice"]) * 100,
        0
    )

    # ── Sales Velocity ──
    # 2024 is a leap year so 366 days
    df["AvgUnitsSoldPerDay"] = (df["TotalSalesQuantity"] / 366).round(2)

    # ── Volume Category (bottle size segmentation) ──
    df["VolumeCategory"] = pd.cut(
        df["Volume"],
        bins      = [0, 200, 750, 1000, 1750, float("inf")],
        labels    = ["Miniature(≤200ml)", "Standard(201-750ml)",
                     "Large(751-1000ml)", "Magnum(1001-1750ml)", "Extra Large(>1750ml)"],
        right     = True
    )

    # ── Performance Tier (vendor level) ──
    vendor_sales = df.groupby("VendorNumber")["TotalSalesDollars"].transform("sum")
    high_thresh  = vendor_sales.quantile(0.75)
    low_thresh   = vendor_sales.quantile(0.25)

    df["PerformanceTier"] = pd.cut(
        vendor_sales,
        bins   = [-float("inf"), low_thresh, high_thresh, float("inf")],
        labels = ["Low", "Mid", "High"]
    )  
    
    # ── Underperforming Flag ──────────────────────────────────────
    # EDA Finding (see notebooks/01_EDA.ipynb — Section 3):
    # 18.5% of vendor-brand records show negative gross profit
    # totalling -$4,068,030. Investigation showed these are real
    # business records (overstock, poor demand planning) not data errors.
    # Decision: Flag rather than remove, allowing Power BI users to
    # filter between full view and profitable-only view.
    df['IsUnderperforming'] = df['GrossProfit'] < 0

    logging.info(f"Features added. Final shape: {df.shape}")
    logging.info(f"\nPerformance Tier distribution:\n{df['PerformanceTier'].value_counts()}")
    
    return df


# ─────────────────────────────────────────────
# STEP 4 — SAVE TO DATABASE AND CSV
# ─────────────────────────────────────────────

def save_summary(df, conn):
    """
    Saves the final vendor summary to:
    1. SQLite database (for notebook analysis)
    2. CSV file in outputs/ folder (for Power BI)
    """
    logging.info("Saving vendor summary...")

    os.makedirs("outputs", exist_ok=True)

    # Save to SQLite
    df.to_sql("vendor_sales_summary", conn, if_exists="replace", index=False)
    logging.info(f"Saved to SQLite table [vendor_sales_summary]: {len(df):,} rows")

    # Save to CSV for Power BI
    csv_path = os.path.join("outputs", "vendor_sales_summary.csv")
    df.to_csv(csv_path, index=False)
    logging.info(f"Saved to CSV: {csv_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    start = time.time()

    logging.info("=" * 60)
    logging.info("STARTING VENDOR SUMMARY BUILD")
    logging.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # ── Create indexes for query performance ──────────────────
    # Indexes dramatically speed up JOIN and GROUP BY operations
    # on large tables (purchases: 2.37M rows, sales: 12.8M rows)
    logging.info("Creating indexes for query optimization...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_brand "
                 "ON purchases(Brand)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_vendor "
                 "ON purchases(VendorNumber)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_brand "
                 "ON sales(Brand)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_vendor "
                 "ON sales(VendorNo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invoice_vendor "
                 "ON vendor_invoice(VendorNumber)")
    conn.commit()
    logging.info("Indexes created successfully")

    # Step 1 — Build raw summary from SQL
    df = build_raw_summary(conn)


if __name__ == "__main__":
    main()