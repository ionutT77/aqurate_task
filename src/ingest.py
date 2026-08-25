"""ingest.py — Step 1: Pull orders_raw from the source API and load into our DB."""

import logging
import time
import urllib.request
import json
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from src.config import DATABASE_URL, ORDERS_API_URL, ORDERS_API_KEY

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


def fetch_all_orders() -> list[dict[str, Any]]:
    """Paginate through the source API (1000 rows/page) and return all rows."""
    all_rows: list[dict] = []
    page_size = 1000
    offset = 0

    while True:
        url = f"{ORDERS_API_URL}?apikey={ORDERS_API_KEY}&limit={page_size}&offset={offset}"
        req = urllib.request.Request(url, headers={"apikey": ORDERS_API_KEY})
        with urllib.request.urlopen(req) as resp:
            page = json.loads(resp.read())

        all_rows.extend(page)
        logger.info("Fetched offset=%d  rows=%d  total=%d", offset, len(page), len(all_rows))

        if len(page) < page_size:
            break
        offset += page_size

    return all_rows


INSERT_SQL = """
    INSERT INTO orders_raw (
        order_id, customer_id, customer_email, order_ts, status, channel,
        sku, product_name, category, qty, unit_price, currency, country,
        fx_reference_date
    ) VALUES %s
"""


def load_orders(conn, rows: list[dict]) -> int:
    """TRUNCATE + bulk INSERT — idempotent snapshot of the source data."""
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE orders_raw")
    tuples = [
        (
            r.get("order_id"), r.get("customer_id"), r.get("customer_email"),
            r.get("order_ts"),  # stored as raw TEXT; normalised in clean step
            r.get("status"), r.get("channel"), r.get("sku"),
            r.get("product_name"), r.get("category"), r.get("qty"),
            r.get("unit_price"), r.get("currency"), r.get("country"),
            r.get("fx_reference_date"),
        )
        for r in rows
    ]
    psycopg2.extras.execute_values(cur, INSERT_SQL, tuples, page_size=500)
    cur.close()
    return len(tuples)


def log_run(conn, step: str, status: str, rows: int, duration: float, error: str | None = None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pipeline_runs (step_name, status, rows_processed, duration_seconds, error_message) "
        "VALUES (%s, %s, %s, %s, %s)",
        (step, status, rows, round(duration, 2), error),
    )
    cur.close()


def run():
    step = "ingest"
    start = time.time()
    try:
        logger.info("=== STEP 1: INGEST ===")
        rows = fetch_all_orders()
        logger.info("Total rows fetched: %d", len(rows))

        with get_conn() as conn:
            count = load_orders(conn, rows)
            duration = time.time() - start
            log_run(conn, step, "success", count, duration)

        logger.info("Done. %d rows in %.1fs", count, duration)
        return count

    except Exception as exc:
        duration = time.time() - start
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        with get_conn() as conn:
            log_run(conn, step, "failure", 0, duration, str(exc))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    run()
