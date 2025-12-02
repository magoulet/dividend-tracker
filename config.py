import os
from pymongo import MongoClient

# MongoDB Configuration
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
MONGO_DB = 'portfolio_tracker'

# Collections
PORTFOLIO_USD = 'usd'
PORTFOLIO_CAD = 'cad'
DIVIDEND_HISTORY = 'dividend_history'
DIVIDEND_CACHE = 'dividend_cache'

# Cache Settings
CACHE_TTL_DAYS = 7

# Dividend Fetch Window
DIVIDEND_LOOKBACK_DAYS = 30 # Check for ex-dates in last x days

def get_db():
    """Get MongoDB database connection"""
    client = MongoClient(MONGO_HOST, MONGO_PORT)
    return client[MONGO_DB]
