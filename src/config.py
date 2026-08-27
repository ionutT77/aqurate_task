"""
config.py — centralised configuration loaded from .env
All other modules import from here; nothing reads os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Required — loaded from .env or GitHub Secrets
DATABASE_URL: str = os.environ["DATABASE_URL"]

ORDERS_API_URL: str = os.getenv(
    "ORDERS_API_URL",
    "https://jzozteoirwfczccltcdr.supabase.co/rest/v1/orders_raw",
)
ORDERS_API_KEY: str = os.getenv(
    "ORDERS_API_KEY",
    "sb_publishable_Xwjiw--qkKcbMuSbKd6I2w_wN9mpNTv",
)

FX_API_BASE_URL: str = os.getenv("FX_API_BASE_URL", "https://api.frankfurter.dev/v1")

# Pipeline constants
# Currencies present in orders_raw that need FX conversion to EUR
NON_EUR_CURRENCIES = ["RON"]

# Categories to include in the country/category revenue table
REVENUE_CATEGORIES = ["Books", "Electronics"]

# Minimum EUR revenue for country/category table
REVENUE_THRESHOLD_EUR = 40_000
