#    -*- coding: utf-8 -*-
## this is lifted from flask_sqlalchemy,
## maybe overkill...
from flask import current_app, g, session
from math import ceil
import re
from collections import defaultdict
from difflib import SequenceMatcher
from .search_db import get_db  # re-exported for view layer
## dictionary stuff.  really should wrap this in an object?!
md_re = re.compile(r"<[^>]*>|[　-㄀＀-￯\n¶]+|\t[^\n]+\n|\$[^;]+;")
gaiji = re.compile(r"&([^;]+);")
imgbase = "<img height='20' width='20' alt='{gaiji}' title='{gaiji}' src='https://raw.githubusercontent.com/kanripo/KR-Gaiji/master/images/{gaiji}.png'/>"

brtab = defaultdict(lambda : u"【使用者版】", {
u'DCS' : u'【東禪寺】',
u'GOZAN' : u'【日本五山版】',
u'CK-KZ-jye' : u'【道藏輯要電子版】',
u'ZTDZ' : u'【正統道藏・三家本】', 
u'T@DUN' : u'【大→敦】', 
u'T@XI' : u'【大→西】', 
u'WLG' : u'【四庫全書・文瀾閣】', 
u'T@LIYI' : u'【大→麗乙】', 
u'T@LIUBUBEN' : u'【大→流布本】', 
u'T@HE' : u'【大→和】', 
u'K' : u'【麗】', 
u'T@DUNBING' : u'【大→敦丙】', 
u'T@ZHI' : u'【大→知】', 
u'L' : u'【乾隆大藏經】', 
u'P' : u'【永樂北藏】', 
u'T' : u'【大】', 
u'X' : u'【卍續】', 
u'T@SEN' : u'【大→森】', 
u'T@DE' : u'【大→德】', 
u'T@MINGYI' : u'【大→明異】', 
u'YP-C' : u'【原版道藏輯要】', 
u'T@B' : u'【大→Ｂ】', 
u'T@A' : u'【大→Ａ】', 
u'T@DUNYI' : u'【大→敦乙】', 
u'T@NAN' : u'【大→南】', 
u'T@JIU' : u'【大→久】', 
u'T@JIN' : u'【大→金】', 
u'SBCK' : u'【四部叢刊】', 
u'SBCK-zw' : u'【四部叢刊-別】', 
u'T@SHENGYI' : u'【大→聖乙】', 
u'T@JIA' : u'【大→甲】', 
u'TKD' : u'【高麗藏・東國影印版】', 
u'TK' : u'【高麗藏・東國影印版】', 
u'T@RIGUANG' : u'【大→日光】', 
u'T@BO' : u'【大→博】', 
u'T@WAN' : u'【大→万】', 
u'T@JI' : u'【大→己】', 
u'QISHA' : u'【磧砂】', 
u'T@YI' : u'【大→乙】', 
u'C' : u'【中華大藏經】', 
u'G' : u'【佛教大藏經】', 
u'T@SHENGBING' : u'【大→聖丙】', 
u'T@DING' : u'【大→丁】', 
u'S' : u'【宋藏遺珍】', 
u'W' : u'【藏外佛經】', 
u'T@LIUTONGBEN' : u'【大→流通本】', 
u'T@GONG' : u'【大→宮】', 
u'T@SONG' : u'【大→宋】', 
u'T@DONG' : u'【大→東】', 
u'T@ZHONG' : u'【大→中】', 
u'T@NANZANG' : u'【大→南藏】', 
u'CK-KZ' : u'【重刊道藏輯要】', 
u'ZHWIKI' : u'【維基文庫】', 
u'T@UNKNOWN' : u'【大→unknown】', 
u'WYG' : u'【四庫全書・文淵閣】', 
u'T@GONGYI' : u'【大→宮乙】', 
u'Yan' : u'【柳田版】', 
u'HFL' : u'【正統道藏・涵芬樓版】', 
u'T@JIAXING' : u'【大→嘉興】', 
u'T@LI' : u'【大→麗】', 
u'T@BING' : u'【大→丙】', 
u'T@XUZANG' : u'【大→卍續】', 
u'master' : u'master', 
u'T@SHI' : u'【大→石】', 
u'T@GAO' : u'【大→高】', 
u'T@BEIZANG' : u'【大→北藏】', 
u'F' : u'【房山石徑】', 
u'T@SHENG' : u'【大→聖】', 
u'J' : u'【嘉興】', 
u'YAN' : u'【柳田版】', 
u'T@JIAKAOWEI' : u'【大→甲考偽】', 
u'T@TI' : u'【大→醍】', 
u'T@LONG' : u'【大→龍】', 
u'T@MING' : u'【大→明】', 
u'T@FUYI' : u'【大→福乙】', 
u'ZHW' : u'【維基文庫】', 
u'T@FU' : u'【大→福】', 
u'DALI' : u'【大曆】', 
u'T@NEI' : u'【大→內】', 
u'T@HARA' : u'【大→原】', 
u'T@SUO' : u'【大→縮】', 
u'T@QISHA' : u'【大→磧砂】', 
u'CBETA' : u'【電子佛典集成】', 
u'T@YUAN' : u'【大→元】', 
u'T@WU' : u'【大→戊】', 
u'A' : u'【趙城金藏】', 
u'M' : u'【卍正藏】', 
u'U' : u'【洪武南藏】', 
u'T@LIUBUBIE' : u'【大→流布別本】', 
u'T@DUNFANG' : u'【大→敦方】', 
u'T@SHIGU' : u'【大→獅谷】', 
u'T@LI-CBETA' : u'【大→麗-CB】', 
u'T@BEI' : u'【大→別】', 
})

