-- ============================================================
--  Useful ad-hoc queries for analysis
-- ============================================================

-- Monthly Revenue Summary
SELECT
    order_year,
    order_month,
    order_month_name,
    COUNT(DISTINCT order_id)                        AS total_orders,
    SUM(quantity)                                   AS units_sold,
    ROUND(SUM(net_revenue)::numeric, 2)             AS net_revenue,
    ROUND(AVG(net_revenue)::numeric, 2)             AS avg_order_value
FROM fact_orders
WHERE status = 'completed'
GROUP BY order_year, order_month, order_month_name
ORDER BY order_year, order_month;

-- ─────────────────────────────────────────────────────────────

-- Top 10 Revenue Generating Products
SELECT
    p.product_id,
    p.name,
    p.brand,
    p.category,
    SUM(o.quantity)                                 AS units_sold,
    ROUND(SUM(o.net_revenue)::numeric, 2)           AS revenue,
    ROUND(AVG(o.net_revenue)::numeric, 2)           AS avg_sale_value
FROM fact_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.status = 'completed'
GROUP BY p.product_id, p.name, p.brand, p.category
ORDER BY revenue DESC
LIMIT 10;

-- ─────────────────────────────────────────────────────────────

-- Customer Lifetime Value (Top 20)
SELECT
    c.customer_id,
    c.full_name,
    c.country,
    COUNT(DISTINCT o.order_id)                      AS total_orders,
    ROUND(SUM(o.net_revenue)::numeric, 2)           AS lifetime_value,
    MIN(o.order_date)                               AS first_order,
    MAX(o.order_date)                               AS last_order
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY c.customer_id, c.full_name, c.country
ORDER BY lifetime_value DESC
LIMIT 20;

-- ─────────────────────────────────────────────────────────────

-- Cancellation Rate by Channel
SELECT
    channel,
    COUNT(*)                                        AS total_orders,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) AS cancelled,
    ROUND(
        100.0 * COUNT(CASE WHEN status = 'cancelled' THEN 1 END) / COUNT(*), 2
    )                                               AS cancellation_rate_pct
FROM fact_orders
GROUP BY channel
ORDER BY cancellation_rate_pct DESC;

-- ─────────────────────────────────────────────────────────────

-- Daily Returns Rate
SELECT
    return_date,
    COUNT(*)                                        AS returns,
    ROUND(SUM(refund_amount)::numeric, 2)           AS total_refunds
FROM fact_returns
GROUP BY return_date
ORDER BY return_date DESC
LIMIT 30;

-- ─────────────────────────────────────────────────────────────

-- Revenue vs Returns by Category
SELECT
    p.category,
    ROUND(SUM(o.net_revenue)::numeric, 2)           AS total_revenue,
    COUNT(DISTINCT r.return_id)                     AS total_returns,
    ROUND(SUM(r.refund_amount)::numeric, 2)         AS total_refunds,
    ROUND(
        100.0 * COUNT(DISTINCT r.return_id) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2
    )                                               AS return_rate_pct
FROM fact_orders o
JOIN dim_products p ON o.product_id = p.product_id
LEFT JOIN fact_returns r ON o.order_id = r.order_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY total_revenue DESC;
