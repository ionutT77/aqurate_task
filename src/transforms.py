"""transforms.py — Steps 4 & 5: Build customer_spend_eur and country_category_revenue."""

import logging
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from src.config import DATABASE_URL, REVENUE_CATEGORIES, REVENUE_THRESHOLD_EUR

logger = logging.getLogger(__name__)


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# country is order-level, not customer-level — 10 customers have orders in all 4 countries.
# We resolve this by computing spend per customer first, then joining the most-frequent country.
CUSTOMER_SPEND_SQL = """
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
        -- Most frequent shipping country per customer
        SELECT DISTINCT ON (customer_id)
            customer_id,
            country
        FROM orders_clean
        WHERE status = 'completed' AND customer_id IS NOT NULL
        GROUP BY customer_id, country
        ORDER BY customer_id, COUNT(*) DESC
    ),
    country_count AS (
        -- Flag customers who ordered from more than one country
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
    ORDER BY s.total_spent_eur DESC
"""

INSERT_SPEND_SQL = """
    INSERT INTO customer_spend_eur
        (customer_id, customer_email, country, total_orders, total_items,
         total_spent_eur, last_order_date, multiple_countries_bought)
    VALUES %s
"""


def build_customer_spend(conn) -> int:
    cur = conn.cursor()

    logger.info("Truncating customer_spend_eur...")
    cur.execute("TRUNCATE TABLE customer_spend_eur")

    cur.execute(CUSTOMER_SPEND_SQL)
    rows = cur.fetchall()

    psycopg2.extras.execute_values(cur, INSERT_SPEND_SQL, rows, page_size=500)
    cur.close()

    logger.info("Top 5 customers by spend:")
    for r in rows[:5]:
        multi = " [multi-country]" if r[7] else ""
        logger.info("  customer_id=%-6s  country=%-3s  total_spent=€%.2f%s", r[0], r[2], float(r[5]), multi)

    return len(rows)


COUNTRY_REVENUE_SQL = """
    SELECT
        oc.country,
        ROUND(SUM(
            CASE
                WHEN oc.currency = 'EUR' THEN oc.qty * oc.unit_price
                ELSE oc.qty * oc.unit_price / fx.rate
            END
        )::NUMERIC, 2)                                      AS total_revenue_eur,
        COUNT(DISTINCT oc.order_id)                         AS order_count
    FROM orders_clean oc
    JOIN fx_rates fx
        ON  oc.fx_reference_date = fx.rate_date
        AND fx.base_currency     = 'EUR'
        AND fx.target_currency   = 'RON'
    WHERE oc.status   = 'completed'
      AND oc.category = ANY(%s)
    GROUP BY oc.country
    HAVING ROUND(SUM(
        CASE
            WHEN oc.currency = 'EUR' THEN oc.qty * oc.unit_price
            ELSE oc.qty * oc.unit_price / fx.rate
        END
    )::NUMERIC, 2) > %s
    ORDER BY total_revenue_eur DESC
"""
#this sql is meant only for python code
# this is a simple sql quary meant to be executed in psql console
# it is not in the same table as the other sql files

INSERT_REVENUE_SQL = """
    INSERT INTO country_category_revenue (country, total_revenue_eur, order_count)
    VALUES %s
"""


def build_country_revenue(conn) -> int:
    cur = conn.cursor()

    logger.info("Truncating country_category_revenue...")
    cur.execute("TRUNCATE TABLE country_category_revenue")

    cur.execute(COUNTRY_REVENUE_SQL, (REVENUE_CATEGORIES, REVENUE_THRESHOLD_EUR))
    rows = cur.fetchall()

    psycopg2.extras.execute_values(cur, INSERT_REVENUE_SQL, rows, page_size=100)
    cur.close()

    logger.info("Country/category revenue (Books + Electronics, >€%.0f):", REVENUE_THRESHOLD_EUR)
    for r in rows:
        logger.info("  %-4s  €%.2f  (%d orders)", r[0], float(r[1]), r[2])

    return len(rows)



def log_run(conn, step, status, rows, duration, error=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pipeline_runs (step_name, status, rows_processed, duration_seconds, error_message) "
        "VALUES (%s, %s, %s, %s, %s)",
        (step, status, rows, round(duration, 2), error),
    )
    cur.close()


def run_customer_spend():
    step = "customer_spend_eur"
    start = time.time()
    try:
        logger.info("=== STEP 4: CUSTOMER SPEND IN EUR ===")
        with get_conn() as conn:
            count = build_customer_spend(conn)
            duration = time.time() - start
            log_run(conn, step, "success", count, duration)
        logger.info("Done. %d customers in %.1fs", count, duration)
        return count
    except Exception as exc:
        duration = time.time() - start
        logger.error("Step 4 failed: %s", exc, exc_info=True)
        with get_conn() as conn:
            log_run(conn, step, "failure", 0, duration, str(exc))
        raise


def run_country_revenue():
    step = "country_category_revenue"
    start = time.time()
    try:
        logger.info("=== STEP 5: COUNTRY/CATEGORY REVENUE ===")
        with get_conn() as conn:
            count = build_country_revenue(conn)
            duration = time.time() - start
            log_run(conn, step, "success", count, duration)
        logger.info("Done. %d countries in %.1fs", count, duration)
        return count
    except Exception as exc:
        duration = time.time() - start
        logger.error("Step 5 failed: %s", exc, exc_info=True)
        with get_conn() as conn:
            log_run(conn, step, "failure", 0, duration, str(exc))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    run_customer_spend()
    run_country_revenue()
