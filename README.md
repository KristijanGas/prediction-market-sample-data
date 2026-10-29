# prediction-market-sample-data

## Database utilities

The SQLite database is stored at `database/prediction_market.db`.

Remove all rows while preserving the database schema:

```bash
.venv/bin/python data_conversion/empty_db.py
```

Export the complete database to `database/exports/`:

```bash
.venv/bin/python data_conversion/export_database.py
```

The export contains one `database.json` file and one CSV file for each
database table. A different database or output directory can be selected with
`--database` and `--output`.