dictab = {'cik' : u'探典釋辭',
          'hydcd1' : u'漢語大詞典',
          'hydcd' : u'漢語大詞典',
          'yd' : u'漢語大字典',
          'hydzd' : u'漢語大字典',
          'sanli' : u'三禮辭典',
          'daikanwa' : u'大漢和辞典',
          'koga' : u'禅語字典',
          'guoyu' : u'國語辭典',
          'abc' : u'ABC漢英詞典',
          'lyt' : u'林語堂當代漢英詞典',
          'cedict' : u'漢英詞典',
          'daojiao' : u'道教大辭典',
          'fks' : u'佛光佛學大辭典',
          'handedic' : u'漢德詞典',
          'dfb' : u'丁福報佛學大辭典',
          'unihan' : u'Unicode 字典',
          'kanwa' : u'發音',
          'kangxi' : u'康熙字典',
          'pinyin' : u'羅馬拼音',
          'loc' : u'其他詞典',
          'je' : u'日英仏教辞典',
          'kg' : u'葛藤語箋',
          'ina' : u'稲垣久雄:Zen Glossary',
          'iwa' : u'岩波仏教辞典',
          'zgd' : u'禪學大辭典',
          'oda' : u'織田佛教大辭典',
          'mz' : u'望月佛教大辭典',
          'matthews' : u'Matthews Chinese English Dictionary',
          'naka' : u'佛教語大辭典',
          'yo' : u'横井日英禪語辭典',
          'zgo' : u'禅の語録',
          'zhongwen' : u'中文大辭典',
          'bsk' : u'佛書解説大辭典',
          'bcs' : u'佛教漢梵大辭典',
          'zd' : u'Zen Dust',
          'ku' : u'ku',
          'sks' : u'sks',
          'guxun' : u'故訓匯纂',
          } 


## helper routines
# dic
def formatle(l, e, dicurl):
    "formats the location entry"
    ec = e.split('-')
    if l == "daikanwa":
        #V01-p00716-172
        return "[[%sdkw/p%s-%s#%s][%s : %s]]" % (dicurl, ec[0][1:], ec[1][1:], ec[-1], dictab[l], e)
    elif l == "hydzd" :
        return "[[%shydzd/hydzd-%s][%s : %s]]" % (dicurl, ec[1], dictab[l], e)
    #comment the next two lines to link to the cached files on the server
    elif l == "kangxi":
        return "[[http://www.kangxizidian.com/kangxi/%4.4d.gif][%s : %s]]" % (int(e), dictab[l], e)
    elif l in ["koga", "ina", "bcs", "naka", "zgd", "sanli", "kangxi"] :
        if "," in e:
            v = e.split(',')[0]
        else:
            v = e
        v = re.sub('[a-z]', '', v)
        try:
            return "[[%s%s/%s-p%4.4d][%s : %s]]" % (dicurl, l, l, int(v), dictab[l], e)
        except:
            return "%s : %s" % (dictab[l], e)
            
    elif l == "yo":
        ec = e.split(',')
        return "[[%syokoi/yokoi-p%4.4d][%s : %s]]" % (dicurl, int(ec[0]), dictab[l], e)
    elif l == "mz":
        v = e.split(',')[0]
        v = v.split('p')
