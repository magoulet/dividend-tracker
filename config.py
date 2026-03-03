import os
import psycopg2
from pymongo import MongoClient

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
