# Project Journal — Aqurate Junior Data Engineer Challenge

> **Purpose**: Step-by-step log of everything done, every problem encountered, and how it was solved.
> This is a living document — updated after every meaningful action.

---

## Overview

| Field | Value |
|-------|-------|
| Challenge | Junior Data Engineer — Aqurate |
| Start date | 2026-08-25 |
| Deadline | 2026-09-01 (23:59 RO) |
| Stack | Python 3.11, PostgreSQL (Supabase), GitHub Actions |
| Repo | Private until submission |

---

## Session 1 — 2026-08-25

### 1.1 Reading the Challenge

**What I did:**  
Read the PDF `Junior Data Engineer - Challenge.pdf` in full. Extracted the 8 deliverables:

1. Ingest `orders_raw` from a public Supabase REST API into our own database
2. Create `orders_clean` with data issues resolved
3. Pull daily FX rates (EUR ↔ RON) from a free source
4. Create `customer_spend_eur` — total EUR spend per customer
5. Create `country_category_revenue` — EUR revenue by country for Books + Electronics, >€40k
6. Automate steps 4–5 to refresh daily
7. Write a summary covering data issues, monitoring strategy, and AI usage
8. Submit repo link + add `aqurate-careers` as collaborator

**Key notes from the brief:**
- Must exhibit both Python and SQL skills
- Open-ended — how I structure it is part of the evaluation
- Some `fx_reference_date` values are set in the future to simulate daily refresh behaviour
- Tear down automation after 3–5 days (no ongoing cost)

---

### 1.2 Exploring the Source Data

**What I did:**  
Before writing a single line of production code, I pulled the full dataset (9,268 rows) and ran exploratory analysis scripts to understand what I was working with.

**API endpoint used:**
```
GET https://jzozteoirwfczccltcdr.supabase.co/rest/v1/orders_raw
    ?apikey=sb_publishable_Xwjiw--qkKcbMuSbKd6I2w_wN9mpNTv
```

**Dataset shape:**
- **9,268 total rows**
- **14 columns**: `order_id`, `customer_id`, `customer_email`, `order_ts`, `status`, `channel`, `sku`, `product_name`, `category`, `qty`, `unit_price`, `currency`, `country`, `fx_reference_date`
- **1,906 unique customers**
- **Currencies**: EUR (7,340 rows), RON (1,928 rows)
- **Countries**: RO, DE, BG, HU
- **Statuses**: completed (8,764), refunded (403), test (101)
- **Categories**: Books, Electronics, Beauty, Fashion, Home & Kitchen, Sports, NULL (79)

**Data issues found:**

| # | Issue | Count | Decision |
|---|-------|-------|----------|
| 1 | Mixed timestamp formats (ISO 8601, Unix epoch, DD/MM/YYYY HH:MM) | 5592 / 1406 / 2270 | Normalise all to TIMESTAMPTZ |
| 2 | True duplicate rows — same `(order_id, sku)` with identical values | 183 pairs | Deduplicate, keep first |
| 3 | Multi-item orders sharing same `order_id` (different SKUs) | 2,491 order_ids | NOT duplicates — preserve all |
| 4 | Negative quantities on `completed` orders | 167 rows | Exclude — contradictory data |
| 5 | Test orders (`status='test'`, `@aqurate.ai` emails) | 101 rows | Exclude — internal testing data |
| 6 | NULL `customer_id` | 103 rows | Keep but flag — possible guest checkout |
| 7 | NULL `category` | 79 rows | Infer from SKU prefix (deterministic mapping) |
| 8 | Zero `unit_price` on completed orders | 24 rows | Keep but flag — possible promo/freebie |
| 9 | Malformed SKUs (e.g. `SKUEL001` vs `SKU-EL-001`) | ~few | Normalise via regex |

**Key finding — SKU → Category mapping is deterministic:**
```
SKU-BK → Books
SKU-EL → Electronics
SKU-BE → Beauty
SKU-FA → Fashion
SKU-HK → Home & Kitchen
SKU-SP → Sports
```
This meant all 79 NULL categories could be reliably inferred from the SKU.

**FX reference dates:**
- Range: `2026-08-23` → `2026-09-03`
- Several future dates included (as described in the challenge brief — simulates daily refresh)
- For future dates: fetch the latest available rate and flag with `is_estimated = TRUE`

