"""
tests/test_pipeline.py — Unit tests for the ETL pipeline
Run: python -m pytest tests/ -v
"""

# pyrefly: ignore [missing-import]
import pytest
import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform import Transformer

# ─── Shared Transformer Instance ─────────────────────────────────────────────

@pytest.fixture
def transformer():
    return Transformer(
        valid_statuses={"completed", "pending", "cancelled", "refunded"},
        valid_channels={"website", "mobile_app", "marketplace", "in_store"},
        max_discount=70.0,
        min_price=0.01,
    )


# ─── Products Tests ───────────────────────────────────────────────────────────

class TestProductCleaning:

    def test_removes_negative_prices(self, transformer):
        df = pd.DataFrame([{
            "product_id": "PROD0001", "name": "Test Tee", "category": "Tops",
            "brand": "Zara", "cost_price": "-500", "sell_price": "-1200",
            "stock_qty": "100"
        }])
        result = transformer.clean_products(df)
        assert result.iloc[0]["sell_price"] > 0
        assert result.iloc[0]["cost_price"] > 0

    def test_removes_duplicate_products(self, transformer):
        df = pd.DataFrame([
            {"product_id": "PROD0001", "name": "Tee", "category": "Tops",
             "brand": "Zara", "cost_price": "500", "sell_price": "1200", "stock_qty": "100"},
            {"product_id": "PROD0001", "name": "Tee Duplicate", "category": "Tops",
             "brand": "Zara", "cost_price": "500", "sell_price": "1200", "stock_qty": "100"},
        ])
        result = transformer.clean_products(df)
        assert len(result) == 1

    def test_fills_null_stock_with_zero(self, transformer):
        df = pd.DataFrame([{
            "product_id": "PROD0002", "name": "Jeans", "category": "Bottoms",
            "brand": "Levi's", "cost_price": "800", "sell_price": "2000",
            "stock_qty": ""
        }])
        result = transformer.clean_products(df)
        assert result.iloc[0]["stock_qty"] == 0

    def test_computes_profit_margin(self, transformer):
        df = pd.DataFrame([{
            "product_id": "PROD0003", "name": "Dress", "category": "Dresses",
            "brand": "Mango", "cost_price": "500", "sell_price": "1000",
            "stock_qty": "50"
        }])
        result = transformer.clean_products(df)
        assert result.iloc[0]["profit_margin_pct"] == pytest.approx(50.0)

    def test_drops_rows_with_null_product_id(self, transformer):
        df = pd.DataFrame([
            {"product_id": "", "name": "Ghost", "category": "Tops",
             "brand": "X", "cost_price": "100", "sell_price": "200", "stock_qty": "10"},
            {"product_id": "PROD0004", "name": "Real", "category": "Tops",
             "brand": "Y", "cost_price": "100", "sell_price": "200", "stock_qty": "10"},
        ])
        # Convert empty string to NaN to simulate null
        df["product_id"] = df["product_id"].replace("", np.nan)
        result = transformer.clean_products(df)
        assert len(result) == 1
        assert result.iloc[0]["product_id"] == "PROD0004"


# ─── Customer Tests ───────────────────────────────────────────────────────────

class TestCustomerCleaning:

    def _base_customer(self, **kwargs):
        base = {
            "customer_id": "CUST00001", "first_name": "Arjun", "last_name": "Sharma",
            "email": "arjun@example.com", "city": "Mumbai", "country": "India",
            "signup_date": "2024-01-15", "gender": "Male", "age_group": "25-34"
        }
        base.update(kwargs)
        return pd.DataFrame([base])

    def test_invalid_email_nulled(self, transformer):
        df = self._base_customer(email="not-an-email")
        result = transformer.clean_customers(df)
        assert pd.isna(result.iloc[0]["email"])

    def test_valid_email_preserved(self, transformer):
        df = self._base_customer(email="valid@domain.co.in")
        result = transformer.clean_customers(df)
        assert result.iloc[0]["email"] == "valid@domain.co.in"

    def test_full_name_computed(self, transformer):
        df = self._base_customer(first_name="priya", last_name="patel")
        result = transformer.clean_customers(df)
        assert result.iloc[0]["full_name"] == "Priya Patel"

    def test_removes_duplicate_customer_ids(self, transformer):
        row = {"customer_id": "CUST00001", "first_name": "A", "last_name": "B",
               "email": "a@b.com", "city": "Delhi", "country": "India",
               "signup_date": "2024-01-01", "gender": "Male", "age_group": "18-24"}
        df = pd.DataFrame([row, row])
        result = transformer.clean_customers(df)
        assert len(result) == 1

    def test_invalid_signup_date_becomes_nat(self, transformer):
        df = self._base_customer(signup_date="not-a-date")
        result = transformer.clean_customers(df)
        assert pd.isna(result.iloc[0]["signup_date"])


