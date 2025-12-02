import yfinance as yf
from datetime import datetime, timedelta, timezone
from config import get_db, DIVIDEND_CACHE, CACHE_TTL_DAYS

def get_dividend_data(ticker, force_refresh=False):
    """
    Fetch dividend data for a ticker with caching
    Returns list of historical dividends
    """
    db = get_db()
    cache_collection = db[DIVIDEND_CACHE]
    
    now_utc = datetime.now(timezone.utc)
    
    # Check cache first
    if not force_refresh:
        cached = cache_collection.find_one({'ticker': ticker})
        if cached:
            cache_age = now_utc - cached['last_updated'].replace(tzinfo=timezone.utc)
            if cache_age < timedelta(days=CACHE_TTL_DAYS):
                print(f"  [CACHE HIT] {ticker} (age: {cache_age.days} days)")
                return cached.get('dividend_data', [])
    
    # Fetch from yfinance
    print(f"  [API CALL] Fetching dividend data for {ticker}")
    try:
        stock = yf.Ticker(ticker)
        dividends_df = stock.dividends
        
        if dividends_df is None or dividends_df.empty:
            print(f"  [WARNING] No dividend data for {ticker}")
            return []
        
        # Convert to list of dicts
        dividend_data = []
        for date, amount in dividends_df.items():
            div_date = date.to_pydatetime()
            # Ensure timezone-aware
            if div_date.tzinfo is None:
                div_date = div_date.replace(tzinfo=timezone.utc)
            
            dividend_data.append({
                'date': div_date,
                'amount': float(amount)
            })
        
        # Sort by date descending
        dividend_data.sort(key=lambda x: x['date'], reverse=True)
        
        # Update cache
        cache_collection.update_one(
            {'ticker': ticker},
            {
                '$set': {
                    'ticker': ticker,
                    'dividend_data': dividend_data,
                    'last_updated': now_utc
                }
            },
            upsert=True
        )
        
        print(f"  [SUCCESS] Found {len(dividend_data)} historical dividends for {ticker}")
        return dividend_data
    
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {ticker}: {str(e)}")
        return []





if __name__ == '__main__':
    # Test
    test_ticker = 'VTI'
    divs = get_dividend_data(test_ticker)
    print(f"\nLast 3 dividends for {test_ticker}:")
    for div in divs[:3]:
        print(f"  {div['date'].strftime('%Y-%m-%d')}: ${div['amount']}")