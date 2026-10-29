# Release v1.0

Initial release of the Polymarket hourly Bitcoin prediction-market sample
dataset.

## Included

- Hourly Polymarket Bitcoin “Up or Down” market data
- BTCUSDT price observations sourced from Binance
- Best bid and best ask order-book observations
- Normalized SQLite database schema and database dump
- CSV and JSON dataset exports
- Import, cleanup, and export scripts
- Dataset metadata and CC0 1.0 licensing information
- Data gathering support

## Scope

This version covers 5 July 2026 from 05:00 through 13:00 UTC. It stores
approximately one observation per second. Individual order-book levels and
quantities are intentionally excluded; each snapshot contains L1 orderbook (the best bid and best ask).

## GitHub release information

- **Release name:** `Release v1.0`
- **Tag:** `v1.0`
