#    -*- coding: utf-8 -*-
"""SQLite FTS5 trigram indexer for Mandoku text files.

Source layout: <TXTDIR>/<TXTID[0:4]>/<TXTID[0:8]>/<TXTID>_<JUAN>.txt
Page breaks in text are marked by:  <pb:VOL_JUAN_PFX-PAGE>

Indexing is a two-step process:

  1. Per-text build  →  <KRPX_DIR>/<TXTID[0:4]>/<TXTID[0:8]>/<TXTID>.krpx
     Each .krpx is a standalone SQLite database carrying only the
     FTS5 `search_idx` table for one text (all its juan).

  2. Merge           →  <INDEX_DB_PATH>  (typically kanripo.krpx)
     All per-text .krpx files are merged into the corpus database
     used by the running app.

To make queries find phrases that straddle a source line break, each
emitted row's `content` is the original line followed by up to
LOOKAHEAD_CHARS characters drawn from the following emitted lines.
The `line_len` column records the length of the original line so that
queries can anchor matches to the row where the match *starts* (see
app/lib.py: `_ft_search_clause`).
"""
import glob
import json
import os
import re
import sqlite3

from .search_db import connect

PB_RE = re.compile(r"<pb:([^_]+)_([^_]+)_([^-]+)-([^>]+)>")
GAIJI_RE = re.compile(r"(&[^;]+;)")

# Stripped from indexed content so searches ignore punctuation, ASCII
# (annotations, IDs, markup) and any whitespace. The gaiji marker U+2B24
# survives because it isn't in any of these ranges.
#   \x00-\x7F             all ASCII
#   \s                    whitespace (incl. U+3000 via the next range)
#   \u3000-\u303F         CJK symbols and punctuation (、。「」『』 etc.)
#   \uFF00-\uFFEF         halfwidth and fullwidth forms (ASCII + punct)
DROP_RE = re.compile(r"[\x00-\x7F\s\u3000-\u303F\uFF00-\uFFEF]")

LOOKAHEAD_CHARS = 32

KRPX_EXT = ".krpx"


def _emit_rows(path, txtid, juan, lookahead=LOOKAHEAD_CHARS):
    """Yield (content, location, txtid8, line_len) per non-empty content line.

    `content` is the original line concatenated with up to `lookahead`
    characters drawn from subsequent emitted lines, so that a query
    phrase straddling a line break is still indexed on the row where
    the match starts. `line_len` is len(original line).
    """
    txtid8 = txtid[:8]
    page = "0000"
    line_no = 0
    emitted = []  # (content, location)
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
            content = DROP_RE.sub("", content)
            if not content:
                continue
            location = f"{txtid}_{juan}:{page}:{line_no:04d}"
            emitted.append((content, location))

    for i, (content, location) in enumerate(emitted):
        remaining = lookahead
        extra = []
        for j in range(i + 1, len(emitted)):
            if remaining <= 0:
                break
            nxt = emitted[j][0]
            take = nxt[:remaining]
            extra.append(take)
            remaining -= len(take)
        full = content + "".join(extra)
        yield (full, location, txtid8, len(content))


def _parse_filename(path):
    """Return (txtid, juan) from a path like .../ZB1a0001_001.txt."""
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    txtid, _, juan = stem.rpartition("_")
    return txtid, juan


_FTS_CREATE = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5("
    " content, location UNINDEXED, txtid UNINDEXED, line_len UNINDEXED,"
    " tokenize='trigram');"
)


