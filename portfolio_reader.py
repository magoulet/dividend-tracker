from datetime import datetime, timedelta, timezone
from config import get_postgres_conn, PORTFOLIO_USD, PORTFOLIO_CAD
import pandas as pd


def get_latest_portfolio_snapshot():
    """Get the most recent portfolio snapshot from both USD and CAD in postgres"""
    conn = get_postgres_conn()
    
    holdings = {}
    
    # Get latest USD snapshot
    usd_df = pd.read_sql("""
        SELECT portfolio_details, date 
        FROM portfolio_snapshots 
        WHERE currency = 'USD'
        ORDER BY date DESC 
        LIMIT 1
    """, conn)
    
    if not usd_df.empty:
        usd_snapshot = usd_df.iloc[0]
        for holding in usd_snapshot['portfolio_details']:
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'USD',
                'snapshot_date': usd_snapshot['date']
            }
    
    # Get latest CAD snapshot
    cad_df = pd.read_sql("""
        SELECT portfolio_details, date 
        FROM portfolio_snapshots 
        WHERE currency = 'CAD'
        ORDER BY date DESC 
        LIMIT 1
    """, conn)
    
    if not cad_df.empty:
        cad_snapshot = cad_df.iloc[0]
        for holding in cad_snapshot['portfolio_details']:
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'CAD',
                'snapshot_date': cad_snapshot['date']
            }
    
    conn.close()
    return list(holdings.values())


def get_portfolio_snapshot_at_date(target_date):
    """Get portfolio holdings at a specific date"""
    conn = get_postgres_conn()
    
    holdings = {}
    
    # Find USD snapshot on or before target date
    usd_df = pd.read_sql("""
        SELECT portfolio_details, date 
        FROM portfolio_snapshots 
        WHERE currency = 'USD' AND date <= %s
        ORDER BY date DESC 
        LIMIT 1
    """, conn, params=(target_date,))
    
    if not usd_df.empty:
        usd_snapshot = usd_df.iloc[0]
        for holding in usd_snapshot['portfolio_details']:
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'USD',
                'snapshot_date': usd_snapshot['date']
            }
    
    # Find CAD snapshot on or before target date
    cad_df = pd.read_sql("""
        SELECT portfolio_details, date 
        FROM portfolio_snapshots 
        WHERE currency = 'CAD' AND date <= %s
        ORDER BY date DESC 
        LIMIT 1
    """, conn, params=(target_date,))
    
    if not cad_df.empty:
        cad_snapshot = cad_df.iloc[0]
        for holding in cad_snapshot['portfolio_details']:
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'CAD',
                'snapshot_date': cad_snapshot['date']
            }
    
    conn.close()
    return holdings


def get_recent_portfolio_tickers(lookback_days):
    """Get all unique tickers from portfolio snapshots within lookback window"""
    conn = get_postgres_conn()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    
    tickers = {}
    
    # Get recent USD snapshots
    usd_df = pd.read_sql("""
        SELECT portfolio_details 
        FROM portfolio_snapshots 
        WHERE currency = 'USD' AND date >= %s
    """, conn, params=(cutoff_date.date(),))
    
    for _, row in usd_df.iterrows():
        for holding in row['portfolio_details']:
            ticker = holding['Ticker']
            tickers[ticker] = {'ticker': ticker, 'currency': 'USD'}
    
    # Get recent CAD snapshots
    cad_df = pd.read_sql("""
        SELECT portfolio_details 
        FROM portfolio_snapshots 
        WHERE currency = 'CAD' AND date >= %s
    """, conn, params=(cutoff_date.date(),))
    
    for _, row in cad_df.iterrows():
        for holding in row['portfolio_details']:
            ticker = holding['Ticker']
            tickers[ticker] = {'ticker': ticker, 'currency': 'CAD'}
    
    conn.close()
    return list(tickers.values())


if __name__ == '__main__':
    # Test
    holdings = get_latest_portfolio_snapshot()
    print(f"Found {len(holdings)} holdings:")
    for h in holdings:
        print(f"  {h['ticker']}: {h['quantity']} shares ({h['currency']})")
