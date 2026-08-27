# Aqurate Data Pipeline — Junior Data Engineer Challenge

An end-to-end ETL pipeline that ingests raw e-commerce order data, cleans it through robust validation and transformation rules, fetches daily FX rates, and produces two analytical tables — all automated via GitHub Actions.

## Pipeline steps

| Step | Script | Output |
|------|--------|--------|
| 1. Ingest | `src/ingest.py` | `orders_raw` — snapshot of source API |
| 2. Clean | `src/clean.py` | `orders_clean` — validated and normalised orders |
| 3. FX Rates | `src/fx_rates.py` | `fx_rates` — daily EUR/RON rates with gap-filling |
| 4. Customer Spend | `src/transforms.py` | `customer_spend_eur` — total EUR spend per customer |
| 5. Country Revenue | `src/transforms.py` | `country_category_revenue` — Books+Electronics revenue by country |

## Setup

```bash
git clone https://github.com/ionutT77/aqurate_task.git
cd aqurate_task
pip install -r requirements.txt
cp .env.example .env   # fill in your DATABASE_URL
```

## Run manually

```bash
python -m src.pipeline
```

## Automation

A GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`) runs the full pipeline every day at **17:00 UTC** — after the ECB publishes daily FX rates. The pipeline shuts itself off automatically after **2026-09-01**.

Required GitHub secrets: `DATABASE_URL`, `ORDERS_API_KEY`.

## Database

Hosted on Supabase (PostgreSQL). Schema defined in `sql/01_create_tables.sql`.
All pipeline steps are idempotent — safe to rerun at any time.

## Documentation

- `PROJECT_JOURNAL.md` — step-by-step log of every decision and problem encountered
- `WRITEUP.md` — summary of data issues, engineering decisions, and monitoring strategy
