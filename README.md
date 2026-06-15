#  E-Commerce Data Pipeline

> A **production-grade ETL pipeline** for fashion & lifestyle e-commerce brands.
> Simulates real-world data engineering workflows — CSV ingestion → cleaning → PostgreSQL → automated reports.

---

##  Project Structure

```
ecommerce-pipeline/
├── data/
│   ├── raw/                  ← Input CSV files (generated)
│   └── processed/            ← Cleaned CSVs (audit trail)
├── src/
│   ├── extract.py            ← E — CSV ingestion & validation
│   ├── transform.py          ← T — Cleaning, enrichment, DQ checks
│   ├── load.py               ← L — PostgreSQL upsert loader
│   ├── report.py             ← HTML report with charts
│   └── pipeline.py           ← Main orchestrator
├── sql/
│   ├── schema.sql            ← DB schema (dim/fact tables)
│   └── queries.sql           ← Useful ad-hoc SQL queries
├── reports/                  ← Generated HTML reports
├── logs/                     ← Pipeline run logs
├── tests/
│   └── test_pipeline.py      ← 18 unit tests (pytest)
├── config.py                 ← Centralized config
├── generate_data.py          ← Realistic fake data generator
├── requirements.txt
└── .env.example
```

---

##  Setup

### 1. Clone & Install Dependencies

```bash
cd ecommerce-pipeline
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_db
DB_USER=postgres
DB_PASSWORD=your_password
```

### 3. Create the PostgreSQL Database

```bash
psql -U postgres -c "CREATE DATABASE ecommerce_db;"
```

---

##  Running the Pipeline

### Step 1 — Generate Sample Data

```bash
python generate_data.py
```

Produces 4 CSV files in `data/raw/` with **intentional dirty data** (bad emails, null prices, duplicates) for the cleaning step to handle.

| File           | Rows | Description              |
|----------------|------|--------------------------|
| `products.csv` |   80 | Fashion product catalog  |
| `customers.csv`|  500 | Customer profiles        |
| `orders.csv`   | 3000 | Sales transactions       |
| `returns.csv`  |  200 | Product return records   |

### Step 2 — Run the Full ETL Pipeline

```bash
python src/pipeline.py
```

This runs all 4 phases:

```
EXTRACT   → Reads & validates CSV files
TRANSFORM  → Cleans data, flags issues, computes revenue
LOAD      → Upserts into PostgreSQL (idempotent, safe to re-run)
REPORT    → Generates HTML report with charts → reports/
```

### Other Run Modes

```bash
# Validate data only (no DB required)
python src/pipeline.py --dry-run

# Run ETL without generating a report
python src/pipeline.py --no-report
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

18 unit tests covering all data cleaning rules:
- Negative price fixing
- Duplicate removal
- Email validation
- Revenue computation
- Discount clamping
- Time dimension extraction
- ... and more

---

## Database Schema

```
dim_products      — Product catalog (dimension table)
dim_customers     — Customer profiles (dimension table)
fact_orders       — Sales transactions (fact table)
fact_returns      — Return records (fact table)
daily_sales_summary — Pre-aggregated analytics table
```

The schema follows a **star schema** design — standard in data warehousing — with dimension tables linked to fact tables by foreign keys.

---

## Generated Report

After running the pipeline, open the report in your browser:

```bash
open reports/latest_report.html
```

The report includes:
-  **KPI Dashboard** — Revenue, Orders, Units, AOV, Discounts
-  **30-day Revenue Trend** (line chart)
-  **Daily Orders Volume** (bar chart)
-  **Revenue by Category** (horizontal bar)
-  **Revenue by Channel** (pie chart)
-  **Revenue by Country** (bar chart)
-  **Top 10 Products table**
-  **Order Status & Returns breakdown**

---

##  Skills Demonstrated

| Skill | Implementation |
|-------|---------------|
| **Python** | OOP pipeline design, argparse CLI, logging |
| **Pandas** | DataFrame cleaning, type coercion, derived columns |
| **SQL** | Star schema, window functions, upsert (ON CONFLICT) |
| **ETL** | Extract→Transform→Load with audit trail & DQ report |
| **Database Design** | Dimension/Fact tables, indexes, FK constraints |
| **Testing** | pytest, 18 unit tests across all transform rules |
| **Data Quality** | Automated flagging & fixing of 10+ issue types |
| **Reporting** | Matplotlib charts + Jinja2 HTML template |

---

##  Re-Running the Pipeline

The pipeline is **fully idempotent** — you can safely re-run it on the same data:
- `INSERT ON CONFLICT DO UPDATE` handles duplicates gracefully
- Daily summary is recomputed and updated each run
- Processed CSVs are overwritten with the latest clean version

---

##  Logs

All pipeline runs are logged to `logs/pipeline.log`:

```
2024-06-15 18:30:01  INFO       Pipeline started
2024-06-15 18:30:01  INFO       EXTRACT PHASE — Reading Raw CSV Files
2024-06-15 18:30:02  INFO       Loaded 'orders.csv' → 3,000 rows
2024-06-15 18:30:03  WARNING       [orders] Rows dropped (zero qty): 12
2024-06-15 18:30:05  INFO      Load phase complete.
2024-06-15 18:30:08  INFO       Pipeline completed in 7.2s
```
