# prediction-market-sample-data

This repository provides a free-to-use sample dataset of hourly Bitcoin
up-or-down prediction markets from Polymarket.

The dataset contains hourly market metadata, cryptocurrency prices, market
observations, and order-book states for the related Polymarket assets. It is
intended for experimentation, analysis, data engineering, and research
projects involving prediction markets and cryptocurrency market data.

Do note that the rate of saving for this database is around every ~1 second.

## Database utilities

The SQLite database is stored at `database/prediction_market.db`.

Add from dataset:

```bash
.venv/bin/python data_conversion/add_to_database.py datasets/bitcoin-up-or-down
```

Remove all rows:

```bash
.venv/bin/python data_conversion/empty_db.py
```

Export the complete database to `database/exports/`:

```bash
.venv/bin/python data_conversion/export_database.py
```

The export contains one `database.json` file, one CSV file for each database
table, and normalized `all.csv` and `all.json` snapshot files. Each snapshot
file has one record per order-book state, with links to the related market
hour, observation, asset, and crypto price. Hourly metadata remains in the
`market_hour` export instead of being repeated on every snapshot row (the file becomes way too big and crashes vscode). If
order-book levels are present, bid and ask levels are included in each
snapshot as JSON arrays.