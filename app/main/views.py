#    -*- coding: utf-8 -*-
from flask import Response, session, render_template, redirect, url_for, abort, flash, request, current_app, make_response, send_from_directory, g
from markupsafe import Markup
from flask_login import current_user
from flask_babel import gettext, ngettext
from flask_sqlalchemy.record_queries import get_recorded_queries
from flask_dance.contrib.github import make_github_blueprint, github
from github import Github
import urllib

from . import main
# from .forms import EditProfileForm, EditProfileAdminForm, PostForm,\
#     CommentForm
from .. import db
from .. import lib
from .. import mybabel
#from ..models import Permission, Role, User, Post, Comment
#from ..decorators import admin_required, permission_required
from collections import Counter

from datetime import datetime
import subprocess

from collections import defaultdict

import codecs, re
from .. import mandoku_view
from .. import kr2tls
import git, requests, sys

from app import limiter


link_re = re.compile(r'\[\[([^\]]+)\]\[([^\]]+)')
img_re = re.compile(r'<i[^>]*>')
mdx_re = re.compile(r"<[^>]*>|[　-㄀＀-￯]|\n|¶")
mdx_re = re.compile(r"<[^>]*>|[　-㄀＀-￯\n\r¶]+|\t[^\n\r]+\r\n|\$[^;]+;")
hd = re.compile(r"^(\*+) (.*)$")

def get_locale():
    lg = request.values.get("lg", None)
    if lg:
        session['lg'] = lg
    if not lg:
        if "lg" in session:
            lg = session['lg']
        else:
            lg = request.accept_languages.best_match(
                current_app.config['LANGUAGES'].keys())
        if not lg:
            lg = "ja"
    return lg

@main.route('/favicon.ico')
@main.route('/robots.txt')
@main.route('/googled78ca805afaa95df.html')
# @main.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(current_app.static_folder, request.path[1:])

@main.route('/api')
def api_doc():
    return render_template("apidoc.html")

@main.route('/<coll>/search', methods=['GET', 'POST',])
@main.route('/search', methods=['GET', 'POST',])
@limiter.limit(lambda: current_app.config['RATELIMIT_DEFAULT'],
               exempt_when=lambda: 'user' in session)
def searchtext(count=20, page=1):
    key = request.values.get('query', '')
    count = int(request.values.get('count', count))
    page = int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    tpe = request.values.get('type', '')
    sort = request.values.get('sort', lib.SORT_POST)
    if not key:
        return render_template("error_page.html", code="400", name="Search Error",
                               description="No search term. Please submit the search term as parameter 'query'.")
    fs = [a for a in filters.split(';') if a]
    start = (page - 1) * count
    dynasty = fs[0] if (tpe == 'DYNASTY' and fs) else None
    id_filters = [] if dynasty else fs
    rows, total = lib.doftsearch(key, filters=id_filters, dynasty=dynasty,
                                  offset=start, limit=count, sort=sort)
    if total == 0:
        return render_template("error_page.html",
                               description="Text search for %s: Nothing found!" % (key), key=key)
    ox = [(content, location, lib.get_meta(txtid8))
          for (content, location, txtid8) in rows]
    p = lib.Pagination(key, page, count, total, ox)
    return render_template('result.html',
                           sr={'list': p.items, 'total': total}, key=key,
                           pagination=p,
                           pl={'1': 'a', '2': 'b', '3': 'c', '4': 'd'},
                           start=start, count=count,
                           n=min(start + count, total),
                           filter=";".join(fs), tpe=tpe, sort=sort)



@main.route('/<coll>/bytext', methods=['GET', 'POST',])
@main.route('/bytext', methods=['GET', 'POST',])
def searchbytext():
    key = request.values.get('query', '')
    filters = request.values.get('filter', '')
    if not key:
        return render_template("error_page.html", code="400", name="Search Error",
                               description="No search term. Please submit the search term as parameter 'query'.")
    fs = [a for a in filters.split(';') if a]
    rows = lib.hits_by_text(key, filters=fs)
    total = sum(n for (_id, _t, n) in rows)
    return render_template('bytext.html', rows=rows, key=key,
                           filter=";".join(fs), texts=len(rows), total=total)


@main.route('/text/<coll>', methods=['GET',] )
@limiter.limit(lambda: current_app.config['RATELIMIT_DEFAULT'],
               exempt_when=lambda: 'user' in session)
def showcoll(coll, edition=None, fac=False):
    return coll

