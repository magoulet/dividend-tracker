#!/usr/bin/env python3
"""
One-time backfill of dividend_history from dividend_cache.

The daily tracker only records ex-dividends within a DIVIDEND_LOOKBACK_DAYS
window, so older payments can be permanently missed. This replays every
cached ex-dividend date against the historical portfolio snapshots and
inserts any rows that are missing.

Run once (or occasionally):

    python backfill_dividends.py --dry-run   # preview
    python backfill_dividends.py             # write
"""
import argparse
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone

from config import get_postgres_conn
from dividend_fetcher import get_dividend_data


def load_snapshots(conn):
    """All snapshots as (sorted_dates, holdings_by_index).

    holdings_by_index[i] maps ticker -> {'qty': float, 'currency': str} for
    the snapshot on sorted_dates[i].
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, currency, portfolio_details "
        "FROM portfolio_snapshots ORDER BY date"
    )
    rows = cursor.fetchall()
    cursor.close()

    snap_dates = []
    snap_holdings = []
    # portfolio_snapshots has one row per (date, currency); merge both
    # currencies into a single holdings map per date.
    by_date = {}
    for snap_date, snap_currency, details in rows:
        holdings = by_date.setdefault(snap_date, {})
        for item in details or []:
            holdings[item["Ticker"]] = {
                "qty": float(item["Qty"]),
                "currency": snap_currency,
            }
    for snap_date in sorted(by_date):
        snap_dates.append(snap_date)
        snap_holdings.append(by_date[snap_date])
    return snap_dates, snap_holdings


def shares_held(snap_dates, snap_holdings, target_date, ticker):
    """Latest holding of ticker on or before target_date, or None."""
    index = bisect_right(snap_dates, target_date) - 1
    if index < 0:
        return None
    return snap_holdings[index].get(ticker)


def main():
    parser = argparse.ArgumentParser(description="Backfill dividend history")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    today = date.today()
    now = datetime.now(timezone.utc)

    conn = get_postgres_conn()
    try:
        snap_dates, snap_holdings = load_snapshots(conn)
        if not snap_dates:
            print("No portfolio snapshots found; nothing to backfill.")
            return
        earliest_snapshot = snap_dates[0]

        # Every ticker ever held, with its currency.
        tickers = {}
        for holdings in snap_holdings:
            for ticker, info in holdings.items():
                if ticker not in tickers and info["currency"]:
                    tickers[ticker] = info["currency"]

        print(
            f"Snapshots: {snap_dates[0]} .. {snap_dates[-1]} | "
            f"{len(tickers)} tickers | dry_run={args.dry_run}"
        )

        cursor = conn.cursor()
        cursor.execute("SELECT ticker, ex_dividend_date FROM dividend_history")
        existing = {(t, d) for t, d in cursor.fetchall()}
        checked = inserted = existed = no_holding = 0

        for ticker, currency in sorted(tickers.items()):
            history = get_dividend_data(ticker)
            for div in history:
                ex_date = div["date"].date()
                if ex_date > today or ex_date < earliest_snapshot:
                    continue
                checked += 1

                if (ticker, ex_date) in existing:
                    existed += 1
                    continue

                holding = shares_held(snap_dates, snap_holdings, ex_date, ticker)
                if not holding or holding["qty"] <= 0:
                    no_holding += 1
                    continue

                shares = holding["qty"]
                amount = shares * float(div["amount"])
                existing.add((ticker, ex_date))
                if args.dry_run:
                    print(
                        f"  [WOULD ADD] {ticker} {ex_date} "
                        f"{shares:,.1f} x ${float(div['amount']):.4f} "
                        f"= ${amount:,.2f}"
                    )
                    inserted += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO dividend_history
                        (ticker, currency, ex_dividend_date, payment_date,
                         dividend_per_share, shares_held, dividend_amount,
                         status, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'recorded', %s)
                    ON CONFLICT (ticker, ex_dividend_date) DO NOTHING
                    """,
                    (
                        ticker,
                        currency,
                        ex_date,
                        ex_date + timedelta(days=7),
                        float(div["amount"]),
                        shares,
                        amount,
                        now,
                    ),
                )
                inserted += cursor.rowcount

        if not args.dry_run:
            conn.commit()
        cursor.close()

        print(
            f"\nChecked {checked} ex-dates | inserted {inserted} | "
            f"already present {existed} | no holding {no_holding}"
        )
        if args.dry_run:
            print("Dry run - nothing written.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
