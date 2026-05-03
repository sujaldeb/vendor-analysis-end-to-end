import os
import logging
import time
import sqlite3
import pandas as pd

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/ingestion_db.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)

# Print logs to console so you can see progress live
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
DATA_DIR   = "data"
DB_PATH    = "inventory.db"

# Chunk size for large files (number of rows per chunk)
CHUNK_SIZE = 100_000

# Columns to drop per table (useless or near-empty columns)
COLUMNS_TO_DROP = {
    "vendor_invoice": ["Approval"],
}

# Date columns to parse per table
DATE_COLUMNS = {
    "vendor_invoice": ["InvoiceDate", "PODate", "PayDate"],
    "purchases":      ["PODate", "ReceivingDate", "InvoiceDate", "PayDate"],
    "sales":          ["SalesDate"],
    "begin_inventory": ["startDate"],
    "end_inventory":   ["endDate"],
}

# Tables that are large and need chunked loading
LARGE_FILES = ["sales.csv", "purchases.csv"]


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def clean_string_columns(df):
    """Strip leading/trailing whitespace from all string columns."""
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())
    return df


def convert_date_columns(df, table_name):
    """Convert known date columns from string to datetime."""
    cols = DATE_COLUMNS.get(table_name, [])
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def drop_unwanted_columns(df, table_name):
    """Drop columns that are not useful for analysis."""
    cols = COLUMNS_TO_DROP.get(table_name, [])
    cols_present = [c for c in cols if c in df.columns]
    if cols_present:
        df = df.drop(columns=cols_present)
        logging.info(f"  Dropped columns {cols_present} from {table_name}")
    return df


def fix_volume_column(df):
    """Convert Volume column from string/object to numeric if present."""
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
    return df


def apply_cleaning(df, table_name):
    """Apply all cleaning steps to a dataframe."""
    df = clean_string_columns(df)
    df = convert_date_columns(df, table_name)
    df = drop_unwanted_columns(df, table_name)
    df = fix_volume_column(df)
    return df


# ─────────────────────────────────────────────
# INGESTION FUNCTIONS
# ─────────────────────────────────────────────

def ingest_standard(filepath, table_name, conn):
    """
    Load a regular-sized CSV fully into memory,
    clean it, and write to SQLite.
    """
    logging.info(f"Loading {table_name} (standard load)...")
    df = pd.read_csv(filepath)
    logging.info(f"  Raw shape: {df.shape}")

    df = apply_cleaning(df, table_name)

    null_summary = df.isnull().sum()
    null_cols = null_summary[null_summary > 0]
    if not null_cols.empty:
        logging.info(f"  Nulls after cleaning:\n{null_cols}")

    df.to_sql(table_name, conn, if_exists="replace", index=False)
    logging.info(f"  Ingested {len(df):,} rows into [{table_name}]")


def ingest_chunked(filepath, table_name, conn):
    """
    Load a large CSV in chunks to avoid memory issues,
    clean each chunk, and write to SQLite incrementally.
    """
    logging.info(f"Loading {table_name} (chunked load, chunk size = {CHUNK_SIZE:,})...")

    total_rows = 0
    first_chunk = True

    for i, chunk in enumerate(pd.read_csv(filepath, chunksize=CHUNK_SIZE)):
        chunk = apply_cleaning(chunk, table_name)

        # First chunk replaces the table; subsequent chunks append
        if_exists = "replace" if first_chunk else "append"
        chunk.to_sql(table_name, conn, if_exists=if_exists, index=False)

        total_rows += len(chunk)
        first_chunk = False

        if (i + 1) % 10 == 0:
            logging.info(f"  Processed {total_rows:,} rows so far...")

    logging.info(f"  Ingested {total_rows:,} total rows into [{table_name}]")


def load_all_data():
    """
    Main function — iterates over all CSVs in the data directory
    and loads them into the SQLite database.
    """
    if not os.path.exists(DATA_DIR):
        logging.error(f"Data directory '{DATA_DIR}' not found. Exiting.")
        return

    conn = sqlite3.connect(DB_PATH)
    logging.info(f"Connected to database: {DB_PATH}")
    logging.info("=" * 60)

    start_total = time.time()

    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]

    if not csv_files:
        logging.warning(f"No CSV files found in '{DATA_DIR}'. Exiting.")
        conn.close()
        return

    logging.info(f"Found {len(csv_files)} CSV files: {csv_files}")
    logging.info("=" * 60)

    for file in csv_files:
        table_name = file[:-4]  # strip .csv
        filepath   = os.path.join(DATA_DIR, file)
        start      = time.time()

        try:
            if file in LARGE_FILES:
                ingest_chunked(filepath, table_name, conn)
            else:
                ingest_standard(filepath, table_name, conn)

            elapsed = (time.time() - start) / 60
            logging.info(f"  Time taken: {elapsed:.2f} minutes")
            logging.info("-" * 60)

        except Exception as e:
            logging.error(f"FAILED to ingest {file}: {e}", exc_info=True)

    # ── Verify all tables loaded correctly ──
    logging.info("=" * 60)
    logging.info("VERIFICATION — Tables in database:")
    tables = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'", conn
    )
    for t in tables["name"]:
        count = pd.read_sql_query(f"SELECT COUNT(*) as cnt FROM {t}", conn)
        logging.info(f"  {t}: {count['cnt'].iloc[0]:,} rows")

    total_elapsed = (time.time() - start_total) / 60
    logging.info("=" * 60)
    logging.info(f"ALL INGESTION COMPLETE — Total time: {total_elapsed:.2f} minutes")

    conn.close()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    load_all_data()