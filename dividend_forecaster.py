#!/usr/bin/env python3
"""
Dividend Forecaster - Tier 0 (TTM run-rate) + per-share growth

Projects forward dividend income for current holdings using trailing
twelve month (TTM) dividends per share. Shares are assumed constant.

Growth: each ticker's forward dividends-per-share compound from year 1
onward by an annual rate derived from its own long-run per-share dividend
history (independent of how many shares are held):

  1. FORECAST_GROWTH_OVERRIDES        (manual, highest precedence)
  2. log-linear regression slope of annual per-share dividends, clamped
  3. FORECAST_DEFAULT_GROWTH_RATE     (fallback)

Each 12-month block is allocated across months using the ticker's
historical month-of-year seasonality (even split as fallback).

Output is written one row per (run_date, ticker, forecast_month) into the
`dividend_forecast` table.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np

from config import (
    FORECAST_DEFAULT_GROWTH_RATE,
    FORECAST_GROWTH_CLAMP_MAX,
    FORECAST_GROWTH_CLAMP_MIN,
    FORECAST_GROWTH_LOOKBACK_YEARS,
    FORECAST_GROWTH_MIN_YEARS,
    FORECAST_GROWTH_OVERRIDES,
    FORECAST_HORIZON_MONTHS,
    FORECAST_SEASONALITY_YEARS,
    FORECAST_TTM_DAYS,
    get_postgres_conn,
)
from dividend_fetcher import get_dividend_data
from portfolio_reader import get_latest_portfolio_snapshot

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dividend_forecast (
    run_date        DATE NOT NULL,
    ticker          VARCHAR(20) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    forecast_month  DATE NOT NULL,
    shares          NUMERIC(15,4),
    dps_forward     NUMERIC(10,6),
    amount          NUMERIC(15,2),
    growth_rate     NUMERIC(8,4),
    growth_source   VARCHAR(16),
    PRIMARY KEY (run_date, ticker, forecast_month)
)
"""


def ensure_schema(conn):
    """Create/upgrade the forecast table (self-healing)."""
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    cursor.execute(
        "ALTER TABLE dividend_forecast "
        "ADD COLUMN IF NOT EXISTS growth_source VARCHAR(16)"
    )
    conn.commit()
    cursor.close()


def _month_start(d):
    return d.replace(day=1)


def _add_months(d, months):
    """First day of the month `months` months after `d`."""
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def _as_utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _ttm_dividends(dividend_history, run_date):
    """Sum dividends per share over the trailing FORECAST_TTM_DAYS window."""
    cutoff = datetime.combine(
        run_date - timedelta(days=FORECAST_TTM_DAYS), datetime.min.time()
    ).replace(tzinfo=timezone.utc)

    total = 0.0
    count = 0
    for div in dividend_history:
        if _as_utc(div["date"]) >= cutoff:
            total += float(div["amount"])
            count += 1
    return total, count


def _seasonality_weights(dividend_history, run_date):
    """
    Fraction of annual dividends historically paid in each month (1-12).

    Uses completed calendar years only, so a partially elapsed current
    year does not bias the earlier months. Falls back to all available
    history if there are no completed years. Returns None when there is
    nothing usable (caller then splits evenly).
    """
    start_year = run_date.year - FORECAST_SEASONALITY_YEARS

    def collect(predicate):
        monthly = defaultdict(float)
        for div in dividend_history:
            if predicate(div["date"]):
                monthly[div["date"].month] += float(div["amount"])
        total = sum(monthly.values())
        if total <= 0:
            return None
        return {m: monthly.get(m, 0.0) / total for m in range(1, 13)}

    weights = collect(lambda d: start_year <= d.year < run_date.year)
    if weights is None:
        weights = collect(lambda d: d.year < run_date.year)
    return weights


def _annual_dps(dividend_history, run_date):
    """Per-share dividends summed by completed calendar year."""
    by_year = defaultdict(float)
    for div in dividend_history:
        year = div["date"].year
        if year < run_date.year:
            by_year[year] += float(div["amount"])
    return by_year


def compute_raw_growth(dividend_history, run_date):
    """
    Annual per-share dividend growth, estimated as the slope of a
    log-linear regression of annual DPS on year over the lookback window.
    Robust to volatility, gaps and single-year specials.
    Returns (raw_rate_or_None, years_used).
    """
    by_year = _annual_dps(dividend_history, run_date)
    start_year = run_date.year - FORECAST_GROWTH_LOOKBACK_YEARS
    points = [
        (year, by_year[year])
        for year in sorted(by_year)
        if year >= start_year and by_year[year] > 0
    ]
    if len(points) < FORECAST_GROWTH_MIN_YEARS:
        return None, len(points)

    years = np.array([year for year, _ in points], dtype=float)
    dps = np.array([value for _, value in points], dtype=float)
    slope = np.polyfit(years, np.log(dps), 1)[0]
    return math.exp(slope) - 1, len(points)


def estimate_growth_rate(ticker, dividend_history, run_date):
    """Resolve the annual growth rate and its source for a ticker."""
    if ticker in FORECAST_GROWTH_OVERRIDES:
        return FORECAST_GROWTH_OVERRIDES[ticker], "override"

    raw, _ = compute_raw_growth(dividend_history, run_date)
    if raw is None:
        return FORECAST_DEFAULT_GROWTH_RATE, "default"

    return min(max(raw, FORECAST_GROWTH_CLAMP_MIN), FORECAST_GROWTH_CLAMP_MAX), "derived"


def forecast_ticker(ticker, shares, run_date):
    """Build a monthly forward-income projection for a single ticker."""
    history = get_dividend_data(ticker)
    if not history:
        return None

    dps_ttm, count = _ttm_dividends(history, run_date)
    if dps_ttm <= 0:
        return None

    growth, source = estimate_growth_rate(ticker, history, run_date)

    start = _month_start(run_date)
    months = [_add_months(start, i) for i in range(FORECAST_HORIZON_MONTHS)]
    weights = _seasonality_weights(history, run_date)

    rows = []
    year1_income = 0.0
    total_income = 0.0
    for index, month in enumerate(months):
        block = index // 12  # 0 = year 1, 1 = year 2, ...
        # growth applies from year 1 onward
        dps = dps_ttm * (1 + growth) ** (block + 1)
        annual = shares * dps
        weight = (1 / 12) if weights is None else weights[month.month]
        amount = annual * weight
        rows.append({"month": month, "dps": dps, "amount": amount})
        if block == 0:
            year1_income += amount
        total_income += amount

    return {
        "ticker": ticker,
        "shares": shares,
        "dps_forward": dps_ttm,
        "ttm_payments": count,
        "growth_rate": growth,
        "growth_source": source,
        "annual_income": year1_income,   # next 12 months
        "total_income": total_income,    # whole horizon
        "rows": rows,
    }


def run_forecast(run_date=None):
    """Forecast forward dividend income for all current holdings."""
    run_date = run_date or date.today()
    holdings = get_latest_portfolio_snapshot()

    conn = get_postgres_conn()
    year1_by_currency = defaultdict(float)
    total_by_currency = defaultdict(float)
    try:
        ensure_schema(conn)
        cursor = conn.cursor()

        # Idempotent re-run: clear this run_date before inserting fresh rows.
        cursor.execute("DELETE FROM dividend_forecast WHERE run_date = %s", (run_date,))
        conn.commit()

        rows = []
        for holding in holdings:
            ticker = holding["ticker"]
            shares = float(holding["quantity"])
            if shares <= 0:
                continue

            result = forecast_ticker(ticker, shares, run_date)
            if not result:
                print(f"  [SKIP] {ticker}: no positive trailing dividends")
                continue

            currency = holding["currency"]
            year1_by_currency[currency] += result["annual_income"]
            total_by_currency[currency] += result["total_income"]
            for row in result["rows"]:
                rows.append((
                    run_date, ticker, currency, row["month"], shares,
                    row["dps"], row["amount"], result["growth_rate"],
                    result["growth_source"],
                ))
            print(
                f"  [FORECAST] {ticker}: {shares:,.1f} sh x "
                f"${result['dps_forward']:.4f} "
                f"(g={result['growth_rate']:+.1%} {result['growth_source']}) "
                f"= ${result['annual_income']:,.2f}/yr"
            )

        if rows:
            cursor.executemany(
                """
                INSERT INTO dividend_forecast
                    (run_date, ticker, currency, forecast_month, shares,
                     dps_forward, amount, growth_rate, growth_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            conn.commit()
        cursor.close()
    finally:
        conn.close()

    print(f"\n  Run date: {run_date}")
    for currency in sorted(set(year1_by_currency) | set(total_by_currency)):
        print(
            f"  {currency}: ${year1_by_currency[currency]:,.2f}/yr next 12m, "
            f"${total_by_currency[currency]:,.2f} over {FORECAST_HORIZON_MONTHS // 12}y"
        )

    return year1_by_currency


if __name__ == "__main__":
    print("=" * 60)
    print("Dividend Forecaster")
    print("=" * 60)
    run_forecast()
