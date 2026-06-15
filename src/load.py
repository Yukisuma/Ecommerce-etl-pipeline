"""
src/load.py — Load phase: Upsert cleaned data into PostgreSQL
"""

import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text, inspect
# pyrefly: ignore [missing-import]
from sqlalchemy.engine import Engine
from typing import Dict

logger = logging.getLogger(__name__)


class Loader:
    """
    Loads cleaned DataFrames into PostgreSQL.
    Uses upsert (INSERT ON CONFLICT DO UPDATE) for idempotent reruns.
    """

    def __init__(self, database_url: str, sql_dir: Path):
        self.database_url = database_url
        self.sql_dir = sql_dir
        self.engine: Engine = None

    def connect(self):
        """Establish connection to the database."""
        self.engine = create_engine(self.database_url, echo=False)
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("  🔌 Database connection established.")

    def initialize_schema(self):
        """Run the schema SQL to create tables if they don't exist."""
        schema_file = self.sql_dir / "schema.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_file, "r") as f:
            schema_sql = f.read()

        with self.engine.begin() as conn:
            conn.execute(text(schema_sql))
        logger.info("  🏗️  Database schema initialized.")

    def upsert_table(self, df: pd.DataFrame, table: str, conflict_col: str):
        """
        Load a DataFrame into a PostgreSQL table using chunked upsert logic.
        For large tables this approach handles reruns gracefully.
        """
        if df.empty:
            logger.warning(f"  ⚠️  Skipping empty DataFrame for table: {table}")
            return

        # Write to a temp table first, then upsert
        temp_table = f"_tmp_{table}"
        df.to_sql(temp_table, self.engine, if_exists="replace", index=False, method="multi", chunksize=500)

        # Build upsert SQL dynamically
        columns = list(df.columns)
        col_list = ", ".join(f'"{c}"' for c in columns)
        update_set = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in columns if c != conflict_col
        )

        upsert_sql = f"""
            INSERT INTO {table} ({col_list})
            SELECT {col_list} FROM {temp_table}
            ON CONFLICT ("{conflict_col}") DO UPDATE SET {update_set};
            DROP TABLE IF EXISTS {temp_table};
        """

        with self.engine.begin() as conn:
            conn.execute(text(upsert_sql))

        logger.info(f"  📤 Upserted {len(df):,} rows → table '{table}'")

    def save_processed_csv(self, df: pd.DataFrame, name: str, processed_dir: Path):
        """Save cleaned DataFrame as CSV for audit trail."""
        filepath = processed_dir / f"{name}_cleaned.csv"
        df.to_csv(filepath, index=False)
        logger.info(f"  💾 Saved processed CSV: {filepath.name}")

    def compute_and_load_daily_summary(self):
        """
        Compute the daily_sales_summary table using SQL aggregation.
        This is the core analytics table used for reporting.
        """
        summary_sql = """
            INSERT INTO daily_sales_summary (
                report_date, total_orders, completed_orders, cancelled_orders,
                total_gross_revenue, total_discount_amount, total_net_revenue,
                total_units_sold, avg_order_value, top_channel, top_category
            )
            SELECT
                o.order_date::date                                      AS report_date,
                COUNT(DISTINCT o.order_id)                              AS total_orders,
                COUNT(DISTINCT CASE WHEN o.status = 'completed' THEN o.order_id END) AS completed_orders,
                COUNT(DISTINCT CASE WHEN o.status = 'cancelled' THEN o.order_id END) AS cancelled_orders,
                ROUND(SUM(o.gross_revenue)::numeric, 2)                 AS total_gross_revenue,
                ROUND(SUM(o.discount_amount)::numeric, 2)               AS total_discount_amount,
                ROUND(SUM(o.net_revenue)::numeric, 2)                   AS total_net_revenue,
                SUM(o.quantity)                                         AS total_units_sold,
                ROUND(AVG(o.net_revenue)::numeric, 2)                   AS avg_order_value,
                (
                    SELECT channel FROM fact_orders
                    WHERE order_date::date = o.order_date::date
                    GROUP BY channel ORDER BY COUNT(*) DESC LIMIT 1
                )                                                        AS top_channel,
                (
                    SELECT p.category FROM fact_orders fo2
                    JOIN dim_products p ON fo2.product_id = p.product_id
                    WHERE fo2.order_date::date = o.order_date::date
                    GROUP BY p.category ORDER BY SUM(fo2.net_revenue) DESC LIMIT 1
                )                                                        AS top_category
            FROM fact_orders o
            GROUP BY o.order_date::date
            ON CONFLICT (report_date) DO UPDATE SET
                total_orders         = EXCLUDED.total_orders,
                completed_orders     = EXCLUDED.completed_orders,
                cancelled_orders     = EXCLUDED.cancelled_orders,
                total_gross_revenue  = EXCLUDED.total_gross_revenue,
                total_discount_amount= EXCLUDED.total_discount_amount,
                total_net_revenue    = EXCLUDED.total_net_revenue,
                total_units_sold     = EXCLUDED.total_units_sold,
                avg_order_value      = EXCLUDED.avg_order_value,
                top_channel          = EXCLUDED.top_channel,
                top_category         = EXCLUDED.top_category,
                updated_at           = NOW();
        """
        with self.engine.begin() as conn:
            conn.execute(text(summary_sql))
        logger.info("  📊 Daily sales summary computed and loaded.")

    def load_all(
        self, cleaned: Dict[str, pd.DataFrame], processed_dir: Path
    ):
        """Full load sequence: connect → schema → upsert → summary."""
        logger.info("=" * 60)
        logger.info("📦  LOAD PHASE — Persisting Data to PostgreSQL")
        logger.info("=" * 60)

        self.connect()
        self.initialize_schema()

        # Map dataset names to (table_name, primary_key)
        load_map = {
            "products": ("dim_products", "product_id"),
            "customers": ("dim_customers", "customer_id"),
            "orders": ("fact_orders", "order_id"),
            "returns": ("fact_returns", "return_id"),
        }

        for name, (table, pk) in load_map.items():
            df = cleaned[name]

            # Filter returns to only include order_ids that exist in fact_orders
            if name == "returns" and "order_id" in df.columns:
                with self.engine.connect() as conn:
                    valid_orders = pd.read_sql(
                        text("SELECT order_id FROM fact_orders"), conn
                    )["order_id"].tolist()
                before = len(df)
                df = df[df["order_id"].isin(valid_orders)].copy()
                dropped = before - len(df)
                if dropped > 0:
                    logger.warning(
                        f"  ⚠️  Dropped {dropped} return(s) with orphaned order_id "
                        f"(order not in fact_orders)"
                    )

            self.upsert_table(df, table, pk)
            self.save_processed_csv(df, name, processed_dir)

        self.compute_and_load_daily_summary()
        logger.info("  ✅ Load phase complete.")
