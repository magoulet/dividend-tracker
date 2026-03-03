import yfinance as yf
from datetime import datetime, timedelta, timezone
from config import get_postgres_conn, CACHE_TTL_DAYS
import pandas as pd


def get_dividend_data(ticker, force_refresh=False):
    """
    Fetch dividend data for a ticker with caching
    Returns list of historical dividends
    """
    conn = get_postgres_conn()
    
    now_utc = datetime.now(timezone.utc)
    
    # Check cache first
    if not force_refresh:
        cached_df = pd.read_sql("""
            SELECT dividend_data, last_updated 
            FROM dividend_cache 
            WHERE ticker = %s
        """, conn, params=(ticker,))
        
        if not cached_df.empty:
            cached = cached_df.iloc[0]
            last_updated = cached['last_updated']
            if last_updated:
                cache_age = now_utc - last_updated.replace(tzinfo=timezone.utc)
                if cache_age < timedelta(days=CACHE_TTL_DAYS):
                    print(f"  [CACHE HIT] {ticker} (age: {cache_age.days} days)")
                    # Convert JSON string back to list with datetime objects
                    dividend_data = cached['dividend_data']
                    if isinstance(dividend_data, str):
                        import json
                        data_list = json.loads(dividend_data)
                    else:
                        data_list = dividend_data
                    # Convert date strings back to datetime
                    for div in data_list:
                        if isinstance(div['date'], str):
                            div['date'] = datetime.fromisoformat(div['date'])
                    return data_list
    
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
        
        # Convert datetime to string for JSON serialization
        dividend_data_json = []
        for div in dividend_data:
            dividend_data_json.append({
                'date': div['date'].isoformat(),
                'amount': div['amount']
            })
        
        # Update cache in postgres
        import json
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dividend_cache (ticker, dividend_data, last_updated)
            VALUES (%s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET dividend_data = EXCLUDED.dividend_data, last_updated = EXCLUDED.last_updated
        """, (ticker, json.dumps(dividend_data_json), now_utc))
        conn.commit()
        cursor.close()
        
        print(f"  [SUCCESS] Found {len(dividend_data)} historical dividends for {ticker}")
        return dividend_data
    
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {ticker}: {str(e)}")
        return []
    finally:
        conn.close()





if __name__ == '__main__':
    # Test
    test_ticker = 'VTI'
    divs = get_dividend_data(test_ticker)
    print(f"\nLast 3 dividends for {test_ticker}:")
    for div in divs[:3]:
        print(f"  {div['date'].strftime('%Y-%m-%d')}: ${div['amount']}")