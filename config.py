"""
config.py — Central configuration for the E-Commerce Data Pipeline
"""

import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = BASE_DIR / os.getenv("RAW_DATA_DIR", "data/raw")
PROCESSED_DATA_DIR = BASE_DIR / os.getenv("PROCESSED_DATA_DIR", "data/processed")
REPORTS_DIR = BASE_DIR / os.getenv("REPORTS_DIR", "reports")
SQL_DIR = BASE_DIR / "sql"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
for _dir in [RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─── Database Configuration ───────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "ecommerce_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# ─── Pipeline Settings ────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "pipeline.log"

# ─── Expected CSV columns ─────────────────────────────────────────────────────
EXPECTED_COLUMNS = {
    "orders": [
        "order_id", "customer_id", "product_id", "quantity",
        "unit_price", "discount_pct", "order_date", "status", "channel"
    ],
    "products": [
        "product_id", "name", "category", "brand",
        "cost_price", "sell_price", "stock_qty"
    ],
    "customers": [
        "customer_id", "first_name", "last_name", "email",
        "city", "country", "signup_date", "gender", "age_group"
    ],
    "returns": [
        "return_id", "order_id", "product_id", "reason",
        "return_date", "refund_amount"
    ],
}

# ─── Business Rules ───────────────────────────────────────────────────────────
VALID_ORDER_STATUSES = {"completed", "pending", "cancelled", "refunded"}
VALID_CHANNELS = {"website", "mobile_app", "marketplace", "in_store"}
MAX_DISCOUNT_PCT = 70.0
MIN_PRICE = 0.01