# ─── Order Tests ──────────────────────────────────────────────────────────────

class TestOrderCleaning:

    def _base_order(self, **kwargs):
        base = {
            "order_id": "ORD000001", "customer_id": "CUST00001",
            "product_id": "PROD0001", "quantity": "2",
            "unit_price": "1500.00", "discount_pct": "10",
            "order_date": "2024-06-01", "status": "completed",
            "channel": "website"
        }
        base.update(kwargs)
        return pd.DataFrame([base])

    def test_revenue_computed_correctly(self, transformer):
        df = self._base_order(quantity="3", unit_price="1000", discount_pct="20")
        result = transformer.clean_orders(df)
        assert result.iloc[0]["gross_revenue"] == 3000.0
        assert result.iloc[0]["discount_amount"] == 600.0
        assert result.iloc[0]["net_revenue"] == 2400.0

    def test_invalid_status_corrected(self, transformer):
        df = self._base_order(status="GARBAGE")
        result = transformer.clean_orders(df)
        assert result.iloc[0]["status"] == "pending"

    def test_invalid_channel_corrected(self, transformer):
        df = self._base_order(channel="UNKNOWN")
        result = transformer.clean_orders(df)
        assert result.iloc[0]["channel"] == "website"

    def test_zero_quantity_dropped(self, transformer):
        df = self._base_order(quantity="0")
        result = transformer.clean_orders(df)
        assert len(result) == 0

    def test_missing_price_dropped(self, transformer):
        df = self._base_order(unit_price="")
        result = transformer.clean_orders(df)
        assert len(result) == 0

    def test_duplicate_order_ids_removed(self, transformer):
        df = pd.concat([self._base_order(), self._base_order()])
        result = transformer.clean_orders(df)
        assert len(result) == 1

    def test_excessive_discount_clamped(self, transformer):
        df = self._base_order(discount_pct="99")
        result = transformer.clean_orders(df)
        assert result.iloc[0]["discount_pct"] <= 70.0

    def test_time_dimensions_extracted(self, transformer):
        df = self._base_order(order_date="2024-07-15")
        result = transformer.clean_orders(df)
        assert result.iloc[0]["order_year"] == 2024
        assert result.iloc[0]["order_month"] == 7
        assert result.iloc[0]["order_month_name"] == "July"
        assert result.iloc[0]["order_day_of_week"] == "Monday"


# ─── Return Tests ─────────────────────────────────────────────────────────────

class TestReturnCleaning:

    def test_removes_duplicate_returns(self, transformer):
        row = {
            "return_id": "RET00001", "order_id": "ORD000001",
            "product_id": "PROD0001", "reason": "Wrong size",
            "return_date": "2024-06-10", "refund_amount": "800"
        }
        df = pd.DataFrame([row, row])
        result = transformer.clean_returns(df)
        assert len(result) == 1

    def test_null_refund_filled_with_zero(self, transformer):
        df = pd.DataFrame([{
            "return_id": "RET00002", "order_id": "ORD000002",
            "product_id": "PROD0002", "reason": "Defective",
            "return_date": "2024-06-10", "refund_amount": ""
        }])
        result = transformer.clean_returns(df)
        assert result.iloc[0]["refund_amount"] == 0.0

    def test_reason_title_cased(self, transformer):
        df = pd.DataFrame([{
            "return_id": "RET00003", "order_id": "ORD000003",
            "product_id": "PROD0003", "reason": "wrong size",
            "return_date": "2024-06-10", "refund_amount": "500"
        }])
        result = transformer.clean_returns(df)
        assert result.iloc[0]["reason"] == "Wrong Size"