# @main.route('/text/<id>/', methods=['GET',])
# def texttop(id=0, coll=None, seq=0):
#     ct = {'toc' : [], 'id' : id}
#     filename = "%s/%s/Readme.org" % (id[0:4], id[0:8])
#     datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
#     try:
#         datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
#         fn = codecs.open(datei, 'r', 'utf-8')
#     except:
#         return "File Not found: %s" % (filename)
#     for line in fn:
#         if line.startswith('#+TITLE:'):
#             ct['title'] = line[:-1].split(' ', 1)[-1]
#         if hd.search(line):
#             tmp = hd.findall(line)[0][0]
#             lev = len(tmp[0])
#         else:
#             tmp = ""
#         if link_re.search(line):
#             l = [tmp]
#             l.extend(re.findall(r'\[\[([^\]]+)\]\[([^\]]+)', line))
#             ct['toc'].append(l)
#     return  render_template('texttop.html', ct=ct)
#@main.route('/text/<coll>/<int:seq>/<int:juan>', methods=['GET',] )
@main.route('/text/<id>/', methods=['GET',])
@main.route('/text/<coll>/<seq>/<juan>', methods=['GET',] )
@main.route('/text/<id>/<juan>', methods=['GET',])
#TODO: add a redirect for these ?
@main.route('/edition/<branch>/<id>/<juan>', methods=['GET',])
@main.route('/edition/<branch>/<id>/', methods=['GET',])
#added new URL scheme for textref.org [2017-12-08T11:30:11+0900]
@main.route('/ed/<id>/<branch>/<juan>', methods=['GET',])
@main.route('/ed/<id>/<branch>/', methods=['GET',])
@limiter.limit(lambda: current_app.config['RATELIMIT_DEFAULT'],
               exempt_when=lambda: 'user' in session)
def showtext(juan="Readme.org", id=0, coll=None, seq=0, branch="master", user="kanripo"):
    master_only = current_app.config.get('MASTER_ONLY', False)
    if master_only and branch != "master" and 'user' not in session:
        abort(503, description="Alternate editions are temporarily unavailable.")
    editurl = False
    showtoc = True
    fn = ""
    key = request.values.get('query', '')
    templ = "%4.4d" if len(juan) == 4 else "%3.3d"
    try:
        juan = templ % (int(juan))
    except:
        showtoc = False
    if coll:
        if coll.startswith('KR'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            id = "Not Implemented"
    uid = current_app.config['GHKANRIPO']
    logged_in = 'user' in session
    gh_token = session.get('token') if logged_in else None
    use_github = current_app.config.get('USE_GITHUB', False) or logged_in
    txtdir = current_app.config['TXTDIR']
    repo_dir = "%s/%s/%s" % (txtdir, id[0:4], id[0:8])
    text_rel = juan if juan.startswith("Readme") else "%s_%s.txt" % (id, juan)
    toc_rel = "Readme.org"
    gh_owners = ([session['user']] if logged_in else []) + [uid]

    def read_local(rel):
        """Read `rel` from the local git repo at `repo_dir` for `branch`."""
        if branch == "master":
            try:
                with open("%s/%s" % (repo_dir, rel), "rb") as fh:
                    return fh.read()
            except Exception:
                return b""
        try:
            repo = git.Repo(repo_dir)
            return repo.tree(branch)[rel].data_stream.read()
        except Exception:
            return b""

    def fetch_gh(rel):
        """Try each candidate owner's fork on raw.githubusercontent.com."""
        headers = {'Authorization': 'token ' + gh_token} if gh_token else {}
        for owner in gh_owners:
            url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, id, branch, rel)
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    return r.content
            except Exception:
                continue
        return b""

    if use_github:
        fn = fetch_gh(text_rel)
        ftoc = fn if juan.startswith("Readme") else (fetch_gh(toc_rel) or read_local(toc_rel))
    else:
        fn = read_local(text_rel)
        ftoc = fn if juan.startswith("Readme") else read_local(toc_rel)
    if isinstance(ftoc, bytes):
        ftoc = ftoc.decode("utf-8", errors="replace")
    toc = defaultdict(list)
    for l in ftoc.split("\n"):
        if "file" not in l:
            continue
        re.sub(r"\[\[file:([^_]+)[^:]+::([^-]+)-([^]]+)\]\[([^]]+)\]",
               lambda x: toc[x.group(2)].append(x.groups()), l)
    if len(toc) < 1:
        for l in ftoc.split("\n"):
            if "file" not in l:
                continue
            re.sub(r"\[\[file:([^_]+)_([^\.]+)\.([^]]+)\]\[([^]]+)\]",
                   lambda x: toc[x.group(2)].append(x.groups()), l)
    tk = sorted(toc.keys())
    try:
        t2 = [[(a, b[2], b[3].split()[-1]) for b in toc[a]] for a in tk]
    except Exception:
        t2 = ""
    branches = []
    if not master_only or logged_in:
        if use_github:
            try:
                gh = Github(gh_token) if gh_token else Github()
                rp = gh.get_repo("%s/%s" % (uid, id))
                branches = [(a.name, lib.brtab[a.name]) for a in rp.get_branches()
                            if a.name not in ('_data', 'master')]
            except Exception:
                branches = []
        if not branches:
            try:
                repo = git.Repo(repo_dir)
                branches = [(a.name, lib.brtab[a.name]) for a in repo.branches
                            if a.name not in ('_data', 'master')]
            except Exception:
                branches = []
    if not fn:
        return "File Not found: %s/%s" % (branch, text_rel)
    if isinstance(fn, bytes):
        fn = fn.decode("utf-8", errors="replace")
    md = mandoku_view.mdDocument(fn, id, juan)
    res = lib.get_meta(id[0:8])
    res['ID'] = id
    title = res.get('TITLE', '')
    return render_template('showtext.html',
                           ct={'mtext': Markup("<br/>\n".join(md.md)), 'doc': res},
                           doc=res, key=key, title=title, txtid=res['ID'],
                           juan=juan, branches=branches, edition=branch,
                           toc=t2, showtoc=showtoc, editurl=editurl, ed=md.ed)


