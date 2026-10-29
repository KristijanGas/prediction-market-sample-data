"""Export the SQLite database to normalized JSON and CSV files."""

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

SNAPSHOT_QUERY = """
    SELECT
        date.trading_date_id AS trading_date_id,
        date.calendar_date AS calendar_date,
        hour.market_hour_id AS market_hour_id,
        hour.hour_start AS hour_start,
        hour.hour_end AS hour_end,
        asset.asset_id AS asset_id,
        asset.token_id AS token_id,
        asset.outcome AS outcome,
        observation.observation_id AS observation_id,
        observation.observed_at AS observed_at,
        price.symbol AS price_symbol,
        price.price AS price,
        price.source AS price_source,
        state.order_book_state_id AS order_book_state_id,
        state.best_bid AS best_bid,
        state.best_ask AS best_ask
    FROM order_book_state AS state
    JOIN observation
        ON observation.observation_id = state.observation_id
    JOIN market_hour AS hour
        ON hour.market_hour_id = observation.market_hour_id
    JOIN trading_date AS date
        ON date.trading_date_id = hour.trading_date_id
    JOIN market_asset AS asset
        ON asset.asset_id = state.asset_id
    LEFT JOIN crypto_price AS price
        ON price.observation_id = observation.observation_id
    ORDER BY state.order_book_state_id
"""

LEVELS_QUERY = """
    SELECT order_book_state_id, side, price, quantity
    FROM order_book_level
    ORDER BY order_book_state_id, order_book_level_id
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export normalized database JSON and CSV files."
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


def export_snapshots(connection: sqlite3.Connection, output_directory: Path) -> None:
    level_table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'order_book_level'
        """
    ).fetchone()
    snapshot_cursor = connection.execute(SNAPSHOT_QUERY)
    columns = [column[0] for column in snapshot_cursor.description]
    columns.extend(["bid_levels", "ask_levels"])

    level_cursor = (
        connection.execute(LEVELS_QUERY) if level_table_exists else None
    )
    next_level = next(level_cursor, None) if level_cursor else None

    def levels_for_state(state_id: int) -> tuple[str | None, str | None]:
        nonlocal next_level
        if level_cursor is None:
            return None, None

        bids: list[dict[str, object]] = []
        asks: list[dict[str, object]] = []
        while next_level is not None and next_level[0] < state_id:
            next_level = next(level_cursor, None)
        while next_level is not None and next_level[0] == state_id:
            _, side, price, quantity = next_level
            level = {"price": price, "quantity": quantity}
            (bids if side == "bid" else asks).append(level)
            next_level = next(level_cursor, None)
        return json.dumps(bids), json.dumps(asks)

    with (
        (output_directory / "all.csv").open("w", newline="", encoding="utf-8") as csv_file,
        (output_directory / "all.json").open("w", encoding="utf-8") as json_file,
    ):
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        json_file.write("[\n")
        for row_index, row in enumerate(snapshot_cursor):
            row_data = dict(zip(columns, row))
            row_data["bid_levels"], row_data["ask_levels"] = levels_for_state(
                row_data["order_book_state_id"]
            )
            writer.writerow(row_data)
            if row_index:
                json_file.write(",\n")
            json.dump(row_data, json_file, ensure_ascii=False)
        json_file.write("\n]\n")


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
        export_snapshots(connection, output_directory)
    return len(TABLES) + 3


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
