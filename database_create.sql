-- SQLite schema
-- Database file: database/prediction_market.db
-- trading_date -> market_hour -> observation
-- observation -> crypto_price + order_book_state

PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS trading_date (
    trading_date_id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_hour (
    market_hour_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_date_id INTEGER NOT NULL
        REFERENCES trading_date(trading_date_id)
        ON DELETE CASCADE,

    -- ISO-8601 timestamps in UTC.
    hour_start TEXT NOT NULL,
    hour_end TEXT NOT NULL,

    -- Polymarket/event metadata for this hour.
    metadata TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(metadata)),

    UNIQUE (trading_date_id, hour_start),
    CHECK (hour_end > hour_start)
);

CREATE TABLE IF NOT EXISTS market_asset (
    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_hour_id INTEGER NOT NULL
        REFERENCES market_hour(market_hour_id)
        ON DELETE CASCADE,

    -- Polymarket CLOB token ID.
    token_id TEXT NOT NULL,

    -- For example: Up or Down.
    outcome TEXT,

    UNIQUE (market_hour_id, token_id)
);

CREATE TABLE IF NOT EXISTS observation (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_hour_id INTEGER NOT NULL
        REFERENCES market_hour(market_hour_id)
        ON DELETE CASCADE,

    -- ISO-8601 timestamp in UTC.
    observed_at TEXT NOT NULL,

    UNIQUE (market_hour_id, observed_at)
);

CREATE TABLE IF NOT EXISTS crypto_price (
    observation_id INTEGER PRIMARY KEY
        REFERENCES observation(observation_id)
        ON DELETE CASCADE,

    -- BTCUSDT
    symbol TEXT NOT NULL,

    price NUMERIC NOT NULL,
    source TEXT NOT NULL DEFAULT 'binance',

    CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS order_book_state (
    order_book_state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL
        REFERENCES observation(observation_id)
        ON DELETE CASCADE,

    asset_id INTEGER NOT NULL
        REFERENCES market_asset(asset_id)
        ON DELETE CASCADE,

    best_bid NUMERIC,
    best_ask NUMERIC,

    UNIQUE (observation_id, asset_id),

    CHECK (best_bid IS NULL OR best_bid >= 0),
    CHECK (best_ask IS NULL OR best_ask >= 0),
    CHECK (
        best_bid IS NULL
        OR best_ask IS NULL
        OR best_ask >= best_bid
    )
);

CREATE INDEX IF NOT EXISTS idx_market_hour_date
    ON market_hour (trading_date_id, hour_start);

CREATE INDEX IF NOT EXISTS idx_observation_hour_time
    ON observation (market_hour_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_order_book_state_observation
    ON order_book_state (observation_id);

COMMIT;
