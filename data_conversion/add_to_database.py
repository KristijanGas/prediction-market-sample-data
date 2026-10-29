"""Import compressed prediction-market datasets into the repository database."""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "database_create.sql"
DEFAULT_DATABASE_PATH = REPO_ROOT / "database" / "prediction_market.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import .gz or .json dataset files into the SQLite database."
    )
    parser.add_argument("folder", type=Path, help="Folder containing dataset files")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"SQLite database path (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser.parse_args()


def load_dataset(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def parse_iso_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def format_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def timestamp_from_milliseconds(value: Any) -> datetime:
    return datetime.fromtimestamp(int(float(value)) / 1000, tz=timezone.utc)


def decimal_text(value: Any) -> str:
    number = Decimal(str(value))
    if number < 0:
        raise ValueError(f"Expected a non-negative number, got {value!r}")
    return format(number, "f")


def get_market_metadata(data: dict[str, Any], key: str) -> dict[str, Any]:
    values = data.get(key)
    if not isinstance(values, list) or not values or not isinstance(values[0], dict):
        raise ValueError(f"Dataset is missing {key}")
    return values[0]


def get_market_assets(
    metadata: dict[str, Any],
) -> list[tuple[str, str | None]]:
    market = metadata.get("markets", [{}])[0]
    outcomes = json.loads(market.get("outcomes", "[]"))
    token_ids = json.loads(market.get("clobTokenIds", "[]"))
    if not isinstance(outcomes, list) or not isinstance(token_ids, list):
        raise ValueError("Market outcomes and token IDs must be JSON arrays")
    if len(outcomes) != len(token_ids) or not token_ids:
        raise ValueError("Market outcomes and token IDs do not match")
    return [(str(token_id), str(outcome)) for token_id, outcome in zip(token_ids, outcomes)]


def get_hour_bounds(metadata_start: dict[str, Any], metadata_end: dict[str, Any]) -> tuple[datetime, datetime]:
    end_value = metadata_end.get("endDate") or metadata_start.get("endDate")
    if not isinstance(end_value, str):
        raise ValueError("Dataset is missing an hourly end date")
    hour_end = parse_iso_timestamp(end_value)

    start_value = metadata_start.get("eventStartTime")
    if isinstance(start_value, str):
        hour_start = parse_iso_timestamp(start_value)
    else:
        hour_start = hour_end - timedelta(hours=1)
    if hour_end <= hour_start:
        raise ValueError("Dataset hourly end date must be after its start date")
    return hour_start, hour_end


def normalize_book_snapshot(snapshot: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, list):
        raise ValueError("Order-book snapshot must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in snapshot:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[1], dict):
            raise ValueError("Invalid order-book asset entry")
        token_id = str(item[0])
        book = item[1]
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if not isinstance(bids, list) or not isinstance(asks, list):
            raise ValueError(f"Invalid order book for asset {token_id}")
        result[token_id] = {"bids": bids, "asks": asks}
    return result


def insert_dataset(connection: sqlite3.Connection, path: Path) -> tuple[int, int, bool]:
    data = load_dataset(path)
    metadata_start = get_market_metadata(data, "metadata_start")
    metadata_end = get_market_metadata(data, "metadata_end")
    hour_start, hour_end = get_hour_bounds(metadata_start, metadata_end)
    assets = get_market_assets(metadata_start)

    calendar_date = hour_start.date().isoformat()
    hour_start_text = format_timestamp(hour_start)
    if connection.execute(
        """
        SELECT 1
        FROM market_hour AS hour
        JOIN trading_date AS date ON date.trading_date_id = hour.trading_date_id
        WHERE date.calendar_date = ? AND hour.hour_start = ?
        """,
        (calendar_date, hour_start_text),
    ).fetchone():
        return 0, 0, True

    metadata = json.dumps(
        {"metadata_start": data["metadata_start"], "metadata_end": data["metadata_end"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    connection.execute(
        "INSERT OR IGNORE INTO trading_date (calendar_date) VALUES (?)",
        (calendar_date,),
    )
    trading_date_id = connection.execute(
        "SELECT trading_date_id FROM trading_date WHERE calendar_date = ?",
        (calendar_date,),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT OR IGNORE INTO market_hour
            (trading_date_id, hour_start, hour_end, metadata)
        VALUES (?, ?, ?, ?)
        """,
        (trading_date_id, hour_start_text, format_timestamp(hour_end), metadata),
    )
    market_hour_id = connection.execute(
        """
        SELECT market_hour_id
        FROM market_hour
        WHERE trading_date_id = ? AND hour_start = ?
        """,
        (trading_date_id, format_timestamp(hour_start)),
    ).fetchone()[0]

    asset_ids: dict[str, int] = {}
    for token_id, outcome in assets:
        connection.execute(
            """
            INSERT OR IGNORE INTO market_asset (market_hour_id, token_id, outcome)
            VALUES (?, ?, ?)
            """,
            (market_hour_id, token_id, outcome),
        )
        asset_ids[token_id] = connection.execute(
            """
            SELECT asset_id FROM market_asset
            WHERE market_hour_id = ? AND token_id = ?
            """,
            (market_hour_id, token_id),
        ).fetchone()[0]

    prices = [
        item for item in data.get("all_prices", [])
        if isinstance(item, dict) and item.get("timestamp") is not None
    ]
    books = [
        (timestamp_from_milliseconds(item[0][1]["timestamp"]), normalize_book_snapshot(item))
        for item in data.get("all_clobs", [])
        if isinstance(item, list)
        and item
        and isinstance(item[0], list)
        and len(item[0]) == 2
        and isinstance(item[0][1], dict)
        and item[0][1].get("timestamp") is not None
    ]
    books.sort(key=lambda item: item[0])
    if not prices or not books:
        raise ValueError("Dataset must contain both prices and order-book snapshots")

    inserted_observations = 0
    inserted_order_book_states = 0
    book_index = 0
    current_book = books[0][1]
    for price in prices:
        observed_at = timestamp_from_milliseconds(float(price["timestamp"]) * 1000)
        while book_index + 1 < len(books) and books[book_index + 1][0] <= observed_at:
            book_index += 1
            current_book = books[book_index][1]

        observed_at_text = format_timestamp(observed_at)
        connection.execute(
            """
            INSERT OR IGNORE INTO observation (market_hour_id, observed_at)
            VALUES (?, ?)
            """,
            (market_hour_id, observed_at_text),
        )
        observation_id = connection.execute(
            """
            SELECT observation_id FROM observation
            WHERE market_hour_id = ? AND observed_at = ?
            """,
            (market_hour_id, observed_at_text),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT OR IGNORE INTO crypto_price
                (observation_id, symbol, price)
            VALUES (?, ?, ?)
            """,
            (observation_id, str(price["symbol"]), decimal_text(price["price"])),
        )
        inserted_observations += 1

        for token_id, asset_id in asset_ids.items():
            book = current_book.get(token_id)
            if book is None:
                raise ValueError(f"Order book is missing asset {token_id}")
            bids = [decimal_text(level["price"]) for level in book["bids"]]
            asks = [decimal_text(level["price"]) for level in book["asks"]]
            best_bid = max((Decimal(price_value) for price_value in bids), default=None)
            best_ask = min((Decimal(price_value) for price_value in asks), default=None)
            connection.execute(
                """
                INSERT OR IGNORE INTO order_book_state
                    (observation_id, asset_id, best_bid, best_ask)
                VALUES (?, ?, ?, ?)
                """,
                (
                    observation_id,
                    asset_id,
                    format(best_bid, "f") if best_bid is not None else None,
                    format(best_ask, "f") if best_ask is not None else None,
                ),
            )
            inserted_order_book_states += 1
    return inserted_observations, inserted_order_book_states, False


def main() -> int:
    args = parse_args()
    folder = args.folder.resolve()
    database_path = args.database.resolve()
    if not folder.is_dir():
        print(f"Error: dataset folder does not exist: {folder}", file=sys.stderr)
        return 2

    files = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix in {".gz", ".json"}
    )
    if not files:
        print(f"Error: no .gz or .json dataset files found in {folder}", file=sys.stderr)
        return 2

    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            total_observations = 0
            total_order_book_states = 0
            for path in files:
                observations, order_book_states, skipped = insert_dataset(connection, path)
                if skipped:
                    print(f"Skipped {path.name}: already imported")
                    continue
                total_observations += observations
                total_order_book_states += order_book_states
                print(
                    f"Imported {path.name}: {observations} observations, "
                    f"{order_book_states} order-book states"
                )
    except (OSError, sqlite3.Error, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Error importing datasets: {error}", file=sys.stderr)
        return 1

    print(
        f"Imported {len(files)} file(s): "
        f"{total_observations} observations, "
        f"{total_order_book_states} order-book states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
