-- ============================================================
--  E-Commerce Data Pipeline — Database Schema
--  PostgreSQL 14+
-- ============================================================

-- ─── Dimension: Products ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_products (
    product_id          VARCHAR(20)     PRIMARY KEY,
    name                VARCHAR(255)    NOT NULL,
    category            VARCHAR(100),
    brand               VARCHAR(100),
    cost_price          NUMERIC(12, 2),
    sell_price          NUMERIC(12, 2),
    stock_qty           INTEGER         DEFAULT 0,
    profit_margin_pct   NUMERIC(6, 2),
    created_at          TIMESTAMP       DEFAULT NOW(),
    updated_at          TIMESTAMP       DEFAULT NOW()
);

-- ─── Dimension: Customers ────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id     VARCHAR(20)     PRIMARY KEY,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    full_name       VARCHAR(255),
    email           VARCHAR(255),
    city            VARCHAR(100),
    country         VARCHAR(100),
    signup_date     DATE,
    gender          VARCHAR(50),
    age_group       VARCHAR(20),
    created_at      TIMESTAMP       DEFAULT NOW(),
    updated_at      TIMESTAMP       DEFAULT NOW()
);

-- ─── Fact: Orders ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_orders (
    order_id            VARCHAR(20)     PRIMARY KEY,
    customer_id         VARCHAR(20)     REFERENCES dim_customers(customer_id) ON DELETE SET NULL,
    product_id          VARCHAR(20)     REFERENCES dim_products(product_id) ON DELETE SET NULL,
    quantity            INTEGER         NOT NULL CHECK (quantity > 0),
    unit_price          NUMERIC(12, 2)  NOT NULL,
    discount_pct        NUMERIC(5, 2)   DEFAULT 0,
    gross_revenue       NUMERIC(14, 2),
    discount_amount     NUMERIC(14, 2),
    net_revenue         NUMERIC(14, 2),
    order_date          DATE            NOT NULL,
    order_year          INTEGER,
    order_month         INTEGER,
    order_month_name    VARCHAR(20),
    order_week          INTEGER,
    order_day_of_week   VARCHAR(20),
    status              VARCHAR(30)     NOT NULL,
    channel             VARCHAR(30),
    created_at          TIMESTAMP       DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_date     ON fact_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status   ON fact_orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_channel  ON fact_orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_product  ON fact_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON fact_orders(customer_id);

-- ─── Fact: Returns ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_returns (
    return_id       VARCHAR(20)     PRIMARY KEY,
    order_id        VARCHAR(20)     REFERENCES fact_orders(order_id) ON DELETE SET NULL,
    product_id      VARCHAR(20)     REFERENCES dim_products(product_id) ON DELETE SET NULL,
    reason          VARCHAR(255),
    return_date     DATE,
    refund_amount   NUMERIC(14, 2)  DEFAULT 0,
    created_at      TIMESTAMP       DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_returns_order   ON fact_returns(order_id);
CREATE INDEX IF NOT EXISTS idx_returns_date    ON fact_returns(return_date);

-- ─── Analytics: Daily Sales Summary ──────────────────────────
CREATE TABLE IF NOT EXISTS daily_sales_summary (
    report_date             DATE            PRIMARY KEY,
    total_orders            INTEGER,
    completed_orders        INTEGER,
    cancelled_orders        INTEGER,
    total_gross_revenue     NUMERIC(16, 2),
    total_discount_amount   NUMERIC(16, 2),
    total_net_revenue       NUMERIC(16, 2),
    total_units_sold        INTEGER,
    avg_order_value         NUMERIC(12, 2),
    top_channel             VARCHAR(50),
    top_category            VARCHAR(100),
    created_at              TIMESTAMP       DEFAULT NOW(),
    updated_at              TIMESTAMP       DEFAULT NOW()
);
