"""股票爬蟲 — yfinance → 資料庫（支援 PostgreSQL / SQLite）"""

import yfinance as yf
import pandas as pd

from config import DB_CONFIG, DB_MODE, SQLITE_PATH


def get_conn():
    """取得資料庫連線（自動判斷 PostgreSQL 或 SQLite）"""
    if DB_MODE == "sqlite":
        import sqlite3
        return sqlite3.connect(str(SQLITE_PATH))
    else:
        import psycopg2
        return psycopg2.connect(**DB_CONFIG)


def ensure_table():
    """確保 stock_prices 資料表存在"""
    if DB_MODE == "sqlite":
        sql = """
        CREATE TABLE IF NOT EXISTS stock_prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT     NOT NULL,
            trade_date  TEXT     NOT NULL,
            open_price  REAL,
            high_price  REAL,
            low_price   REAL,
            close_price REAL,
            volume      INTEGER,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (symbol, trade_date)
        );
        """
    else:
        sql = """
        CREATE TABLE IF NOT EXISTS stock_prices (
            id          SERIAL PRIMARY KEY,
            symbol      VARCHAR(20)  NOT NULL,
            trade_date  DATE         NOT NULL,
            open_price  NUMERIC(12,2),
            high_price  NUMERIC(12,2),
            low_price   NUMERIC(12,2),
            close_price NUMERIC(12,2),
            volume      BIGINT,
            created_at  TIMESTAMP DEFAULT NOW(),
            UNIQUE (symbol, trade_date)
        );
        """

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
    print("✅ stock_prices 資料表已就緒")


def crawl_stock(symbol: str, start: str, end: str) -> int:
    """用 yfinance 爬取股票資料並批次寫入資料庫"""
    print(f"\n📡 爬取 {symbol} ({start} ~ {end}) ...")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end)

    if df.empty:
        print(f"⚠️  {symbol} 無資料")
        return 0

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)
    print(f"✅ 共取得 {len(df)} 筆資料")

    rows = [
        (
            symbol,
            idx.date().isoformat() if DB_MODE == "sqlite" else idx.date(),
            round(row.Open,  2),
            round(row.High,  2),
            round(row.Low,   2),
            round(row.Close, 2),
            int(row.Volume),
        )
        for idx, row in df.iterrows()
    ]

    ensure_table()

    conn = get_conn()
    try:
        cur = conn.cursor()
        if DB_MODE == "sqlite":
            cur.executemany(
                """INSERT OR REPLACE INTO stock_prices
                   (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
        else:
            from psycopg2.extras import execute_values
            sql = """
                INSERT INTO stock_prices
                    (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
                VALUES %s
                ON CONFLICT (symbol, trade_date) DO UPDATE SET
                    open_price  = EXCLUDED.open_price,
                    high_price  = EXCLUDED.high_price,
                    low_price   = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume      = EXCLUDED.volume;
            """
            execute_values(cur, sql, rows)
        conn.commit()
    finally:
        conn.close()

    db_name = "SQLite" if DB_MODE == "sqlite" else "PostgreSQL"
    print(f"💾 {symbol}：已寫入 {len(rows)} 筆至 {db_name}")
    return len(rows)