@main.route('/tlskr/<txtid>', methods=['GET',])
#def tlskr(txtid):
#    return Response(kr2tls.test(txtid), content_type="text/html;charset=UTF-8")

def tlskr_orig(txtid):
    return Response(kr2tls.convert_text(txtid), content_type="text/xml;charset=UTF-8")

## image

@main.route('/getimage', methods=['GET',])
def getimage():
    filename = request.values.get('filename', '')
    try:
        datei = "%s/%s" % (current_app.config['IMGDIR'], filename)
        fn = open(datei, encoding='utf-8')
    except Exception:
        return "Not found"
    return Response("\n%s" % (fn.read(-1)), content_type="text/plain;charset=UTF-8")

## dic  these two also in api

@main.route('/dicpage/<dic>/<page>', methods=['GET',])
def dicpage(dic=None,page=None):
#    pn = "a", "b"
    pn = lib.prevnext(page)
    us = url_for('static', filename='dic')
    return """<html>
<body>
<img src="%s/%s/%s.png" style="width:100%%;"/>
<a href="/dicpage/%s" type="button" id="btnPrev" >%s</a>
<a href="/dicpage/%s" type="button" id="btnNext">%s</a>
</body>
</html>""" % (us, dic, page, "%s/%s" % (dic, pn[0]), pn[0], "%s/%s" % (dic, pn[1]), pn[1])

@main.route('/dic', methods=['GET',])
def searchdic():
    key = request.values.get('query', '')
    return lib.dicentry(key, current_app.config['DICURL'])


## catalog
@main.route('/catalog', methods=['GET',])
def catalog():
    coll = request.values.get('coll', '')
    label = request.values.get('label', '')
    db = lib.get_db()
    if not coll:
        rows = db.execute(
            "SELECT substr(txtid,1,4) AS prefix, COUNT(*) AS n"
            " FROM metadata GROUP BY prefix ORDER BY prefix"
        ).fetchall()
        cat = [{'ID': r['prefix'], 'TITLE': f"{r['prefix']} ({r['n']})",
                'TYPE': 'collection'} for r in rows]
    else:
        rows = db.execute(
            "SELECT txtid FROM metadata WHERE txtid LIKE ? ORDER BY txtid",
            (coll + '%',),
        ).fetchall()
        cat = [lib.get_meta(r['txtid']) for r in rows]
    return render_template('catalog.html', cat=cat,
                           sr={'total': len(cat), 'coll': coll},
                           pagination=None, label=label, allc=len(cat))