#        return "[[%smz/vol%2.2d/mz-v%2.2d-p%4.4d][%s : %s]]" % (dicurl, int(v[0][1:]), int(v[0][1:]), int(re.sub('[a-z]', '', v[1])),  dictab[l], e)
        return "[[%smz/mz-v%2.2d-p%4.4d][%s : %s]]" % (dicurl, int(v[0][1:]), int(re.sub('[a-z]', '', v[1])),  dictab[l], e)
    elif l == "je":
        ec = e.split('/')
        if ec[0] == '---':
            v = re.sub('[a-z]', '', ec[1])
        else:
            v = re.sub('[a-z]', '', ec[0])
        return "[[%sjeb/jeb-p%4.4d][%s : %s]]" % (dicurl, int(v), dictab[l], e)
    elif l == "zhongwen":
        # zhongwen : V09-p14425-1
        return "[[%szhwdcd/zhwdcd-p%5.5d][%s : %s]]" % (dicurl, int(ec[1][1:]), dictab[l], e)
    elif l == "oda" :
        ec = e.split('*')
        try:
            pg = int(ec[-1].split('-')[0])
        except:
            pg = 0
        return "[[%soda/oda-p%4.4d][%s : %s]]" % (dicurl, pg, dictab[l], e)
    else:
        try:
            return "%s : %s" % (dictab[l], e)
        except:
            return "%s : %s" % (l, e)
            
def dicentry(key, dicurl):
    # Dictionary backend (formerly a separate Redis db) is not wired up in
    # this build. Returning empty so the /dic endpoint degrades gracefully.
    return ""

def prevnext(page):
    p = page.split('-')
    if p[-1].startswith ('p'):
        n= int(p[-1][1:])
        fn = fn = "%%%d.%dd" % (len(p[-1]) - 1, len(p[-1]) - 1)
        prev = "%s-p%s" % ("-".join(p[:-1]), fn % (n - 1) )
        next = "%s-p%s" % ("-".join(p[:-1]), fn % (n + 1) )
    else:
        n= int(p[-1])
        fn = fn = "%%%d.%dd" % (len(p[-1]), len(p[-1]))
        prev = "%s-%s" % ("-".join(p[:-1]), fn % (n - 1) )
        next = "%s-%s" % ("-".join(p[:-1]), fn % (n + 1) )
    return prev, next

## search


def _escape_fts(key):
    """Quote a user query for the FTS5 MATCH operator."""
    return '"' + key.replace('"', '""') + '"'


def _ft_search_clause(key):
    """Return (where_sql, params_tail) for searching `content` for `key`.

    The FTS5 trigram tokenizer requires queries of >=3 characters. Shorter
    queries fall back to LIKE on the same column.
    """
    if len(key) >= 3:
        return "search_idx MATCH ?", (_escape_fts(key),)
    return "content LIKE ?", ("%" + key + "%",)


def _filter_clause(filters, dynasty):
    """Return (extra_sql, params) to append to a search query."""
    sql_parts = []
    params = []
    for f in filters or []:
        if not f:
            continue
        sql_parts.append("substr(txtid,1,?) = ?")
        params.extend([len(f), f])
    if dynasty:
        sql_parts.append(
            "txtid IN (SELECT txtid FROM metadata WHERE dynasty = ?)"
        )
        params.append(dynasty)
    if not sql_parts:
        return "", []
    return " AND " + " AND ".join(sql_parts), params


def doftsearch(key, filters=None, dynasty=None, offset=0, limit=20):
    """Full-text search via FTS5 trigram. Returns (rows, total).

    Each row is (content, location, txtid8). `location` is the
    "TXTID_JUAN:PAGE:LINE" string consumed by result.html.
    """
    if not key:
        return [], 0
    where_sql, where_params = _ft_search_clause(key)
    extra_sql, extra_params = _filter_clause(filters, dynasty)
    params = list(where_params) + list(extra_params)
    db = get_db()
    total = db.execute(
        f"SELECT COUNT(*) FROM search_idx WHERE {where_sql}{extra_sql}",
        params,
    ).fetchone()[0]
    rows = db.execute(
        f"SELECT content, location, txtid FROM search_idx"
        f" WHERE {where_sql}{extra_sql}"
        f" ORDER BY location LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    out = [(gaiji.sub("⬤", r["content"]), r["location"], r["txtid"]) for r in rows]
    return out, total


def dotitlesearch(key, offset=0, limit=20):
    """Substring title search. Returns (rows, total). Each row is (txtid, title)."""
    if not key:
        return [], 0
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM titles WHERE title LIKE ?",
        ("%" + key + "%",),
    ).fetchone()[0]
    rows = db.execute(
        "SELECT txtid, title FROM titles WHERE title LIKE ?"
        " ORDER BY title LIMIT ? OFFSET ?",
        ("%" + key + "%", limit, offset),
    ).fetchall()
    return [(r["txtid"], r["title"]) for r in rows], total


