#    -*- coding: utf-8 -*-
"""SQLite FTS5 search-index connection helpers."""
import os
import sqlite3
from flask import current_app, g


SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(
    content,
    location UNINDEXED,
    txtid    UNINDEXED,
    line_len UNINDEXED,
    tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS metadata (
    txtid      TEXT PRIMARY KEY,
    title      TEXT,
    dynasty    TEXT,
    collection TEXT,
    raw_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_meta_dynasty ON metadata(dynasty);

CREATE TABLE IF NOT EXISTS titles (
    txtid TEXT PRIMARY KEY,
    title TEXT
);
CREATE INDEX IF NOT EXISTS idx_titles_title ON titles(title);

CREATE TABLE IF NOT EXISTS taisho_pages (
    vol      TEXT NOT NULL,
    pagekey  INTEGER NOT NULL,
    filename TEXT NOT NULL,
    PRIMARY KEY(vol, pagekey)
);
CREATE INDEX IF NOT EXISTS idx_taisho_vol_pagekey
    ON taisho_pages(vol, pagekey);
"""


def connect(db_path):
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "PRAGMA journal_mode=WAL;"
        "PRAGMA synchronous=NORMAL;"
        "PRAGMA temp_store=MEMORY;"
        "PRAGMA cache_size=-65536;"  # 64 MB page cache
        "PRAGMA mmap_size=268435456;"  # 256 MB mmap
    )
    conn.executescript(SCHEMA)
    return conn


def get_db():
    if 'search_db' not in g:
        g.search_db = connect(current_app.config['INDEX_DB_PATH'])
    return g.search_db


def close_db(_exc=None):
    db = g.pop('search_db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
