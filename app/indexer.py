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


def build_index(txtdir, db_path, rebuild=False, progress=None):
    """Walk TXTDIR and load all lines into the FTS5 search_idx table.

    Returns the number of rows inserted. Idempotent per txtid: existing
    rows for a (txtid) are deleted before its new rows are inserted.
    `progress`, if given, is called as progress(i, n_files, path, rows_so_far)
    once per file.
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
        paths = sorted(glob.glob(pattern))
        n_files = len(paths)
        total = 0
        for i, path in enumerate(paths, 1):
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
            if progress is not None:
                progress(i, n_files, path, total)
        return total
    finally:
        conn.close()


def _parse_title_line(line):
    """Return (txtid, title, dynasty, author) or None.

    Accepts two formats:
      "TXTID<TAB>...<TAB>TITLE"
      "TXTID[ @flag ...] TITLE-DYNASTY-AUTHOR"   (Kanripo search-titles.txt)

    @-prefixed tokens between the TXTID and the trailing
    TITLE-DYNASTY-AUTHOR field are ignored.
    """
    line = line.rstrip("\n").rstrip("\r")
    if not line:
        return None
    if "\t" in line:
        parts = line.split("\t")
        if len(parts) < 2:
            return None
        return parts[0].strip(), parts[-1].strip(), "", ""
    tokens = [t for t in line.split() if not t.startswith("@")]
    if len(tokens) < 2:
        return None
    txtid = tokens[0]
    fields = tokens[-1].split("-")
    title = fields[0].strip() if len(fields) > 0 else ""
    dynasty = fields[1].strip() if len(fields) > 1 else ""
    author = fields[2].strip() if len(fields) > 2 else ""
    if not title:
        return None
    return txtid, title, dynasty, author


def _titles_files(mdbase):
    """Locate *titles.txt under MDBASE, with or without a system/ prefix."""
    candidates = sorted(set(
        glob.glob(os.path.join(mdbase, "system", "*titles.txt")) +
        glob.glob(os.path.join(mdbase, "*titles.txt"))
    ))
    return candidates


def _meta_json(mdbase):
    for p in (os.path.join(mdbase, "system", "meta.json"),
              os.path.join(mdbase, "meta.json")):
        if os.path.exists(p):
            return p
    return None


def load_metadata(mdbase, db_path):
    """Bulk-load titles + metadata from MDBASE.

    Walks `*titles.txt` under <MDBASE> or <MDBASE>/system. Each line is
    either tab-separated (TXTID ... TITLE) or space-separated Kanripo
    style (TXTID TITLE-DYNASTY-AUTHOR). Also reads an optional
    meta.json keyed by txtid8 into the metadata table.
    """
    conn = connect(db_path)
    n = 0
    try:
        for path in _titles_files(mdbase):
            title_rows = []
            meta_rows = []
            with open(path, encoding="utf-8") as fp:
                for line in fp:
                    parsed = _parse_title_line(line)
                    if not parsed:
                        continue
                    txtid, title, dynasty, author = parsed
                    title_rows.append((txtid, title))
                    raw = json.dumps(
                        {"TITLE": title, "DYNASTY": dynasty,
                         "AUTHOR": author, "COLLECTION": txtid[:4]},
                        ensure_ascii=False,
                    )
                    meta_rows.append((txtid, title, dynasty, txtid[:4], raw))
            if title_rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO titles(txtid, title)"
                    " VALUES (?, ?)",
                    title_rows,
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO metadata"
                    "(txtid, title, dynasty, collection, raw_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    meta_rows,
                )
                n += len(title_rows)

        meta_path = _meta_json(mdbase)
        if meta_path:
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


def build_taisho_index(source_path, db_path):
    """Load the Taisho page→file index from a mandoku-cbeta.el source.

    Only entries under `(subcoll "T")` are kept. The pagekey integer is
    the raw 7-digit page number found in the source (vol page-section
    line-offset) -- the same key the lookup in lib.gettaisho computes.
    Returns the number of rows written.
    """
    conn = connect(db_path)
    try:
        rflag = False
        vol = ""
        rows = []
        with open(source_path, encoding="utf-8") as fp:
            for line in fp:
                if 'subcoll "T"' in line:
                    rflag = True
                elif 'subcoll' in line:
                    rflag = False
                if not rflag:
                    continue
                if "vol" in line:
                    vol = "T" + line.split()[-1].replace(")", "")
                elif "page" in line:
                    tmp = line.replace(")", "").split()
                    try:
                        pagekey = int(tmp[-2])
                    except (ValueError, IndexError):
                        continue
                    filename = tmp[-1].replace('"', '')[:-4]
                    rows.append((vol, pagekey, filename))
        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO taisho_pages(vol, pagekey, filename)"
                " VALUES (?, ?, ?)",
                rows,
            )
        conn.commit()
        return len(rows)
    finally:
        conn.close()
