-- ============================================================
-- 01_create_tables.sql
-- Creates all tables for the Aqurate Data Engineer Challenge
-- ============================================================

-- -------------------------------------------------------
-- RAW ORDERS (mirror of the source API data)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders_raw (
    order_id         TEXT,
    customer_id      INTEGER,
    customer_email   TEXT,
    order_ts         TEXT,          -- kept as TEXT; raw values are inconsistent
    status           TEXT,
    channel          TEXT,
    sku              TEXT,
    product_name     TEXT,
    category         TEXT,
    qty              INTEGER,
    unit_price       NUMERIC(12, 4),
    currency         TEXT,
    country          TEXT,
    fx_reference_date DATE,
    -- audit columns
    ingested_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -------------------------------------------------------
-- CLEANED ORDERS
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders_clean (
    order_id          TEXT,
    customer_id       INTEGER,
    customer_email    TEXT,
    order_ts          TIMESTAMPTZ,  -- normalized from all 3 source formats
    status            TEXT,
    channel           TEXT,
    sku               TEXT,         -- normalized (e.g. SKUEL001 → SKU-EL-001)
    product_name      TEXT,
    category          TEXT,         -- inferred from SKU if originally NULL
    qty               INTEGER,
    unit_price        NUMERIC(12, 4),
    currency          TEXT,
    country           TEXT,
    fx_reference_date DATE,
    -- data quality flags (for transparency, not filtering)
    had_null_customer BOOLEAN DEFAULT FALSE,
    had_null_category BOOLEAN DEFAULT FALSE,
    had_zero_price    BOOLEAN DEFAULT FALSE,
    -- audit
    cleaned_at        TIMESTAMPTZ DEFAULT NOW(),
    -- composite PK: one row per (order, sku) after dedup
    PRIMARY KEY (order_id, sku)
);

-- -------------------------------------------------------
-- FX RATES (EUR as base, daily granularity)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date         DATE        NOT NULL,
    base_currency     TEXT        NOT NULL DEFAULT 'EUR',
    target_currency   TEXT        NOT NULL,
    rate              NUMERIC(12, 6) NOT NULL,   -- 1 EUR = rate target_currency
    is_estimated      BOOLEAN     DEFAULT FALSE, -- TRUE if date was in the future when fetched
    fetched_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (rate_date, base_currency, target_currency)
);

-- -------------------------------------------------------
-- CUSTOMER SPEND IN EUR (Step 4)
-- Refreshed daily; dropped and recreated each run
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS customer_spend_eur (
    customer_id       INTEGER,
    customer_email    TEXT,
    country           TEXT,
    total_orders      INTEGER,
    total_items       INTEGER,
    total_spent_eur   NUMERIC(14, 4),
    last_order_date   DATE,
    -- audit
    computed_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (customer_id)
);

-- -------------------------------------------------------
-- COUNTRY / CATEGORY REVENUE (Step 5)
-- Refreshed daily; dropped and recreated each run
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS country_category_revenue (
    country           TEXT        NOT NULL,
    total_revenue_eur NUMERIC(14, 4),
    order_count       INTEGER,
    -- audit
    computed_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country)
);

-- -------------------------------------------------------
-- PIPELINE RUN LOG (for monitoring / observability)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id            SERIAL PRIMARY KEY,
    run_at            TIMESTAMPTZ DEFAULT NOW(),
    step_name         TEXT NOT NULL,
    status            TEXT NOT NULL,           -- 'success' | 'failure'
    rows_processed    INTEGER,
    error_message     TEXT,
    duration_seconds  NUMERIC(10, 2)
);