**FX API tested:**
- [frankfurter.dev](https://api.frankfurter.dev) works without an API key
- Endpoint: `GET /v1/{start_date}..{end_date}?from=EUR&to=RON`
- Returns daily rates; weekends use Friday's rate (market is closed)

---

### 1.3 Designing the Architecture

**What I did:**  
Designed the full project structure and tech stack before writing any code.

**Tech stack chosen:**

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Database | Supabase PostgreSQL (free tier) | Mentioned in the challenge; free; REST API included |
| Language | Python 3.11 | Required |
| SQL | Raw SQL via psycopg2 | Shows SQL skills directly; no ORM abstraction |
| FX API | frankfurter.dev | Free, no key, reliable, supports date ranges |
| Automation | GitHub Actions (cron) | Free, visible in repo, no extra infra |
| Secrets | GitHub Actions Secrets + local `.env` | Industry standard |

**Project structure decided:**
```
aqurate_task/
├── .github/workflows/daily_pipeline.yml
├── src/
│   ├── config.py       # centralised env loading
│   ├── ingest.py       # Step 1
│   ├── clean.py        # Step 2
│   ├── fx_rates.py     # Step 3
│   ├── transforms.py   # Steps 4–5
│   └── pipeline.py     # orchestrator
├── sql/
│   └── 01_create_tables.sql
├── tests/
├── PROJECT_JOURNAL.md  # this file
├── WRITEUP.md
├── README.md
├── requirements.txt
├── .env                # gitignored
└── .env.example
```

---

### 1.4 Setting Up the Gitignore

**What I did:**  
Created `.gitignore` at the repo root to protect secrets and exclude internal files.

**Key entries added:**
```gitignore
implementation_plan.md   # internal planning doc — not for GitHub
_explore.py              # throwaway exploration scripts
.env                     # secrets — NEVER committed
__pycache__/ / *.pyc     # Python bytecode
.vscode/ / .idea/        # IDE files
```

**Reasoning:**  
The implementation plan contains my internal thinking and rough notes — it shouldn't be part of the submitted repo. The `.env` file contains the database password.

---

### 1.5 Creating the Supabase Project

**What I did:**  
Created a new Supabase project to host the target database.

**Steps taken:**
1. Logged into [supabase.com/dashboard](https://supabase.com/dashboard)
2. Created new project: `aqurate-challenge`
3. Selected region: `eu-central-1` (Frankfurt — closest to Romania)
4. Set a database password

**Connection string obtained:**  
Used the **"Connect"** button → **"Direct Connection string"** tab → **Transaction Pooler** option (port 6543, IPv4-compatible — important for home networks which are IPv4-only).

```
postgresql://postgres.rewrjmculyhegsvjpddu:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

> **Problem encountered:** The default "Direct Connection" uses IPv6, which doesn't work on most home networks. Solution: switched to the "Transaction Pooler" (port 6543) which is IPv4-compatible and works everywhere.

---

### 1.6 Creating the Database Tables

**What I did:**  
Wrote `sql/01_create_tables.sql` and ran it in the Supabase SQL Editor.

**Tables created:**

| Table | Purpose |
|-------|---------|
| `orders_raw` | Mirror of the source API data, kept as-is |
| `orders_clean` | Cleaned version with normalised types and quality flags |
| `fx_rates` | Daily EUR→RON rates from Frankfurter API |
| `customer_spend_eur` | Aggregated total EUR spend per customer (Step 4) |
| `country_category_revenue` | Revenue by country for Books+Electronics (Step 5) |
| `pipeline_runs` | Audit log for every pipeline execution (observability) |

**Design decisions:**
- `orders_raw.order_ts` stored as `TEXT` — raw data is too inconsistent for a typed column; normalisation happens in the clean step
- `orders_clean` has a composite `PRIMARY KEY (order_id, sku)` — enforces deduplication at the DB level
- `orders_clean` has 3 boolean flag columns: `had_null_customer`, `had_null_category`, `had_zero_price` — keeps the data while flagging quality issues for downstream consumers
- `fx_rates` has `is_estimated BOOLEAN` — marks rates that were fetched before the market date (future dates)
- `pipeline_runs` logs step name, status, rows processed, duration, and error message — enables production monitoring

**Result:** `Success. No rows returned` — all 6 tables created successfully.

---

### 1.7 Testing the Connection from Python

**What I did:**  
Installed `psycopg2-binary` and `python-dotenv`, wrote `_test_connection.py`, and verified the Python → Supabase connection.

**Command:**
```bash
pip install psycopg2-binary python-dotenv
python _test_connection.py
```

**Output:**
```
Connected successfully!
Tables found: ['country_category_revenue', 'customer_spend_eur', 'fx_rates',
               'orders_clean', 'orders_raw', 'pipeline_runs']
```

All 6 tables visible from Python. ✅

---

### 1.8 Step 1: Ingestion (`src/ingest.py`)

**What I did:**  
Wrote the ingestion module to pull all orders from the source API and load them into our `orders_raw` table.

**Key design decisions:**

1. **Pagination**: Supabase REST API defaults to 1,000 rows per page. Implemented a loop with `limit` + `offset` to fetch all pages until the last page returns fewer than 1,000 rows.

2. **Idempotency**: Used `TRUNCATE + INSERT` (not `UPSERT`) because `orders_raw` has no natural single-column primary key — `order_id` is not unique (multi-item orders). This means the table is always a clean snapshot of the source API.

3. **Pipeline logging**: Every run logs to `pipeline_runs` with step name, row count, duration, and any error.

**Result:**
Total rows fetched from API: 9268
Ingestion complete. 9268 rows loaded in 7.8s

✅ 9,268 rows loaded across 10 paginated API calls.

---

### 1.9 Step 2: Cleaning (`src/clean.py`)

**Cleaning logic implemented:**

**Issue 1 — Timestamp normalisation:**  
Three formats detected. Cascade parser:
- Digits only → Unix epoch → `datetime.fromtimestamp()`
- Contains `T` → `strptime("%Y-%m-%dT%H:%M:%S")`
- Contains `/` → `strptime("%d/%m/%Y %H:%M")`
- All normalised to UTC-aware `TIMESTAMPTZ`

**Issue 2 — True deduplication:**  
Used a Python `set` of `(order_id, sku)` tuples. First occurrence kept, subsequent identical rows discarded.

**Issue 3 — Multi-item orders:**  
Preserved — same `order_id` with different `sku` values = valid multi-line order.

**Issue 4 — Negative quantities:**  
Rows with `qty < 0` and `status = 'completed'` excluded entirely.

**Issue 5 — Test orders:**  
Rows with `status = 'test'` (confirmed by `@aqurate.ai` emails) excluded entirely.

**Issue 6 — NULL customer_id:**  
Kept, flagged with `had_null_customer = TRUE` — likely guest checkouts.

**Issue 7 — NULL category:**  
Inferred from SKU prefix. Flagged with `had_null_category = TRUE`.

**Issue 8 — Zero unit_price:**  
Kept, flagged with `had_zero_price = TRUE`.

**Issue 9 — Malformed SKUs:**  
Normalised via regex `^SKU-?([A-Z]{2})-?(\d{3})$` → `SKU-XX-NNN`.

**Result:**
```
Raw rows: 9268
Excluded: {'test': 101, 'negative_qty': 167}
Deduplication: 9000 → 8823 (removed 177)
Done. 8823 rows in 6.9s
```

**Cleaning funnel:**

| Stage | Rows | Removed |
|-------|------|---------|
| Raw | 9,268 | — |
| − Test orders | 9,167 | −101 |
| − Negative qty | 9,000 | −167 |
| − True duplicates | 8,823 | −177 |
| **orders_clean** | **8,823** | **−445 total** |

✅ `orders_clean` populated with 8,823 clean rows.

---

### 1.9a Real Examples — Each Issue Explained

#### Issue 1 — Mixed Timestamp Formats

The `order_ts` column had three incompatible formats in the same column:

| Format | Raw value | Parsed to |
|--------|-----------|-----------|
| ISO 8601 | `2026-01-12T10:58:06` | `2026-01-12 10:58:06+00:00` |
| Unix epoch | `1781474381` | `2026-06-14 04:39:41+00:00` |
| DD/MM/YYYY | `05/04/2026 07:29` | `2026-04-05 07:29:00+00:00` |

The cascade parser tries each format in order and logs a warning if nothing matches.

---

#### Issue 2 — True Duplicate Rows

Rows with **identical values in every column** — byte-for-byte duplicates:

```
order_id    sku          qty  unit_price  status     order_ts
ORD13536    SKU-HK-001   1    44.34       completed  2026-02-05T10:36:55
ORD13536    SKU-HK-001   1    44.34       completed  2026-02-05T10:36:55  ← duplicate
```

**Fix**: Keep only the first occurrence of each `(order_id, sku)` pair. 177 rows removed.

---

#### Issue 3 — Multi-Item Orders (NOT Duplicates)

Same `order_id`, different SKUs — one order with multiple line items:

```
order_id    sku          product_name              qty  unit_price
ORD10690    SKU-BK-001   Atomic Habits (RO ed.)    2    21.91
ORD10690    SKU-BK-002   The Pragmatic Programmer  2    43.48   ← same order, different item
```

**Fix**: Preserve all. Deduplication only fires when **both** `order_id` AND `sku` match identically.

---

#### Issue 4 — Negative Quantities on Completed Orders

```
order_id    qty   unit_price  status     customer_id
ORD13202    -1    59.32       completed  441
ORD14298    -1    23.76       completed  882
```

A completed sale with qty = −1 is contradictory. Likely a return incorrectly labelled as `completed` instead of `refunded`.

**Fix**: Exclude entirely (167 rows). In production: route to a quarantine table for manual review.

---

#### Issue 5 — Test Orders

```
order_id    status  customer_email                    product_name
ORD11312    test    internal.tester1837@aqurate.ai    Stainless Steel Kettle
ORD14102    test    internal.tester1175@aqurate.ai    Stainless Steel Kettle
```

`@aqurate.ai` email domain confirms these are internal records, not real purchases.

**Fix**: Exclude entirely (101 rows).

---

#### Issue 6 — NULL customer_id

```
order_id    customer_id   status     qty  unit_price  currency
ORD15120    NULL          completed  2    34.99       EUR
```

The order is valid — product, amount, timestamp all present — but no customer identity. Likely a guest checkout.

**Fix**: Keep, set `had_null_customer = TRUE`. Included in revenue totals but excluded from `customer_spend_eur`.

---

#### Issue 7 — NULL Category (inferred from SKU)

```
order_id    sku          product_name          category (raw)  category (fixed)
ORD11973    SKUEL001     Wireless Earbuds X2   NULL            Electronics
ORD12756    SKU-EL-001   Wireless Earbuds X2   NULL            Electronics
ORD13035    SKU-BE-001   Vitamin C Serum 30ml  NULL            Beauty
```

SKU prefix → category mapping is deterministic. After normalising `SKUEL001` → `SKU-EL-001`, the `EL` code maps to `Electronics` with certainty.

**Fix**: Infer from SKU prefix, flag with `had_null_category = TRUE`.

---

#### Issue 8 — Zero Unit Price

```
order_id    sku          product_name              qty  unit_price  status
ORD15993    SKU-HK-001   Stainless Steel Kettle    1    0.00        completed
ORD14255    SKU-FA-003   Running Shoes Pro         2    0.00        completed
ORD12609    SKU-EL-002   USB-C Fast Charger 65W    1    0.00        completed
```

Could be a promo, bundled gift, or data error. No way to determine intent.

**Fix**: Keep, set `had_zero_price = TRUE`. Zero × qty = €0, so revenue totals are not distorted.

---

#### Issue 9 — Malformed SKUs

```
Raw SKU      Normalised      Difference
SKUEL001     SKU-EL-001      Missing both dashes
SKU-EL001    SKU-EL-001      Missing trailing dash
SKU-EL-001   SKU-EL-001      Correct — no change needed
```

Regex `^SKU-?([A-Z]{2})-?(\d{3})$` captures the letter code and digit suffix regardless of dash presence, then rebuilds `SKU-XX-NNN`.

---

### 1.10 requirements.txt

Created `requirements.txt` with pinned versions of the two direct dependencies:

```
psycopg2-binary==2.9.10
python-dotenv==1.0.1
```

Versions pinned (not `>=`) so the pipeline behaves identically locally and in GitHub Actions.

---

## Next Steps

- [x] Step 1: Ingestion (`src/ingest.py`)
- [x] Step 2: Cleaning (`src/clean.py`)
- [x] requirements.txt
- [ ] Step 3: FX rates fetcher (`src/fx_rates.py`)
- [ ] Step 4: Customer spend in EUR (`src/transforms.py`)
- [ ] Step 5: Country/category revenue breakdown
- [ ] Step 6: GitHub Actions automation
- [ ] Step 7: WRITEUP.md
- [ ] Step 8: Submit
