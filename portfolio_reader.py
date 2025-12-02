from datetime import datetime, timedelta, timezone
from config import get_db, PORTFOLIO_USD, PORTFOLIO_CAD

def get_latest_portfolio_snapshot():
    """Get the most recent portfolio snapshot from both USD and CAD collections"""
    db = get_db()
    
    holdings = {}
    
    # Get latest USD snapshot
    usd_snapshot = db[PORTFOLIO_USD].find_one(
        sort=[('date', -1)]
    )
    
    if usd_snapshot:
        for holding in usd_snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'USD',
                'snapshot_date': usd_snapshot['date']
            }
    
    # Get latest CAD snapshot
    cad_snapshot = db[PORTFOLIO_CAD].find_one(
        sort=[('date', -1)]
    )
    
    if cad_snapshot:
        for holding in cad_snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'CAD',
                'snapshot_date': cad_snapshot['date']
            }
    
    return list(holdings.values())


def get_portfolio_snapshot_at_date(target_date):
    """Get portfolio holdings at a specific date"""
    db = get_db()
    
    holdings = {}
    
    # Find USD snapshot on or before target date
    usd_snapshot = db[PORTFOLIO_USD].find_one(
        {'date': {'$lte': target_date}},
        sort=[('date', -1)]
    )
    
    if usd_snapshot:
        for holding in usd_snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'USD',
                'snapshot_date': usd_snapshot['date']
            }
    
    # Find CAD snapshot on or before target date
    cad_snapshot = db[PORTFOLIO_CAD].find_one(
        {'date': {'$lte': target_date}},
        sort=[('date', -1)]
    )
    
    if cad_snapshot:
        for holding in cad_snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            holdings[ticker] = {
                'ticker': ticker,
                'quantity': holding['Qty'],
                'currency': 'CAD',
                'snapshot_date': cad_snapshot['date']
            }
    
    return holdings


def get_recent_portfolio_tickers(lookback_days):
    """Get all unique tickers from portfolio snapshots within lookback window"""
    db = get_db()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    
    tickers = {}
    
    # Get recent USD snapshots
    usd_snapshots = db[PORTFOLIO_USD].find({'date': {'$gte': cutoff_date}})
    for snapshot in usd_snapshots:
        for holding in snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            tickers[ticker] = {'ticker': ticker, 'currency': 'USD'}
    
    # Get recent CAD snapshots  
    cad_snapshots = db[PORTFOLIO_CAD].find({'date': {'$gte': cutoff_date}})
    for snapshot in cad_snapshots:
        for holding in snapshot.get('portfolio_details', []):
            ticker = holding['Ticker']
            tickers[ticker] = {'ticker': ticker, 'currency': 'CAD'}
    
    return list(tickers.values())


if __name__ == '__main__':
    # Test
    holdings = get_latest_portfolio_snapshot()
    print(f"Found {len(holdings)} holdings:")
    for h in holdings:
        print(f"  {h['ticker']}: {h['quantity']} shares ({h['currency']})")
