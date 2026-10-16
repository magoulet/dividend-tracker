import os
import warnings

import psycopg2
from pymongo import MongoClient

# pandas emits a UserWarning when handed a raw psycopg2 connection, because
# only SQLAlchemy connections are officially tested. psycopg2 works fine here,
# and SQLAlchemy is not usable on this interpreter, so silence just that warning.
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy",
    category=UserWarning,
)

# MongoDB Configuration (legacy, can be removed after migration)
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
MONGO_DB = 'portfolio_tracker'

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'u2075INE')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'portfolio')

# Collections (legacy MongoDB names)
PORTFOLIO_USD = 'usd'
PORTFOLIO_CAD = 'cad'
DIVIDEND_HISTORY = 'dividend_history'
DIVIDEND_CACHE = 'dividend_cache'

# Cache Settings
CACHE_TTL_DAYS = 7

# Dividend Fetch Window
DIVIDEND_LOOKBACK_DAYS = 30

# Dividend Forecast Settings
FORECAST_HORIZON_MONTHS = 60       # months of forward income to project (5 years)
FORECAST_TTM_DAYS = 365            # trailing window used for the per-share run-rate
FORECAST_SEASONALITY_YEARS = 5     # completed calendar years used for seasonality

# Per-share dividend growth model
FORECAST_GROWTH_LOOKBACK_YEARS = 10  # max completed calendar years used to estimate growth
FORECAST_GROWTH_MIN_YEARS = 2        # min completed years of positive dividends to derive a rate
FORECAST_GROWTH_CLAMP_MIN = -0.05    # floor on the derived annual growth rate
FORECAST_GROWTH_CLAMP_MAX = 0.10     # ceiling on the derived annual growth rate
FORECAST_DEFAULT_GROWTH_RATE = 0.03  # fallback when history is insufficient
FORECAST_GROWTH_OVERRIDES = {        # ticker -> fixed annual growth (highest precedence)
    "JEPI": 0.0,                     # covered-call: distributions are variable, no trend
    "SGOV": 0.0,                     # rate-tracking: follows short-term rates
}

def get_db():
    """Get MongoDB database connection (legacy)"""
    client = MongoClient(MONGO_HOST, MONGO_PORT)
    return client[MONGO_DB]

def get_postgres_conn():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )
