#!/usr/bin/env python3
"""
Dividend Forecaster - Tier 0 (TTM run-rate)

Projects forward dividend income for current holdings using trailing
twelve month (TTM) dividends per share. Shares are assumed constant.

The annual TTM amount for each ticker is allocated across the next
FORECAST_HORIZON_MONTHS calendar months using that ticker's historical
month-of-year seasonality (falling back to an even split when there is
no usable history). The forecast total therefore stays anchored to the
actual TTM run-rate; only the *timing* is modeled.

Output is written one row per (run_date, ticker, forecast_month) into
the `dividend_forecast` table.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from config import (
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
    PRIMARY KEY (run_date, ticker, forecast_month)
)
"""


def ensure_schema(conn):
    """Create the forecast table if it does not exist yet (self-healing)."""
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
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


def forecast_ticker(ticker, shares, run_date):
    """Build a monthly forward-income projection for a single ticker."""
    history = get_dividend_data(ticker)
    if not history:
        return None

    dps_ttm, count = _ttm_dividends(history, run_date)
    if dps_ttm <= 0:
        return None

    annual_income = shares * dps_ttm
    start = _month_start(run_date)
    months = [_add_months(start, i) for i in range(FORECAST_HORIZON_MONTHS)]

    weights = _seasonality_weights(history, run_date)
    if weights is None:
        amounts = [annual_income / len(months)] * len(months)
    else:
        amounts = [annual_income * weights[m.month] for m in months]

    return {
        "ticker": ticker,
        "shares": shares,
        "dps_forward": dps_ttm,
        "ttm_payments": count,
        "annual_income": annual_income,
        "months": months,
        "amounts": amounts,
    }


def run_forecast(run_date=None):
    """Forecast forward dividend income for all current holdings."""
    run_date = run_date or date.today()
    holdings = get_latest_portfolio_snapshot()

    conn = get_postgres_conn()
    annual_by_currency = defaultdict(float)
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

            annual_by_currency[holding["currency"]] += result["annual_income"]
            for month, amount in zip(result["months"], result["amounts"]):
                rows.append((
                    run_date,
                    ticker,
                    holding["currency"],
                    month,
                    shares,
                    result["dps_forward"],
                    amount,
                    0.0,  # Tier 0: no growth applied
                ))
            print(
                f"  [FORECAST] {ticker}: {shares:,.1f} sh x "
                f"${result['dps_forward']:.4f} = ${result['annual_income']:,.2f}/yr"
            )

        if rows:
            cursor.executemany(
                """
                INSERT INTO dividend_forecast
                    (run_date, ticker, currency, forecast_month,
                     shares, dps_forward, amount, growth_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            conn.commit()
        cursor.close()
    finally:
        conn.close()

    print(f"\n  Run date: {run_date}")
    for currency, total in sorted(annual_by_currency.items()):
        print(f"  Projected next 12 months ({currency}): ${total:,.2f}")

    return annual_by_currency


if __name__ == "__main__":
    print("=" * 60)
    print("Dividend Forecaster - Tier 0 (TTM run-rate)")
    print("=" * 60)
    run_forecast()
