-- Step 4: Total EUR spend per customer
-- Only completed orders, only known customers (non-NULL customer_id)
-- RON orders converted using the fx_reference_date rate from fx_rates
-- country = most frequent shipping destination; multiple_countries_bought flags cross-border customers

WITH spend AS (
    SELECT
        oc.customer_id,
        oc.customer_email,
        COUNT(DISTINCT oc.order_id)                         AS total_orders,
        SUM(oc.qty)                                         AS total_items,
        ROUND(SUM(
            CASE
                WHEN oc.currency = 'EUR' THEN oc.qty * oc.unit_price
                ELSE oc.qty * oc.unit_price / fx.rate
            END
        )::NUMERIC, 2)                                      AS total_spent_eur,
        MAX(oc.order_ts::DATE)                              AS last_order_date
    FROM orders_clean oc
    JOIN fx_rates fx
        ON  oc.fx_reference_date = fx.rate_date
        AND fx.base_currency     = 'EUR'
        AND fx.target_currency   = 'RON'
    WHERE oc.status       = 'completed'
      AND oc.customer_id IS NOT NULL
    GROUP BY oc.customer_id, oc.customer_email
),
primary_country AS (
    SELECT DISTINCT ON (customer_id)
        customer_id,
        country
    FROM orders_clean
    WHERE status = 'completed' AND customer_id IS NOT NULL
    GROUP BY customer_id, country
    ORDER BY customer_id, COUNT(*) DESC
),
country_count AS (
    SELECT customer_id, COUNT(DISTINCT country) > 1 AS multiple_countries_bought
    FROM orders_clean
    WHERE status = 'completed' AND customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT
    s.customer_id,
    s.customer_email,
    pc.country,
    s.total_orders,
    s.total_items,
    s.total_spent_eur,
    s.last_order_date,
    cc.multiple_countries_bought
FROM spend s
JOIN primary_country pc ON s.customer_id = pc.customer_id
JOIN country_count  cc ON s.customer_id = cc.customer_id
ORDER BY total_spent_eur DESC;
