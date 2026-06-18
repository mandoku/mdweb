#    -*- coding: utf-8 -*-
"""SQLite FTS5 search-index connection helpers."""
import sqlite3
from flask import current_app, g


SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(
    content,
    location UNINDEXED,
    txtid    UNINDEXED,
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
"""


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
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