def _open_krpx(path):
    """Open or create a per-text .krpx file (SQLite + FTS5 trigram only)."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "PRAGMA journal_mode=WAL;"
        "PRAGMA synchronous=NORMAL;"
        "PRAGMA temp_store=MEMORY;"
        + _FTS_CREATE
    )
    return conn


def _krpx_path(krpx_dir, txtid):
    return os.path.join(krpx_dir, txtid[:4], txtid[:8], txtid + KRPX_EXT)


def _juan_paths(txtdir, txtid):
    pattern = os.path.join(txtdir, txtid[:4], txtid[:8], f"{txtid}_*.txt")
    return sorted(glob.glob(pattern))


def _list_txtids(txtdir):
    """Discover all txtids under TXTDIR by scanning juan files."""
    pattern = os.path.join(txtdir, "*", "*", "*_*.txt")
    txtids = set()
    for path in glob.glob(pattern):
        txtid, juan = _parse_filename(path)
        if txtid and juan:
            txtids.add(txtid)
    return sorted(txtids)


def build_text_index(txtdir, krpx_dir, txtid, rebuild=False):
    """Write a single per-text .krpx for `txtid`. Returns rows inserted.

    With `rebuild=True` the existing .krpx is removed first; otherwise the
    operation is idempotent per (txtid, juan): rows for each juan being
    re-indexed are deleted before its new rows are inserted.
    """
    paths = _juan_paths(txtdir, txtid)
    if not paths:
        return 0
    krpx_path = _krpx_path(krpx_dir, txtid)
    if rebuild and os.path.exists(krpx_path):
        os.remove(krpx_path)
    conn = _open_krpx(krpx_path)
    total = 0
    try:
        for path in paths:
            _, juan = _parse_filename(path)
            if not juan:
                continue
            conn.execute(
                "DELETE FROM search_idx WHERE location LIKE ?",
                (f"{txtid}_{juan}:%",),
            )
            rows = list(_emit_rows(path, txtid, juan))
            if rows:
                conn.executemany(
                    "INSERT INTO search_idx(content, location, txtid, line_len)"
                    " VALUES (?, ?, ?, ?)",
                    rows,
                )
                total += len(rows)
        conn.commit()
    finally:
        conn.close()
    return total


def build_all_text_indexes(txtdir, krpx_dir, rebuild=False, progress=None):
    """Build a .krpx for every txtid found under TXTDIR.

    `progress`, if given, is called as progress(i, n_texts, txtid, rows_so_far)
    once per text.
    """
    txtids = _list_txtids(txtdir)
    n = len(txtids)
    total = 0
    for i, txtid in enumerate(txtids, 1):
        rows = build_text_index(txtdir, krpx_dir, txtid, rebuild=rebuild)
        total += rows
        if progress is not None:
            progress(i, n, txtid, total)
    return total


def merge_indexes(krpx_dir, corpus_path, rebuild=False, progress=None):
    """Merge all per-text .krpx files under KRPX_DIR into the corpus DB.

    With `rebuild=True` the corpus `search_idx` is dropped and recreated
    before the merge. Otherwise, existing rows for each merged text
    (matched by `txtid` = TXTID[:8]) are deleted first so the merge stays
    idempotent on repeated runs.
    """
    if os.path.abspath(corpus_path).startswith(os.path.abspath(krpx_dir) + os.sep):
        raise ValueError(
            "Corpus path must not live inside KRPX_DIR (would be re-merged)."
        )
    conn = connect(corpus_path)
    try:
        if rebuild:
            conn.execute("DROP TABLE IF EXISTS search_idx")
            conn.executescript(_FTS_CREATE)
        else:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(search_idx)"
            ).fetchall()}
            if cols and "line_len" not in cols:
                raise RuntimeError(
                    f"{corpus_path}: search_idx is missing the 'line_len' "
                    "column (schema predates commit 088abc4). "
                    "Re-run with --rebuild to recreate the corpus index."
                )

        pattern = os.path.join(krpx_dir, "*", "*", "*" + KRPX_EXT)
        paths = sorted(glob.glob(pattern))
        n_files = len(paths)
        total = 0
        for i, path in enumerate(paths, 1):
            base = os.path.basename(path)
            txtid, _ = os.path.splitext(base)
            txtid8 = txtid[:8]
            if not rebuild:
                conn.execute(
                    "DELETE FROM search_idx WHERE txtid = ?",
                    (txtid8,),
                )
            conn.commit()
            conn.execute("ATTACH DATABASE ? AS krpx", (path,))
            cur = conn.execute("SELECT COUNT(*) FROM krpx.search_idx")
            added = cur.fetchone()[0]
            cur.close()
            # executescript finalizes each statement, so DETACH won't see the INSERT still holding `krpx`.
            conn.executescript(
                "INSERT INTO main.search_idx"
                "(content, location, txtid, line_len)"
                "  SELECT content, location, txtid, line_len"
                "    FROM krpx.search_idx;"
                "DETACH DATABASE krpx;"
            )
            total += added
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
