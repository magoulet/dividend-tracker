from datetime import datetime, timedelta, timezone
from config import get_db, DIVIDEND_HISTORY, DIVIDEND_LOOKBACK_DAYS
from portfolio_reader import get_portfolio_snapshot_at_date
from dividend_fetcher import get_dividend_data

def process_ticker_dividends(ticker, quantity, currency):
    """Process dividends for a single ticker"""
    db = get_db()
    
    # Get dividend history
    dividend_history = get_dividend_data(ticker)
    
    if not dividend_history:
        return
    
    # Check for recent ex-dividend dates (lookback window)
    # Use timezone-aware datetime
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
        existing = db[DIVIDEND_HISTORY].find_one({
            'ticker': ticker,
            'ex_dividend_date': ex_date
        })
        
        if existing:
            continue
        
        # Get portfolio snapshot at ex-dividend date
        snapshot = get_portfolio_snapshot_at_date(ex_date)
        
        if ticker in snapshot:
            shares_held = snapshot[ticker]['quantity']
            dividend_amount = shares_held * div['amount']
            
            # Record dividend
            db[DIVIDEND_HISTORY].insert_one({
                'ticker': ticker,
                'currency': currency,
                'ex_dividend_date': ex_date,
                'payment_date': ex_date + timedelta(days=7),  # Estimate payment date
                'dividend_per_share': div['amount'],
                'shares_held': shares_held,
                'dividend_amount': dividend_amount,
                'status': 'recorded',
                'recorded_at': now_utc
            })
            
            print(f"  [RECORDED] {ticker}: $${dividend_amount:.2f} ({shares_held} shares × $${div['amount']})")
    
