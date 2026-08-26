"""fx_rates.py — Step 3: Fetch daily EUR/RON rates from Frankfurter and store in fx_rates."""

import logging
import time
import urllib.request
import json
from contextlib import contextmanager
from datetime import date, timedelta

import psycopg2
import psycopg2.extras

from src.config import DATABASE_URL, FX_API_BASE_URL

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


def get_required_dates() -> list[date]:
    """Return the distinct fx_reference_date values present in orders_clean."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT fx_reference_date FROM orders_clean WHERE fx_reference_date IS NOT NULL ORDER BY 1")
        dates = [row[0] for row in cur.fetchall()]
        cur.close()
    return dates


def fetch_rates_from_api(start: date, end: date) -> dict[date, float]:
    """
    Call Frankfurter for EUR→RON rates over a date range.
    Returns a dict of {date: rate}. Weekend/holiday dates are absent from the response.
    Frankfurter is a public open-source API — no key needed.
    """
    url = f"{FX_API_BASE_URL}/{start}..{end}?from=EUR&to=RON"
    logger.info("Fetching FX rates: %s", url)
    # Frankfurter blocks Python's default user-agent with 403; a browser UA is required
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    # Response shape: {"rates": {"2026-08-25": {"RON": 5.2537}, ...}}
    return {
        date.fromisoformat(d): rates["RON"]
        for d, rates in data.get("rates", {}).items()
    }


def fill_gaps(required_dates: list[date], api_rates: dict[date, float], today: date) -> list[dict]:
    """
    Option A: ensure every required date has a rate.

    - Past/today dates missing from API (weekends/holidays): carry forward
      the last known business-day rate. is_estimated = FALSE — this is the
      standard financial convention, not a guess.
    - Future dates: use the latest available rate. is_estimated = TRUE —
      the real rate doesn't exist yet. Daily refresh overwrites these.
    """
    rows = []
    last_known_rate: float | None = None

    # Walk dates in order so carry-forward works correctly
    all_dates = sorted(set(required_dates))

    for d in all_dates:
        if d in api_rates:
            rate = api_rates[d]
            is_estimated = False
            last_known_rate = rate
        elif d <= today:
            # Weekend or holiday — carry forward last business day rate
            rate = last_known_rate
            is_estimated = False
        else:
            # Future date — use latest known rate as estimate
            rate = last_known_rate
            is_estimated = True

        if rate is None:
            logger.warning("No rate available for %s — skipping", d)
            continue

        rows.append({
            "rate_date":       d,
            "base_currency":   "EUR",
            "target_currency": "RON",
            "rate":            rate,
            "is_estimated":    is_estimated,
        })

    return rows


UPSERT_SQL = """
    INSERT INTO fx_rates (rate_date, base_currency, target_currency, rate, is_estimated)
    VALUES %s
    ON CONFLICT (rate_date, base_currency, target_currency)
    DO UPDATE SET
        rate         = EXCLUDED.rate,
        is_estimated = EXCLUDED.is_estimated,
        fetched_at   = NOW()
"""


def upsert_rates(conn, rows: list[dict]) -> int:
    cur = conn.cursor()
    tuples = [(r["rate_date"], r["base_currency"], r["target_currency"], r["rate"], r["is_estimated"]) for r in rows]
    psycopg2.extras.execute_values(cur, UPSERT_SQL, tuples)
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
    step = "fx_rates"
    start = time.time()
    today = date.today()

    try:
        logger.info("=== STEP 3: FX RATES ===")

        required_dates = get_required_dates()
        logger.info("Required dates from orders_clean: %s", required_dates)

        min_date, max_date = min(required_dates), max(required_dates)

        # Fetch all available rates in one API call
        api_rates = fetch_rates_from_api(min_date, min(max_date, today))
        logger.info("Rates returned by API: %d dates", len(api_rates))

        rows = fill_gaps(required_dates, api_rates, today)
        estimated = sum(1 for r in rows if r["is_estimated"])
        logger.info("Rows to upsert: %d (%d estimated, %d real)", len(rows), estimated, len(rows) - estimated)

        for r in rows:
            flag = "~estimated" if r["is_estimated"] else "real"
            logger.info("  %s  1 EUR = %.4f RON  [%s]", r["rate_date"], r["rate"], flag)

        with get_conn() as conn:
            count = upsert_rates(conn, rows)
            duration = time.time() - start
            log_run(conn, step, "success", count, duration)

        logger.info("Done. %d rates upserted in %.1fs", count, duration)
        return count

    except Exception as exc:
        duration = time.time() - start
        logger.error("FX rates failed: %s", exc, exc_info=True)
        with get_conn() as conn:
            log_run(conn, step, "failure", 0, duration, str(exc))
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    run()
