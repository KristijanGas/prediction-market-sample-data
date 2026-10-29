# Polymarket hourly BTC markets

## About

This repository contains a free-to-use sample dataset of hourly Bitcoin
“Up or Down” prediction markets from Polymarket. The dataset combines
Polymarket market metadata and order-book observations with BTCUSDT prices
from Binance.

The data is intended for learning, experimentation, data engineering,
time-series analysis, and research involving prediction markets and
cryptocurrency market data. The repository demonstrates how to create a
normalized SQLite database and automatically export its contents as
machine-readable CSV and JSON files.

## Dataset metadata

- **Dataset name:** Polymarket hourly Bitcoin prediction markets
- **Version:** 1.0
- **Author:** KristijanGas
- **License:** CC0 1.0 Universal; this dedicates the dataset to the public
  domain to the fullest extent permitted by law; see [LICENSE](LICENSE)
- **Data language:** English
- **Data type:** Time-series and prediction-market data
- **Prediction market source:** Polymarket
- **Cryptocurrency price source:** Binance BTCUSDT
- **Database format:** SQLite
- **Export formats:** CSV and JSON
- **Sampling interval:** Approximately one observation per second
- **Covered period:** 5 July 2026, 05:00–13:00 UTC
- **Market outcomes:** `Up` and `Down`
- **Dataset files:** `polymarket_btc_hourly.csv` and `polymarket_btc_hourly.json`

### Dataset contents

Each exported snapshot represents one order-book state and contains:

- `trading_date_id` and `calendar_date`: date identifiers
- `market_hour_id`, `hour_start`, and `hour_end`: hourly market interval
- `asset_id`, `token_id`, and `outcome`: Polymarket asset information
- `observation_id` and `observed_at`: observation identifiers and timestamp
- `price_symbol`, `price`, and `price_source`: cryptocurrency price data
- `order_book_state_id`: order-book snapshot identifier
- `best_bid` and `best_ask`: best available bid and ask prices

This version intentionally stores only the best bid and best ask for each
order-book state. Individual order-book levels and quantities are not included
in the exported dataset.

## Database utilities

The SQLite database is stored at `database/prediction_market.db`.

Add a dataset folder to the database:

```bash
.venv/bin/python data_conversion/add_to_database.py datasets/bitcoin-up-or-down
```

Remove all rows while preserving the database schema:

```bash
.venv/bin/python data_conversion/empty_db.py
```

Export the database to `database/exports/`:

```bash
.venv/bin/python data_conversion/export_database.py
```

The export contains one `database.json` file, one CSV file for each database
table, and normalized `all.csv` and `all.json` snapshot files. The snapshot
files contain one record per order-book state, without repeating hourly JSON
metadata on every row.

## Release v1.0

Release v1.0 contains:

- this dataset description and metadata
- the CC0 1.0 license
- the normalized SQLite schema
- the SQLite database dump
- the CSV and JSON dataset exports
- scripts for importing, cleaning, and exporting the database

- **Release name:** `Release v1.0`
- **Git tag:** `v1.0`
