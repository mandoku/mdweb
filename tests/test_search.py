#    -*- coding: utf-8 -*-
"""End-to-end test for the SQLite FTS5 trigram search subsystem.

Stubs out the Flask `g`/`current_app` plumbing so the search code can be
exercised without booting the full app.
"""
import os
import sys
import tempfile
import types
import unittest
import importlib.util


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _load_isolated():
    """Load app.search_db and app.lib without triggering app/__init__.py."""
    sys.modules.setdefault('flask', types.SimpleNamespace(current_app=None, g=None))

    if 'app' not in sys.modules:
        sys.modules['app'] = types.ModuleType('app')

    spec1 = importlib.util.spec_from_file_location(
        'app.search_db', os.path.join(REPO_ROOT, 'app', 'search_db.py')
    )
    search_db = importlib.util.module_from_spec(spec1)
    sys.modules['app.search_db'] = search_db
    spec1.loader.exec_module(search_db)

    spec2 = importlib.util.spec_from_file_location(
        'app.indexer', os.path.join(REPO_ROOT, 'app', 'indexer.py')
    )
    indexer = importlib.util.module_from_spec(spec2)
    sys.modules['app.indexer'] = indexer
    spec2.loader.exec_module(indexer)

    spec3 = importlib.util.spec_from_file_location(
        'app.lib', os.path.join(REPO_ROOT, 'app', 'lib.py')
    )
    lib = importlib.util.module_from_spec(spec3)
    sys.modules['app.lib'] = lib
    spec3.loader.exec_module(lib)

    return search_db, indexer, lib


