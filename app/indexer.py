#    -*- coding: utf-8 -*-
"""SQLite FTS5 trigram indexer for Mandoku text files.

Source layout: <TXTDIR>/<TXTID[0:4]>/<TXTID[0:8]>/<TXTID>_<JUAN>.txt
Page breaks in text are marked by:  <pb:VOL_JUAN_PFX-PAGE>
Each non-empty content line is emitted as one FTS row with location
"TXTID_JUAN:PAGE:LINE".
"""
import glob
import json
import os
import re

from .search_db import connect

PB_RE = re.compile(r"<pb:([^_]+)_([^_]+)_([^-]+)-([^>]+)>")
GAIJI_RE = re.compile(r"(&[^;]+;)")


def _emit_rows(path, txtid, juan):
    """Yield (content, location, txtid8) for each non-empty content line."""
    page = "0000"
    line_no = 0
    txtid8 = txtid[:8]
    with open(path, encoding="utf-8") as fp:
        for raw in fp:
            line = raw.rstrip("\n")
            m = PB_RE.search(line)
            if m:
                page = m.group(4)
                line = PB_RE.sub("", line)
            line = line.replace("¶", "").strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith(":"):
                continue
            line_no += 1
            content = GAIJI_RE.sub("⬤", line)
            location = f"{txtid}_{juan}:{page}:{line_no:04d}"
            yield (content, location, txtid8)


def _parse_filename(path):
    """Return (txtid, juan) from a path like .../ZB1a0001_001.txt."""
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    txtid, _, juan = stem.rpartition("_")
    return txtid, juan


def build_index(txtdir, db_path, rebuild=False):
    """Walk TXTDIR and load all lines into the FTS5 search_idx table.

    Returns the number of rows inserted. Idempotent per txtid: existing
    rows for a (txtid) are deleted before its new rows are inserted.
    """
    conn = connect(db_path)
    try:
        if rebuild:
            conn.execute("DROP TABLE IF EXISTS search_idx")
            conn.executescript(
                "CREATE VIRTUAL TABLE search_idx USING fts5("
                " content, location UNINDEXED, txtid UNINDEXED,"
                " tokenize='trigram');"
            )

        pattern = os.path.join(txtdir, "*", "*", "*_*.txt")
        total = 0
        for path in sorted(glob.glob(pattern)):
            txtid, juan = _parse_filename(path)
            if not txtid or not juan:
                continue
            conn.execute(
                "DELETE FROM search_idx WHERE location LIKE ?",
                (f"{txtid}_{juan}:%",),
            )
            rows = list(_emit_rows(path, txtid, juan))
            if rows:
                conn.executemany(
                    "INSERT INTO search_idx(content, location, txtid)"
                    " VALUES (?, ?, ?)",
                    rows,
                )
                total += len(rows)
            conn.commit()
        return total
    finally:
        conn.close()


def load_metadata(mdbase, db_path):
    """Bulk-load titles + metadata from <MDBASE>/system/*titles.txt.

    Expected line format (tab-separated): TXTID \t ... \t TITLE
    Optional sibling JSON metadata at <MDBASE>/system/meta.json keyed by
    txtid8; values become the metadata row.
    """
    conn = connect(db_path)
    n = 0
    try:
        for path in sorted(glob.glob(os.path.join(mdbase, "system", "*titles.txt"))):
            with open(path, encoding="utf-8") as fp:
                rows = []
                for line in fp:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 2:
                        continue
                    txtid = parts[0].strip()
                    title = parts[-1].strip()
                    if txtid and title:
                        rows.append((txtid, title))
                if rows:
                    conn.executemany(
                        "INSERT OR REPLACE INTO titles(txtid, title)"
                        " VALUES (?, ?)",
                        rows,
                    )
                    n += len(rows)

        meta_path = os.path.join(mdbase, "system", "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as fp:
                meta = json.load(fp)
            rows = []
            for txtid, fields in meta.items():
                rows.append((
                    txtid,
                    fields.get("TITLE", ""),
                    fields.get("DYNASTY", ""),
                    fields.get("COLLECTION", ""),
                    json.dumps(fields, ensure_ascii=False),
                ))
            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO metadata"
                    "(txtid, title, dynasty, collection, raw_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
                n += len(rows)
        conn.commit()
        return n
    finally:
        conn.close()