def _row_to_meta(row):
    if row is None:
        return {}
    if row["raw_json"]:
        import json
        try:
            data = json.loads(row["raw_json"])
        except Exception:
            data = {}
    else:
        data = {}
    data.setdefault("TITLE", row["title"] or "")
    data.setdefault("DYNASTY", row["dynasty"] or "")
    data.setdefault("COLLECTION", row["collection"] or "")
    return data


def get_meta(txtid8):
    """Return the metadata dict for an 8-char txtid, or {}."""
    db = get_db()
    row = db.execute(
        "SELECT title, dynasty, collection, raw_json FROM metadata WHERE txtid = ?",
        (txtid8,),
    ).fetchone()
    data = _row_to_meta(row)
    data["ID"] = txtid8
    return data


def get_meta_many(txtids):
    """Return {txtid: meta_dict} for the given ids in a single query."""
    ids = [t for t in txtids if t]
    if not ids:
        return {}
    db = get_db()
    placeholders = ",".join(["?"] * len(ids))
    rows = db.execute(
        f"SELECT txtid, title, dynasty, collection, raw_json"
        f" FROM metadata WHERE txtid IN ({placeholders})",
        ids,
    ).fetchall()
    out = {}
    for r in rows:
        m = _row_to_meta(r)
        m["ID"] = r["txtid"]
        out[r["txtid"]] = m
    return out


def get_facets(key, tpe="ID", id_len=3, top_n=10, filters=None, dynasty=None):
    """Return facet rows for the search-results sidebar.

    Each row is (facet_key, metadata_dict, count, type_label).
    """
    if not key:
        return []
    where_sql, where_params = _ft_search_clause(key)
    extra_sql, extra_params = _filter_clause(filters, dynasty)
    params = list(where_params) + list(extra_params)
    db = get_db()
    limit_clause = f" LIMIT {int(top_n)}" if top_n else ""
    if tpe == "DYNASTY":
        rows = db.execute(
            f"SELECT m.dynasty AS facet, COUNT(*) AS n"
            f" FROM search_idx JOIN metadata m ON m.txtid = search_idx.txtid"
            f" WHERE {where_sql}{extra_sql} AND m.dynasty IS NOT NULL AND m.dynasty != ''"
            f" GROUP BY m.dynasty ORDER BY n DESC{limit_clause}",
            params,
        ).fetchall()
        return [(r["facet"], {"TITLE": r["facet"]}, r["n"], tpe) for r in rows]
    rows = db.execute(
        f"SELECT substr(txtid,1,?) AS facet, COUNT(*) AS n"
        f" FROM search_idx WHERE {where_sql}{extra_sql}"
        f" GROUP BY facet ORDER BY n DESC{limit_clause}",
        [int(id_len)] + params,
    ).fetchall()
    meta_by_id = get_meta_many([r["facet"] for r in rows])
    return [(r["facet"],
             meta_by_id.get(r["facet"]) or {"ID": r["facet"]},
             r["n"], tpe)
            for r in rows]

## helper object for view, this could at some point be moved into a flask extension
class Pagination(object):
    """Internal helper class returned by :meth:`BaseQuery.paginate`.  You
    can also construct it from any other SQLAlchemy query object if you are
    working with other libraries.  Additionally it is possible to pass `None`
    as query object in which case the :meth:`prev` and :meth:`next` will
    no longer work.
    """

    def __init__(self, query, page, per_page, total, items):
        #: the unlimited query object that was used to create this
        #: pagination object.
        # ie, the query string
        self.query = query
        #: the current page number (1 indexed)
        self.page = page
        #: the number of items to be displayed on a page.
        self.per_page = per_page
        #: the total number of items matching the query
        self.total = total
        #: the items for the current page
        self.items = items

    @property
    def pages(self):
        """The total number of pages"""
        if self.per_page == 0:
            pages = 0
        else:
            pages = int(ceil(self.total / float(self.per_page)))
        return pages

    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page - 1, self.per_page, error_out)

    @property
    def prev_num(self):
        """Number of the previous page."""
        return self.page - 1

    @property
    def has_prev(self):
        """True if a previous page exists"""
        return self.page > 1

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page + 1, self.per_page, error_out)

    @property
    def has_next(self):
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_num(self):
        """Number of the next page"""
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        """Iterates over the page numbers in the pagination.  The four
        parameters control the thresholds how many numbers should be produced
        from the sides.  Skipped page numbers are represented as `None`.
        This is how you could render such a pagination in the templates:

        .. sourcecode:: html+jinja

            {% macro render_pagination(pagination, endpoint) %}
              <div class=pagination>
              {%- for page in pagination.iter_pages() %}
                {% if page %}
                  {% if page != pagination.page %}
                    <a href="{{ url_for(endpoint, page=page) }}">{{ page }}</a>
                  {% else %}
                    <strong>{{ page }}</strong>
                  {% endif %}
                {% else %}
                  <span class=ellipsis>…</span>
                {% endif %}
              {%- endfor %}
              </div>
            {% endmacro %}
        """
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and \
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

