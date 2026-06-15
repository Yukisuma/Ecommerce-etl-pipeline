"""
generate_data.py — Generates realistic sample CSV data for the pipeline.
Run this first: python generate_data.py
"""

import random
import csv
import os
from pathlib import Path
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from faker import Faker # type: ignore

fake = Faker()
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Constants ────────────────────────────────────────────────────────────────
NUM_CUSTOMERS = 500
NUM_PRODUCTS = 80
NUM_ORDERS = 3000
NUM_RETURNS = 200

BRANDS = [
    "Zara", "H&M", "Mango", "Forever 21", "UNIQLO",
    "Levi's", "Tommy Hilfiger", "Calvin Klein", "Puma", "Adidas"
]

CATEGORIES = [
    "Tops", "Bottoms", "Dresses", "Outerwear", "Footwear",
    "Accessories", "Activewear", "Formal", "Ethnic", "Swimwear"
]

CHANNELS = ["website", "mobile_app", "marketplace", "in_store"]
STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
RETURN_REASONS = [
    "Wrong size", "Defective product", "Changed mind",
    "Not as described", "Arrived late", "Better price elsewhere"
]

AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]

CITIES = [
    ("Mumbai", "India"), ("Delhi", "India"), ("Bangalore", "India"),
    ("Chennai", "India"), ("Hyderabad", "India"), ("Pune", "India"),
    ("London", "UK"), ("Manchester", "UK"), ("Birmingham", "UK"),
    ("Dubai", "UAE"), ("Abu Dhabi", "UAE"), ("Singapore", "Singapore"),
    ("New York", "USA"), ("Los Angeles", "USA"), ("Chicago", "USA"),
]


def random_date(start_days_ago=365, end_days_ago=0):
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    return start + (end - start) * random.random()


# ─── Generate Products ────────────────────────────────────────────────────────
def generate_products():
    products = []
    adjectives = ["Premium", "Classic", "Slim Fit", "Relaxed", "Vintage",
                  "Modern", "Essential", "Luxury", "Casual", "Sports"]
    for i in range(1, NUM_PRODUCTS + 1):
        category = random.choice(CATEGORIES)
        brand = random.choice(BRANDS)
        adj = random.choice(adjectives)
        name = f"{brand} {adj} {category[:-1] if category.endswith('s') else category}"
        cost = round(random.uniform(200, 2000), 2)
        sell = round(cost * random.uniform(1.5, 3.5), 2)
        stock = random.randint(0, 500)
        # Introduce some dirty data
        if random.random() < 0.02:
            sell = -sell  # bad price
        if random.random() < 0.01:
            stock = None  # missing stock
        products.append({
            "product_id": f"PROD{i:04d}",
            "name": name,
            "category": category,
            "brand": brand,
            "cost_price": cost,
            "sell_price": sell,
            "stock_qty": stock,
        })
    return products


# ─── Generate Customers ───────────────────────────────────────────────────────
def generate_customers():
    customers = []
    emails_seen = set()
    for i in range(1, NUM_CUSTOMERS + 1):
        city_info = random.choice(CITIES)
        email = fake.email()
        while email in emails_seen:
            email = fake.email()
        emails_seen.add(email)
        signup = random_date(730, 30)
        # Introduce dirty data
        if random.random() < 0.015:
            email = "invalid-email"  # bad email
        if random.random() < 0.02:
            signup = None  # missing date
        customers.append({
            "customer_id": f"CUST{i:05d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": email,
            "city": city_info[0],
            "country": city_info[1],
            "signup_date": signup.strftime("%Y-%m-%d") if signup else "",
            "gender": random.choice(GENDERS),
            "age_group": random.choice(AGE_GROUPS),
        })
    return customers


# ─── Generate Orders ──────────────────────────────────────────────────────────
def generate_orders(products, customers):
    orders = []
    product_ids = [p["product_id"] for p in products]
    customer_ids = [c["customer_id"] for c in customers]
    seen_ids = set()

    for i in range(1, NUM_ORDERS + 1):
        order_id = f"ORD{i:06d}"
        seen_ids.add(order_id)
        order_date = random_date(365, 0)
        qty = random.randint(1, 5)
        product = random.choice(products)
        unit_price = product["sell_price"] if product["sell_price"] > 0 else abs(product["sell_price"])
        discount = round(random.uniform(0, 30), 1)
        status = random.choice(STATUSES)
        channel = random.choice(CHANNELS)

        # Introduce dirty data
        if random.random() < 0.02:
            qty = 0  # zero qty
        if random.random() < 0.015:
            unit_price = None  # missing price
        if random.random() < 0.01:
            status = "UNKNOWN"  # invalid status
        if random.random() < 0.005:
            order_id = random.choice(list(seen_ids))  # duplicate

        orders.append({
            "order_id": order_id,
            "customer_id": random.choice(customer_ids),
            "product_id": product["product_id"],
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": discount,
            "order_date": order_date.strftime("%Y-%m-%d"),
            "status": status,
            "channel": channel,
        })
    return orders


# ─── Generate Returns ─────────────────────────────────────────────────────────
def generate_returns(orders):
    returns = []
    completed = [o for o in orders if o["status"] in ("completed", "refunded")]
    sampled = random.sample(completed, min(NUM_RETURNS, len(completed)))
    for i, order in enumerate(sampled, 1):
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        return_date = order_date + timedelta(days=random.randint(1, 30))
        refund = round(
            float(order["unit_price"] or 0) * int(order["quantity"] or 1) * random.uniform(0.5, 1.0), 2
        )
        returns.append({
            "return_id": f"RET{i:05d}",
            "order_id": order["order_id"],
            "product_id": order["product_id"],
            "reason": random.choice(RETURN_REASONS),
            "return_date": return_date.strftime("%Y-%m-%d"),
            "refund_amount": refund,
        })
    return returns


# ─── Write CSVs ──────────────────────────────────────────────────────────────
def write_csv(filename, data):
    if not data:
        return
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  ✅ {filename:<25} — {len(data):>5} rows  →  {filepath}")


if __name__ == "__main__":
    print("\n🛍️  Generating E-Commerce Sample Data...\n")
    products = generate_products()
    customers = generate_customers()
    orders = generate_orders(products, customers)
    returns = generate_returns(orders)

    write_csv("products.csv", products)
    write_csv("customers.csv", customers)
    write_csv("orders.csv", orders)
    write_csv("returns.csv", returns)

    print(f"\n✨ Done! All data saved to: {OUTPUT_DIR}\n")