class TestFTS5SearchPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search_db, cls.indexer, cls.lib = _load_isolated()
        cls.tmpdir = tempfile.mkdtemp(prefix="mdweb-test-")
        cls.txtdir = os.path.join(cls.tmpdir, "text")
        os.makedirs(os.path.join(cls.txtdir, "AB12", "AB120001"))
        os.makedirs(os.path.join(cls.txtdir, "XY99", "XY990001"))
        with open(os.path.join(cls.txtdir, "AB12", "AB120001",
                               "AB120001_001.txt"), "w", encoding="utf-8") as f:
            f.write(
                "#+TITLE: 道德經\n"
                "<pb:AB120001_001_x-001>\n"
                "道可道非常道\n"
                "名可名非常名\n"
                "<pb:AB120001_001_x-002>\n"
                "無名天地之始\n"
                "有名萬物之母\n"
            )
        with open(os.path.join(cls.txtdir, "XY99", "XY990001",
                               "XY990001_001.txt"), "w", encoding="utf-8") as f:
            f.write(
                "<pb:XY990001_001_x-001>\n"
                "道路、不通。\n"
                "ABC 123 ＡＢＣ\n"
                "山,水/林。\n"
            )
        cls.krpx_dir = os.path.join(cls.tmpdir, "krpx")
        cls.db_path = os.path.join(cls.tmpdir, "kanripo.krpx")
        cls.indexer.build_all_text_indexes(
            cls.txtdir, cls.krpx_dir, rebuild=True
        )
        cls.indexer.merge_indexes(cls.krpx_dir, cls.db_path, rebuild=True)

        # Patch get_db to return a real connection for lib.* to use.
        cls.conn = cls.search_db.connect(cls.db_path)
        cls.search_db.get_db = lambda: cls.conn
        cls.lib.get_db = lambda: cls.conn

    def test_indexer_populates_rows(self):
        n = self.conn.execute("SELECT count(*) FROM search_idx").fetchone()[0]
        self.assertGreaterEqual(n, 5)

    def test_fts5_trigram_match(self):
        rows, total = self.lib.doftsearch("道可道", limit=10)
        self.assertEqual(total, 1)
        content, location, txtid8 = rows[0]
        self.assertIn("道可道", content)
        self.assertRegex(location, r"^[A-Z0-9]{8}_\d+:[^:]+:\d+$")
        self.assertEqual(txtid8, "AB120001")

    def test_like_fallback_for_short_query(self):
        rows, total = self.lib.doftsearch("道", limit=10)
        self.assertGreaterEqual(total, 2)
        for content, location, _ in rows:
            self.assertIn("道", content)
            self.assertRegex(location, r"^[A-Z0-9]{8}_\d+:[^:]+:\d+$")

    def test_collection_prefix_filter(self):
        rows, total = self.lib.doftsearch("道", filters=["AB12"], limit=10)
        self.assertGreater(total, 0)
        for _, _, txtid8 in rows:
            self.assertTrue(txtid8.startswith("AB12"))

        _, no_total = self.lib.doftsearch("道", filters=["ZZ99"], limit=10)
        self.assertEqual(no_total, 0)

    def test_dynasty_filter_uses_metadata(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata(txtid, title, dynasty, collection, raw_json)"
            " VALUES (?, ?, ?, ?, ?)",
            ("AB120001", "道德經", "周", "AB12", "{}"),
        )
        self.conn.commit()
        rows, total = self.lib.doftsearch("道", dynasty="周", limit=10)
        self.assertGreater(total, 0)
        for _, _, txtid8 in rows:
            self.assertEqual(txtid8, "AB120001")

        _, none_total = self.lib.doftsearch("道", dynasty="唐", limit=10)
        self.assertEqual(none_total, 0)

    def test_location_parses_to_expected_shape(self):
        rows, _ = self.lib.doftsearch("道可道", limit=1)
        _, location, _ = rows[0]
        txtid, _, rest = location.partition("_")
        juan, page, line = rest.split(":")
        self.assertEqual(len(txtid), 8)
        self.assertTrue(juan and page and line)

    def test_get_meta_returns_dict(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata(txtid, title, dynasty, collection, raw_json)"
            " VALUES (?, ?, ?, ?, ?)",
            ("AB120001", "道德經", "周", "AB12", '{"AUTHOR": "老子"}'),
        )
        self.conn.commit()
        meta = self.lib.get_meta("AB120001")
        self.assertEqual(meta["ID"], "AB120001")
        self.assertEqual(meta["TITLE"], "道德經")
        self.assertEqual(meta["DYNASTY"], "周")
        self.assertEqual(meta["AUTHOR"], "老子")

    def test_strips_punctuation_ascii_and_space(self):
        # "道路、不通。" → cleaned content "道路不通", so "路不" matches
        # despite the comma between them in the source.
        _, total = self.lib.doftsearch("路不", limit=10)
        self.assertEqual(total, 1)
        # "ABC 123 ＡＢＣ" (pure ASCII/fullwidth) drops to empty and is not
        # emitted; "山,水/林。" cleans to "山水林".
        rows, total = self.lib.doftsearch("山水", limit=10)
        self.assertEqual(total, 1)
        content, _, _ = rows[0]
        self.assertNotIn(",", content)
        self.assertNotIn("/", content)
        self.assertNotIn("。", content)

    def test_cross_line_phrase_match(self):
        # "常道名可" = last 2 chars of "道可道非常道" + first 2 of "名可名非常名".
        # Pre-lookahead indexing missed it; now it matches the row anchored
        # on the first line and is *not* duplicated on the second line.
        rows, total = self.lib.doftsearch("常道名可", limit=10)
        self.assertEqual(total, 1)
        content, location, txtid8 = rows[0]
        self.assertIn("常道名可", content)
        self.assertEqual(txtid8, "AB120001")
        line = location.rsplit(":", 1)[-1]
        self.assertEqual(int(line), 1)

    def test_lookahead_does_not_duplicate_in_line_match(self):
        # "名可名" is fully within line 2; lookahead bleeds it into line 1's
        # indexed content, but the instr-vs-line_len filter must drop that
        # spurious row so the hit count stays at 1.
        _, total = self.lib.doftsearch("名可名", limit=10)
        self.assertEqual(total, 1)

    def test_per_text_krpx_files_written(self):
        import sqlite3
        for txtid in ("AB120001", "XY990001"):
            path = os.path.join(self.krpx_dir, txtid[:4], txtid[:8],
                                txtid + ".krpx")
            self.assertTrue(os.path.exists(path), path)
            conn = sqlite3.connect(path)
            try:
                n = conn.execute("SELECT count(*) FROM search_idx").fetchone()[0]
            finally:
                conn.close()
            self.assertGreater(n, 0)

    def test_merge_is_idempotent_with_rebuild(self):
        before = self.conn.execute(
            "SELECT count(*) FROM search_idx"
        ).fetchone()[0]
        self.indexer.merge_indexes(self.krpx_dir, self.db_path, rebuild=True)
        # Re-open via the cached connection's same path.
        after = self.conn.execute(
            "SELECT count(*) FROM search_idx"
        ).fetchone()[0]
        self.assertEqual(before, after)

    def test_facets_by_id(self):
        facets = self.lib.get_facets("道", tpe="ID", id_len=4, top_n=10)
        keys = [k for (k, _meta, _n, _t) in facets]
        self.assertIn("AB12", keys)
        self.assertIn("XY99", keys)


if __name__ == "__main__":
    unittest.main()
