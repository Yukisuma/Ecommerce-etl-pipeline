"""
src/transform.py — Transform phase: Clean, validate, and enrich data
"""

import logging
import re
# pyrefly: ignore [missing-import]
import numpy as np
import pandas as pd
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class TransformationReport:
    """Tracks all changes made during transformation for auditability."""

    def __init__(self):
        self.issues: Dict[str, list] = {}

    def log(self, dataset: str, issue: str, count: int):
        if dataset not in self.issues:
            self.issues[dataset] = []
        self.issues[dataset].append({"issue": issue, "rows_affected": count})
        if count > 0:
            logger.warning(f"  ⚠️  [{dataset}] {issue}: {count} row(s)")

    def summary(self) -> str:
        lines = ["\n📋 Data Quality Report:"]
        for ds, issues in self.issues.items():
            lines.append(f"\n  [{ds.upper()}]")
            for item in issues:
                lines.append(f"    • {item['issue']}: {item['rows_affected']} row(s)")
        return "\n".join(lines)


class Transformer:
    """
    Cleans and enriches raw DataFrames.
    Each dataset has its own dedicated cleaning method.
    """

    def __init__(self, valid_statuses: set, valid_channels: set,
                 max_discount: float, min_price: float):
        self.valid_statuses = valid_statuses
        self.valid_channels = valid_channels
        self.max_discount = max_discount
        self.min_price = min_price
        self.report = TransformationReport()

    # ─── Products ─────────────────────────────────────────────────────────────

    def clean_products(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("  🔧 Cleaning products...")
        original_len = len(df)

        # Cast types
        df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce")
        df["sell_price"] = pd.to_numeric(df["sell_price"], errors="coerce")
        df["stock_qty"] = pd.to_numeric(df["stock_qty"], errors="coerce").fillna(0).astype(int)

        # Fix negative prices (business error)
        neg_prices = (df["sell_price"] < 0) | (df["cost_price"] < 0)
        self.report.log("products", "Negative prices fixed (took absolute value)", neg_prices.sum())
        df.loc[df["sell_price"] < 0, "sell_price"] = df.loc[df["sell_price"] < 0, "sell_price"].abs()
        df.loc[df["cost_price"] < 0, "cost_price"] = df.loc[df["cost_price"] < 0, "cost_price"].abs()

        # Drop rows with null critical fields
        null_rows = df[["product_id", "name", "category", "sell_price"]].isnull().any(axis=1)
        self.report.log("products", "Rows dropped (null critical fields)", null_rows.sum())
        df = df[~null_rows].copy()

        # Remove duplicates
        dupes = df.duplicated(subset=["product_id"])
        self.report.log("products", "Duplicate product_ids removed", dupes.sum())
        df = df.drop_duplicates(subset=["product_id"])

        # Normalize strings
        df["name"] = df["name"].str.strip().str.title()
        df["category"] = df["category"].str.strip().str.title()
        df["brand"] = df["brand"].str.strip()

        # Derived: profit margin
        df["profit_margin_pct"] = ((df["sell_price"] - df["cost_price"]) / df["sell_price"] * 100).round(2)

        logger.info(f"    → products: {original_len} → {len(df)} rows after cleaning")
        return df

    # ─── Customers ────────────────────────────────────────────────────────────

    def clean_customers(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("  🔧 Cleaning customers...")
        original_len = len(df)

        # Fix bad emails
        email_pattern = r"^[\w\.\+\-]+@[\w\-]+(\.[\w\-]+)*\.[a-zA-Z]{2,}$"
        bad_emails = ~df["email"].str.match(email_pattern, na=False)
        self.report.log("customers", "Invalid emails set to NULL", bad_emails.sum())
        df.loc[bad_emails, "email"] = np.nan

        # Parse dates
        df["signup_date"] = pd.to_datetime(df["signup_date"], errors="coerce")
        null_dates = df["signup_date"].isnull()
        self.report.log("customers", "Missing/invalid signup_date rows", null_dates.sum())

        # Drop rows with null customer_id
        no_id = df["customer_id"].isnull() | (df["customer_id"].str.strip() == "")
        self.report.log("customers", "Rows dropped (no customer_id)", no_id.sum())
        df = df[~no_id].copy()

        # Remove duplicates
        dupes = df.duplicated(subset=["customer_id"])
        self.report.log("customers", "Duplicate customer_ids removed", dupes.sum())
        df = df.drop_duplicates(subset=["customer_id"])

        # Normalize name fields
        df["first_name"] = df["first_name"].str.strip().str.title()
        df["last_name"] = df["last_name"].str.strip().str.title()
        df["full_name"] = df["first_name"] + " " + df["last_name"]
        df["country"] = df["country"].str.strip()
        df["city"] = df["city"].str.strip().str.title()

        logger.info(f"    → customers: {original_len} → {len(df)} rows after cleaning")
        return df

    # ─── Orders ───────────────────────────────────────────────────────────────

    def clean_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("  🔧 Cleaning orders...")
        original_len = len(df)

        # Cast numeric types
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
        df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
        df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)

        # Parse dates
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

        # Drop rows where critical fields are null
        critical_null = df[["order_id", "customer_id", "product_id", "order_date"]].isnull().any(axis=1)
        self.report.log("orders", "Rows dropped (null critical fields)", critical_null.sum())
        df = df[~critical_null].copy()

        # Drop rows with missing price or zero/negative quantity
        bad_price = df["unit_price"].isnull() | (df["unit_price"] < self.min_price)
        self.report.log("orders", "Rows dropped (missing/invalid unit_price)", bad_price.sum())
        df = df[~bad_price].copy()

        bad_qty = df["quantity"].isnull() | (df["quantity"] <= 0)
        self.report.log("orders", "Rows dropped (zero/negative quantity)", bad_qty.sum())
        df = df[~bad_qty].copy()

        # Fix invalid statuses → set to 'pending'
        invalid_status = ~df["status"].str.lower().isin(self.valid_statuses)
        self.report.log("orders", "Invalid statuses corrected to 'pending'", invalid_status.sum())
        df.loc[invalid_status, "status"] = "pending"
        df["status"] = df["status"].str.lower()

        # Fix invalid channels
        invalid_channel = ~df["channel"].str.lower().isin(self.valid_channels)
        self.report.log("orders", "Invalid channels corrected to 'website'", invalid_channel.sum())
        df.loc[invalid_channel, "channel"] = "website"
        df["channel"] = df["channel"].str.lower()

        # Clamp discount percentage
        over_discount = df["discount_pct"] > self.max_discount
        self.report.log("orders", f"Discounts clamped to {self.max_discount}%", over_discount.sum())
        df.loc[over_discount, "discount_pct"] = self.max_discount

        # Remove duplicate order_ids (keep first)
        dupes = df.duplicated(subset=["order_id"])
        self.report.log("orders", "Duplicate order_ids removed", dupes.sum())
        df = df.drop_duplicates(subset=["order_id"])

        # Derived fields
        df["quantity"] = df["quantity"].astype(int)
        df["gross_revenue"] = (df["unit_price"] * df["quantity"]).round(2)
        df["discount_amount"] = (df["gross_revenue"] * df["discount_pct"] / 100).round(2)
        df["net_revenue"] = (df["gross_revenue"] - df["discount_amount"]).round(2)

        # Extract time dimensions
        df["order_year"] = df["order_date"].dt.year
        df["order_month"] = df["order_date"].dt.month
        df["order_month_name"] = df["order_date"].dt.strftime("%B")
        df["order_week"] = df["order_date"].dt.isocalendar().week.astype(int)
        df["order_day_of_week"] = df["order_date"].dt.strftime("%A")

        logger.info(f"    → orders: {original_len} → {len(df)} rows after cleaning")
        return df

    # ─── Returns ──────────────────────────────────────────────────────────────

    def clean_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("  🔧 Cleaning returns...")
        original_len = len(df)

        df["refund_amount"] = pd.to_numeric(df["refund_amount"], errors="coerce").fillna(0)
        df["return_date"] = pd.to_datetime(df["return_date"], errors="coerce")

        null_rows = df[["return_id", "order_id"]].isnull().any(axis=1)
        self.report.log("returns", "Rows dropped (null critical fields)", null_rows.sum())
        df = df[~null_rows].copy()

        dupes = df.duplicated(subset=["return_id"])
        self.report.log("returns", "Duplicate return_ids removed", dupes.sum())
        df = df.drop_duplicates(subset=["return_id"])

        df["reason"] = df["reason"].str.strip().str.title()

        logger.info(f"    → returns: {original_len} → {len(df)} rows after cleaning")
        return df

    # ─── Orchestrator ─────────────────────────────────────────────────────────

    def transform_all(
        self, datasets: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict[str, pd.DataFrame], TransformationReport]:
        logger.info("=" * 60)
        logger.info("⚙️   TRANSFORM PHASE — Cleaning & Enriching Data")
        logger.info("=" * 60)

        cleaned = {
            "products": self.clean_products(datasets["products"]),
            "customers": self.clean_customers(datasets["customers"]),
            "orders": self.clean_orders(datasets["orders"]),
            "returns": self.clean_returns(datasets["returns"]),
        }

        logger.info(self.report.summary())
        logger.info("  ✅ Transformation complete.")
        return cleaned, self.report
