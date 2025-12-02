#!/usr/bin/env python3
"""
Dividend Tracker - Main Orchestrator
"""
from datetime import datetime
from portfolio_reader import get_recent_portfolio_tickers
from dividend_calculator import process_ticker_dividends
from config import DIVIDEND_LOOKBACK_DAYS

def main():
    print("=" * 60)
    print(f"Dividend Tracker - Running at {datetime.now()}")
    print("=" * 60)
    
    # Get recent portfolio tickers
    print("\n[1] Reading recent portfolio tickers...")
    tickers = get_recent_portfolio_tickers(DIVIDEND_LOOKBACK_DAYS)
    print(f"    Found {len(tickers)} unique tickers from last {DIVIDEND_LOOKBACK_DAYS} days")
    
    # Process each ticker
    print("\n[2] Processing dividends...")
    for ticker_info in tickers:
        ticker = ticker_info['ticker']
        currency = ticker_info['currency']
        
        print(f"\n  Processing {ticker} ({currency})...")
        process_ticker_dividends(ticker, None, currency)
    
    print("\n" + "=" * 60)
    print("Dividend tracker complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
