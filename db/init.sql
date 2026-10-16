-- Dividend forecast output table.
-- One row per (run_date, ticker, forecast_month). The forecaster also runs
-- CREATE TABLE IF NOT EXISTS at startup, so this file is for reference /
-- manual bootstrapping only.
CREATE TABLE IF NOT EXISTS dividend_forecast (
    run_date        DATE NOT NULL,
    ticker          VARCHAR(20) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    forecast_month  DATE NOT NULL,       -- first day of the month
    shares          NUMERIC(15,4),
    dps_forward     NUMERIC(10,6),
    amount          NUMERIC(15,2),
    growth_rate     NUMERIC(8,4),
    PRIMARY KEY (run_date, ticker, forecast_month)
);

CREATE INDEX IF NOT EXISTS dividend_forecast_run_date_idx
    ON dividend_forecast (run_date);
