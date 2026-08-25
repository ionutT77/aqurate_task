"""clean.py — Step 2: Transform orders_raw → orders_clean (see PROJECT_JOURNAL.md for issue details)."""

import logging
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from src.config import DATABASE_URL

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


# Issue 1 — three timestamp formats found in orders_raw
_TS_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601
    "%d/%m/%Y %H:%M",      # DD/MM/YYYY
    "%Y-%m-%d %H:%M:%S",   # ISO with space
]

def parse_timestamp(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw.isdigit():  # Unix epoch
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning("Could not parse timestamp: %r", raw)
    return None


# Issue 9 — canonical SKU format: SKU-XX-NNN
_SKU_RE = re.compile(r"^SKU-?([A-Z]{2})-?(\d{3})$", re.IGNORECASE)

def normalise_sku(sku: str | None) -> str | None:
    if sku is None:
        return None
    m = _SKU_RE.match(sku.strip().upper())
    return f"SKU-{m.group(1).upper()}-{m.group(2)}" if m else sku.strip().upper()


# Issue 7 — deterministic SKU prefix → category mapping
_SKU_TO_CATEGORY = {
    "BK": "Books", "EL": "Electronics", "BE": "Beauty",
    "FA": "Fashion", "HK": "Home & Kitchen", "SP": "Sports",
}

def infer_category(category: str | None, sku: str | None) -> tuple[str | None, bool]:
    """Returns (category, was_inferred). Infers from SKU prefix if category is NULL."""
    if category is not None:
        return category, False
    if sku is None:
        return None, False
    parts = (normalise_sku(sku) or "").split("-")
    if len(parts) == 3:
        inferred = _SKU_TO_CATEGORY.get(parts[1].upper())
        if inferred:
            return inferred, True
    return None, False


def clean_row(raw: dict) -> dict | None:
    """Apply all transformation rules. Returns None for excluded rows."""
    if raw.get("status") == "test":  # Issue 5
        return None
    qty = raw.get("qty")
    if qty is not None and qty < 0:  # Issue 4
        return None

    sku = normalise_sku(raw.get("sku"))
    category, had_null_category = infer_category(raw.get("category"), sku)
    unit_price = raw.get("unit_price")

    return {
        "order_id":          raw.get("order_id"),
        "customer_id":       raw.get("customer_id"),
        "customer_email":    raw.get("customer_email"),
        "order_ts":          parse_timestamp(raw.get("order_ts")),
        "status":            raw.get("status"),
        "channel":           raw.get("channel"),
        "sku":               sku,
        "product_name":      raw.get("product_name"),
        "category":          category,
        "qty":               qty,
        "unit_price":        unit_price,
        "currency":          raw.get("currency"),
        "country":           raw.get("country"),
        "fx_reference_date": raw.get("fx_reference_date"),
        "had_null_customer": raw.get("customer_id") is None,   # Issue 6
        "had_null_category": had_null_category,                 # Issue 7
        "had_zero_price":    unit_price is not None and unit_price == 0,  # Issue 8
    }


def deduplicate(rows: list[dict]) -> list[dict]:
    """Issue 2 — remove rows with identical (order_id, sku), keep first occurrence."""
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in rows:
        key = (row["order_id"], row["sku"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


INSERT_SQL = """
    INSERT INTO orders_clean (
        order_id, customer_id, customer_email, order_ts, status, channel,
        sku, product_name, category, qty, unit_price, currency, country,
        fx_reference_date, had_null_customer, had_null_category, had_zero_price
    ) VALUES %s
    ON CONFLICT (order_id, sku) DO NOTHING
"""


def load_clean(conn, rows: list[dict]) -> int:
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE orders_clean")
    tuples = [
        (
            r["order_id"], r["customer_id"], r["customer_email"],
            r["order_ts"], r["status"], r["channel"],
            r["sku"], r["product_name"], r["category"],
            r["qty"], r["unit_price"], r["currency"], r["country"],
            r["fx_reference_date"],
            r["had_null_customer"], r["had_null_category"], r["had_zero_price"],
        )
        for r in rows
    ]
    psycopg2.extras.execute_values(cur, INSERT_SQL, tuples, page_size=500)
    cur.close()
    return len(tuples)


def log_run(conn, step, status, rows, duration, error=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pipeline_runs (step_name, status, rows_processed, duration_seconds, error_message) "
        "VALUES (%s, %s, %s, %s, %s)",
        (step, status, rows, round(duration, 2), error),
    )
    cur.close()


def run():
    step = "clean"
    start = time.time()
    try:
        logger.info("=== STEP 2: CLEAN ===")

        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM orders_raw")
            raw_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        logger.info("Raw rows: %d", len(raw_rows))

        cleaned = []
        excluded = {"test": 0, "negative_qty": 0}
        for raw in raw_rows:
            if raw.get("status") == "test":
                excluded["test"] += 1
                continue
            if (raw.get("qty") or 0) < 0:
                excluded["negative_qty"] += 1
                continue
            row = clean_row(raw)
            if row:
                cleaned.append(row)

        logger.info("Excluded: %s", excluded)

        before = len(cleaned)
        cleaned = deduplicate(cleaned)
        logger.info("Deduplication: %d → %d (removed %d)", before, len(cleaned), before - len(cleaned))

        with get_conn() as conn:
            count = load_clean(conn, cleaned)
            duration = time.time() - start
            log_run(conn, step, "success", count, duration)

        logger.info("Done. %d rows in %.1fs", count, duration)
        return count

    except Exception as exc:
        duration = time.time() - start
        logger.error("Cleaning failed: %s", exc, exc_info=True)
        with get_conn() as conn:
            log_run(conn, step, "failure", 0, duration, str(exc))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    run()