def gettaisho(vol, page):
    "Retrieves the file for a pair of volume, page of the taisho."
    vol = vol.upper()
    page = page.lower().replace("p", "")
    tmp = re.split("([a-z])", page)
    if len(tmp) == 1:
        tmp.append("a")
    if len(tmp) == 2 or len(tmp[2]) < 2:
        tmp[2] = "00"
    try:
        pn = int(tmp[0] + str(ord(tmp[1]) - 96) + tmp[2])
    except (ValueError, IndexError):
        pn = 0
    db = get_db()
    row = db.execute(
        "SELECT filename, pagekey FROM taisho_pages"
        " WHERE vol = ? AND pagekey BETWEEN ? AND ? AND pagekey > ?"
        " ORDER BY pagekey LIMIT 1",
        (vol, pn - 20000, pn + 20000, pn),
    ).fetchone()
    if row is None:
        return False
    return row["filename"].split("_")

def partition(lst, n):
    division = len(lst) / float(n)
    return [ lst[int(round(division * i)): int(round(division * (i + 1)))] for i in range(n) ]

def cscore(s, ref):
    m = SequenceMatcher()
    m.set_seq1(ref)
    m.set_seq2(s)
    return m.quick_ratio()

def consorted(defdic):
    #This will take a dictionary of lists and consolidate the list
    #elements in the list are tuples: score, text, location, key
    #scores are added, text values aggregated, one location will be
    #used an the key ignored
    out = []
    for d in defdic:
        s = 0
        t = ""
        for l in defdic[d]:
            s += l[0]
            if len(t) > 0:
                t = t + " / " + l[1] + "-(%s)" % (l[3]) 
            else:
                t = l[1] + "-(%s)" % (l[3]) 
        #print s, t, d, defdic[d]
        out.append((s, t, defdic[d][0][2]))
    out = sorted(out, key=lambda x : x[0], reverse=True)
    return out

def kformat(a):
    "make an indexloc sortable KR4d0427_006:6b:5:4:8, or KR5i0038_002:02p049b:10:21:20" 
    t1 = a.split(":")
    a = "%s:%4.4d%s%3.3d%3.3d%6.6d" % (t1[0], int(t1[1][:-1].replace("p", "0")), t1[1][-1], int(t1[2]), int(t1[3]), int(t1[4]))
    return a

def kclose(a, b):
    """determine if the index location a is close to the index location
b. Close means in the same juan on neighbouring lines."""
    resp=False
    tx =[a.split(":"), b.split(":")]
    # different text/juan
    if tx[0][0] == tx[1][0]:
        if tx[0][1] == tx[1][1]:
            if abs(int(tx[0][2]) - int(tx[1][2])) < 2:
                resp = True
        else:
            #different pages: are we on neighbouring pages?
            try:
                if abs(int(tx[0][1][:-1]) - int(tx[1][1][:-1])) < 2:
                    #one has to be line 1, the other? fairly large?, not 1
                    if min(int(tx[0][2]), int(tx[1][2])) == 1 and max(int(tx[0][2]), int(tx[1][2])) > 1:
                        resp = True
            except:
                pass
    return resp


def kcondense (res, kf = lambda x : x.split("\t")[1]):
    """This will return a list with locations that occur in proximity,
grouped in lists of adjoining results. The list has to be sorted by
location."""
    out = []    
    for i, rx in enumerate(res):
        if len(out) > 0:
            if kclose(kf(out[-1][-1]), kf(res[i])):
                if res[i] in out[-1]:
                    pass
                else:
                    out[-1].append(res[i])
                continue
        if i < len(res) - 1:
            if kclose(kf(res[i]), kf(res[i+1])):
                out.append([res[i], res[i+1]])
    return out

def krestore(l):
    """Restores an index line to the original string, removes the location"""
    fx = l.split("\t")[0].split(",")
    if len(fx) > 1:
        return "%s%s" % (fx[1], fx[0])
    else:
        return fx[0]
    

def kcombine(lx):
    """Combines the index items in the list to one string where possible."""
    res = lx[0]
    for s in lx[1:]:
        tmp = res[-4:]
        if s.find(tmp) > 0:
            res = res + s[s.index(tmp):]
        else:
            res = res + " / " + s
    return res
