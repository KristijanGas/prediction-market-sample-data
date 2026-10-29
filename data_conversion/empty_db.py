"""Remove all database rows while preserving the SQLite schema."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = REPO_ROOT / "database" / "prediction_market.db"

TABLES = (
    "order_book_state",
    "crypto_price",
    "observation",
    "market_asset",
    "market_hour",
    "trading_date",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all rows from db"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"SQLite database path (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser.parse_args()


def empty_database(database_path: Path) -> int:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        for table in TABLES:
            connection.execute(f"DELETE FROM {table}")
        connection.execute("DELETE FROM sqlite_sequence")
        connection.commit()

        remaining_rows = sum(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES
        )
        if remaining_rows != 0:
            raise RuntimeError("Database cleanup did not remove all rows")
    return len(TABLES)


def main() -> int:
    args = parse_args()
    try:
        table_count = empty_database(args.database.resolve())
    except (OSError, sqlite3.Error, RuntimeError) as error:
        print(f"Error cleaning database: {error}")
        return 1
    print(f"Removed all rows from {table_count} tables; schema preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())