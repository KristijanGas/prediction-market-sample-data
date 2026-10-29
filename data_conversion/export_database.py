"""Export the SQLite database to one JSON file and one CSV per table."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = REPO_ROOT / "database" / "prediction_market.db"
DEFAULT_OUTPUT_DIRECTORY = REPO_ROOT / "database" / "exports"

TABLES = (
    "trading_date",
    "market_hour",
    "market_asset",
    "observation",
    "crypto_price",
    "order_book_state",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export all database tables to JSON and CSV files."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"SQLite database path (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=f"Export directory (default: {DEFAULT_OUTPUT_DIRECTORY})",
    )
    return parser.parse_args()


def export_database(database_path: Path, output_directory: Path) -> int:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    output_directory.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        with (output_directory / "database.json").open(
            "w", encoding="utf-8"
        ) as json_file:
            json_file.write("{\n")
            for table_index, table in enumerate(TABLES):
                cursor = connection.execute(f"SELECT * FROM {table}")
                columns = [column[0] for column in cursor.description]
                csv_path = output_directory / f"{table}.csv"
                with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=columns)
                    writer.writeheader()
                    json_file.write(f"  {json.dumps(table)}: [\n")
                    for row_index, row in enumerate(cursor):
                        row_data = dict(zip(columns, row))
                        writer.writerow(row_data)
                        if row_index:
                            json_file.write(",\n")
                        json.dump(row_data, json_file, ensure_ascii=False)
                    json_file.write("\n  ]")
                if table_index < len(TABLES) - 1:
                    json_file.write(",")
                json_file.write("\n")
            json_file.write("}\n")
    return len(TABLES) + 1


def main() -> int:
    args = parse_args()
    try:
        file_count = export_database(args.database.resolve(), args.output.resolve())
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Error exporting database: {error}")
        return 1
    print(f"Exported {file_count} files to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
