"""pipeline.py — Orchestrator: runs all 5 steps in sequence."""

import logging
import sys
from datetime import date

from src.ingest import run as run_ingest
from src.clean import run as run_clean
from src.fx_rates import run as run_fx_rates
from src.transforms import run_customer_spend, run_country_revenue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# Auto shut-off: challenge says tear down after 3-5 days
# so i choose to end it on 1 of september.
PIPELINE_END_DATE = date(2026, 9, 1)


def main():
    today = date.today()
    if today > PIPELINE_END_DATE:
        logger.info("Pipeline end date %s reached. Exiting without running.", PIPELINE_END_DATE)
        sys.exit(0)

    logger.info("=== AQURATE PIPELINE — %s ===", today)

    steps = [
        ("ingest",              run_ingest),
        ("clean",               run_clean),
        ("fx_rates",            run_fx_rates),
        ("customer_spend_eur",  run_customer_spend),
        ("country_revenue",     run_country_revenue),
    ]

    for name, step_fn in steps:
        logger.info("--- Running: %s ---", name)
        try:
            result = step_fn()
            logger.info("--- Done: %s (rows=%s) ---", name, result)
        except Exception as exc:
            logger.error("--- FAILED: %s — %s ---", name, exc)
            sys.exit(1)  # fail fast: stop pipeline, mark GitHub Action as failed

    logger.info("=== PIPELINE COMPLETE ===")


if __name__ == "__main__":
    main()
