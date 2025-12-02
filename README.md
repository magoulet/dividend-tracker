# Dividend Tracker

A Python tool that automatically tracks dividend payments for your portfolio holdings.

## Overview

This system fetches dividend data from Yahoo Finance (via yfinance) and records dividend payments based on your historical portfolio positions. It maintains a cache of dividend data and only processes recent dividends to avoid duplicate entries.

## Key Features

- Fetches dividend data with caching (7-day TTL)
- Records dividends based on actual share ownership on ex-dividend dates
- Processes all tickers held within the last 30 days (not just current holdings)
- Supports both USD and CAD portfolio collections
- Timezone-aware date handling

## Usage

```bash
python main.py
```

## Configuration

Set MongoDB connection via environment variables:
- `MONGO_HOST` (default: localhost)
- `MONGO_PORT` (default: 27017)

## Database Collections

- `usd` / `cad` - Portfolio snapshots
- `dividend_history` - Recorded dividend payments
- `dividend_cache` - Cached dividend data from yfinance