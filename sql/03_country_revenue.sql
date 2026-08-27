-- Step 5: EUR revenue by country for Books + Electronics
-- Only completed orders; only countries where combined revenue exceeds €40,000
-- Ranked by revenue descending

SELECT
    oc.country,
    ROUND(SUM(
        CASE
            WHEN oc.currency = 'EUR' THEN oc.qty * oc.unit_price
            ELSE oc.qty * oc.unit_price / fx.rate
        END
    )::NUMERIC, 2)              AS total_revenue_eur,
    COUNT(DISTINCT oc.order_id) AS order_count
FROM orders_clean oc
JOIN fx_rates fx
    ON  oc.fx_reference_date = fx.rate_date
    AND fx.base_currency     = 'EUR'
    AND fx.target_currency   = 'RON'
WHERE oc.status   = 'completed'
  AND oc.category IN ('Books', 'Electronics')
GROUP BY oc.country
HAVING ROUND(SUM(
    CASE
        WHEN oc.currency = 'EUR' THEN oc.qty * oc.unit_price
        ELSE oc.qty * oc.unit_price / fx.rate
    END
)::NUMERIC, 2) > 40000
ORDER BY total_revenue_eur DESC;
