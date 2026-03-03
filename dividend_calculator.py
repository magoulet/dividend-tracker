from datetime import datetime, timedelta, timezone
from config import get_postgres_conn, DIVIDEND_HISTORY, DIVIDEND_LOOKBACK_DAYS
from portfolio_reader import get_portfolio_snapshot_at_date
from dividend_fetcher import get_dividend_data
import pandas as pd


def process_ticker_dividends(ticker, quantity, currency):
    """Process dividends for a single ticker"""
    conn = get_postgres_conn()
    
    # Get dividend history
    dividend_history = get_dividend_data(ticker)
    
    if not dividend_history:
        return
    
    # Check for recent ex-dividend dates (lookback window)
    now_utc = datetime.now(timezone.utc)
    lookback_date = now_utc - timedelta(days=DIVIDEND_LOOKBACK_DAYS)
    
    for div in dividend_history:
        ex_date = div['date']
        
        # Make ex_date timezone-aware if it's not
        if ex_date.tzinfo is None:
            ex_date = ex_date.replace(tzinfo=timezone.utc)
        
        # Only process recent dividends
        if ex_date < lookback_date:
            continue
        
        # Check if we already recorded this dividend
        ex_date_date = ex_date.date()
        existing_df = pd.read_sql("""
            SELECT id FROM dividend_history 
            WHERE ticker = %s AND ex_dividend_date = %s
        """, conn, params=(ticker, ex_date_date))
        
        if not existing_df.empty:
            continue
        
        # Get portfolio snapshot at ex-dividend date
        snapshot = get_portfolio_snapshot_at_date(ex_date)
        
        if ticker in snapshot:
            shares_held = snapshot[ticker]['quantity']
            dividend_amount = shares_held * div['amount']
            
            # Record dividend
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dividend_history 
                (ticker, currency, ex_dividend_date, payment_date, dividend_per_share, shares_held, dividend_amount, status, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ticker,
                currency,
                ex_date_date,
                ex_date_date + timedelta(days=7),
                div['amount'],
                shares_held,
                dividend_amount,
                'recorded',
                now_utc
            ))
            conn.commit()
            cursor.close()
            
            print(f"  [RECORDED] {ticker}: $${dividend_amount:.2f} ({shares_held} shares × $${div['amount']})")
    
    conn.close()
    