@main.route('/titlesearch', methods=['GET',])
def titlesearch(count=20, page=1):
    lg=get_locale()
    key = request.values.get('query', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    fs = [a for a in filters.split(';') if len(a) > 1]
    if not key:
        return render_template("error_page.html", code="400", name="Search Error",
                               description="No search term. Please submit the search term as parameter 'query'.")
    start = (page - 1) * count
    rows, total = lib.dotitlesearch(key, offset=start, limit=count)
    if total == 0:
        return render_template("error_page.html",
                               description="Title search for %s: Nothing found" % (key), key=key)
    tits = [f"{txtid} {title}" for (txtid, title) in rows]
    p = lib.Pagination(key, page, count, total, tits)
    return render_template('titles.html',
                           sr={'list': p.items, 'total': total}, key=key,
                           pagination=p,
                           pl={'1': 'a', '2': 'b', '3': 'c', '4': 'd'},
                           start=start, count=count,
                           n=min(start + count, total),
                           filter=";".join(fs), prefix='')

## filter
@main.route('/getfacets', methods=['GET', ])
def getfacets():
    f = []
    key = request.values.get('query', '')
    tpe = request.values.get('type', 'ID')
    ln = int(request.values.get('len', '3'))
    cnt = int(request.values.get('cnt', '3'))
    top_n = cnt if cnt > 0 else 0
    fs = lib.get_facets(key, tpe=tpe, id_len=ln, top_n=top_n)
    return render_template('facets.html', fs=fs, key=key)

@main.route('/addfilter', methods=['GET',])
def addfilter(count=20, page=1):
    key = request.values.get('query', '')
    add = request.values.get('newfilter', '')
    filters = request.values.get('filter', '')
    count = int(request.values.get('count', count))
    page = int(request.values.get('page', page))
    fs = [a for a in filters.split(';') if a]
    if add:
        fs.append(add)
    start = (page - 1) * count
    rows, total = lib.doftsearch(key, filters=fs, offset=start, limit=count)
    oy = [(content, location, lib.get_meta(txtid8))
          for (content, location, txtid8) in rows]
    p = lib.Pagination(key, page, count, total, oy)
    return render_template('result.html',
                           sr={'list': p.items, 'total': total,
                               'head': '', 'link': ''},
                           key=key, pagination=p,
                           pl={'1': 'a', '2': 'b', '3': 'c', '4': 'd'})


@main.route('/remfilter', methods=['GET',])
def remfilter():
    # Placeholder kept for URL stability; filter state is encoded in the
    # client-side query string, so there's nothing to mutate here.
    return ('', 204)
    
## unrelated:

# @main.after_app_request
# def after_request(response):
#     for query in get_debug_queries():
#         if query.duration >= current_app.config['MDWEB_SLOW_DB_QUERY_TIME']:
#             current_app.logger.warning(
#                 'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
#                 % (query.statement, query.parameters, query.duration,
#                    query.context))
#     return response


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'


@main.route('/', methods=['GET', 'POST'])
def index():
    if "user" in session:
        user = session['user']
        #print "token", session['token']
    else:
        user = "Login"
    lg=get_locale()
    return render_template('index.html', user=user, lg=lg)

@main.route('/login/<user>', methods=['GET',])
def usersettings(user=None):
    print("user:", user)
    #implement some logic to
    # - see if we have the KR-Workspace on the user account, getting it if not.
    # - displaying some info and offering to change settings.
    pass

@main.route('/login',methods=['GET',])
def login():
    if not github.authorized:
        #print url_for("github.login")
        #return redirect("/")
        return redirect(url_for("github.login"))
    resp = github.get("/user")
    assert resp.ok
    session['user'] = resp.json()["login"]
    session['token'] = github.token["access_token"]
    flash(gettext("Welcome to the Kanseki Repository, user %(value)s! ", value= (session['user'])))
    return redirect(request.values.get('next') or '/')


@main.route('/profile/signout')
def signout():
    try:
        del session['user']
        del session['token']
    except KeyError:
        pass
    flash(gettext("You have been logged out."))
    return redirect(request.values.get('next') or '/')


@main.route('/about/<id>')
def about(id):
    if id=='dzjy':
        return render_template('about_dzjy.html')
    else:
        return render_template('about.html')

@main.route('/contact')
def contact():
    lg=get_locale()
    return render_template('contact.html', lg=lg)

@main.route('/taisho/<vol>/<page>', methods=['GET',])
def taisho(vol, page):
    fn=lib.gettaisho(vol, page)
    pg = re.split("([a-z])", page)
    if len(pg) == 1:
        pg.append("a")
    page = "%4.4d%s" % (int(pg[0]), pg[1])
    if fn:
        return redirect(url_for("main.showtext", juan=fn[1], id=fn[0], branch="CBETA", _anchor="%s-%s" %(fn[1], page )))
    else:
        return "%s %s Not found." % (vol, page)
# showtext(juan="Readme.org", id=0, coll=None, seq=0, branch="master", user="kanripo", loc="")

@main.route('/advsearch', methods=['GET','POST'])
def advsearch():
    help = "Under construction."
    return render_template('advsearch.html', res=[], help=help)

@main.route('/citfind', methods=['GET','POST'])
def citfind():
    cutoff = 0.7
    ima=datetime.now()
    if request.method == 'GET':
        help="""Enter the text you want to find parallels in the textfield above.
<p>The following options are available:</p> <ul> <li><b>How many times to
search?</b><br/>The text will be split into as many parts as indicated
here and for each of these parts a search will be executed and the
results will be consolidated. Alternatively the text can be split at a
linebreak (newline).  </li> <li><b>Consolidate by</b><br/>The search results
will be grouped together either by paragraph or by juan. Alternatively
"None" can be selected to do no consolidation.</li> <li><b>Cutoff
value</b><br/> The search results will be scored against the source text;
the score values are between 1.0 for identical strings and 0.0 for
completely different strings. Results with scores less than the cutoff
value will be ignored.</li> 
<li><b>Include branches</b><br/> By default only the master branch is used for scoring. Check here to include also other versions.</li></ul>"""
        return render_template('citfind.html', res=[], help=help, cutoff=cutoff)
    else:
        tbl=[]
        out = []
        x = 2
        n = 3
        acc = "para"
        if "br" in request.form:
            br = True
        else:
            br = False
        try:
            cutoff = float(request.form["cutoff"])
        except:
            cutoff = 0.4
        try:
            inp= request.form["inp"]
            x = int(request.form["x"])
            acc = request.form["acc"]
        except:
            inp=""
        if len(inp) > 0:
            if x == 0:
                inp = inp.replace("\n", "$$")
                inp = mdx_re.sub("", inp)
                strs = inp.split("$$")
            else:
                inp = mdx_re.sub("", inp)
                strs = lib.partition(inp, x)
            for s in strs:
                key = s[:n]
                if len(key) > 0:
                    pos = inp.index(s)
                    rows, _ = lib.doftsearch(key, limit=10000)
                    res = [(img_re.sub(u"〓", content), location, txtid8)
                           for (content, location, txtid8) in rows]
                    tbl.append((key, s, len(res)))
                    for content, location, txtid8 in res:
                        if br or (txtid8.startswith("KR") or txtid8.startswith("n")):
                            t = content.split(",")[0]
                            c = lib.cscore(t, inp[pos:pos+len(t)])
                            if c > cutoff:
                                out.append((c, t, location, key))
        out = sorted(out, key = lambda k : lib.kformat(k[2]))
        out = lib.kcondense(out, kf=lambda x : x[2])
        out = sorted(out, key = lambda k : len(k), reverse = True)
        o2 = []
        for o in out:
            c = 0
            s = lib.kcombine([lib.krestore(a[1]) for a in o])
            for k in [a[3] for a in o]:
                if k in s:
                    c += 1
            o2.append((c, s, o[0][2], ",".join([a[3] for a in o])))
        out = [(a, lib.get_meta(a[2].split(":")[0][0:8])) for a in o2]
        out = sorted(out, key = lambda k: k[0], reverse = True)
        elapsed = "%s" % (datetime.now() - ima).total_seconds()
        if x == 0:
            inp = "\n".join(strs)
        return render_template('citfind.html', tbl=tbl, inp=inp, res=out, df = elapsed, x=x, acc=acc, cutoff=cutoff)


@main.route('/locjump', methods=['GET','POST'])
def locjump():
    if request.method == 'GET':
        vol= ["T%2.2d"%(a) for a in range(1, 56)]
        vol.append("T85")
        return render_template('locjump.html', vol=vol)
    else:
        vol= request.form["vol"]
        page = request.form["page"]
        sec = request.form["sec"]
        page = "%4.4d%s" % (int(page), sec)
        fn=lib.gettaisho(vol, page)
        pg = re.split("([a-z])", page)
        if len(pg) == 1:
            pg.append("a")
        if fn:
            return redirect(url_for("main.showtext", juan=fn[1], id=fn[0], branch="CBETA", _anchor="%s-%s" %(fn[1], page )))
