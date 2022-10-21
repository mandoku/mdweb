#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
from flask import Response, session, render_template, redirect, url_for, abort, flash, Markup, request,\
    current_app, make_response, send_from_directory, g
from flask.ext.login import current_user
from flask.ext.babel import gettext, ngettext
#from flask.ext.sqlalchemy import get_debug_queries
## github authentication [2015-10-03T17:08:15+0900]
from werkzeug.contrib.fixers import ProxyFix
from flask_dance.contrib.github import make_github_blueprint   
from jinja2 import Environment, PackageLoader
from github import Github
import urllib

from . import main
# from .forms import EditProfileForm, EditProfileAdminForm, PostForm,\
#     CommentForm
from .. import db
from .. import redis_store
from .. import lib
from .. import babel
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


reload(sys)
sys.setdefaultencoding('utf-8')

zbmeta = "kr:meta:"
kr_user = "kr_user:"
titpref = "kr:title:"
link_re = re.compile(r'\[\[([^\]]+)\]\[([^\]]+)')
img_re = re.compile(ur'<i[^>]*>')
mdx_re = re.compile(ur"<[^>]*>|[　-㄀＀-￯]|\n|¶")
mdx_re = re.compile(ur"<[^>]*>|[　-㄀＀-￯\n\r¶]+|\t[^\n\r]+\r\n|\$[^;]+;")
hd = re.compile(r"^(\*+) (.*)$")
env = Environment(loader=PackageLoader('__main__', 'templates'))

#get the language, if provided save it, if it is saved, use it.  still needs a way to set it in the IF.    
@babel.localeselector
def get_locale():
    lg=request.values.get("lg", None)
    if lg:
        session['lg'] = lg
    if not lg:
        if "lg" in session:
            lg = session['lg']
        else:
            lg=request.accept_languages.best_match(current_app.config['LANGUAGES'].keys())
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

@main.route('/textlist/unload', methods=['GET',])
def unloadtextlist():
    tl=request.values.get("ffile")
    user=session['user']
    redis_store.delete("%s%s$%s" % (kr_user, user, tl))
    flash(gettext("File %(value)s removed from internal database.", value=tl))
    return redirect(request.values.get('next') or '/')
@main.route('/textlist/load', methods=['GET',])
def loadtextlist():
    tl=request.values.get("ffile")
    user=session['user']
    lib.ghfilterfile2redis("%s$%s" % (user, tl))
    try:
        flash(gettext("Loaded %(value)s into the internal database.", value=tl))
    except:
        flash(gettext("Could not load %(value)s." , value=tl))
    return redirect(request.values.get('next') or '/')
    
        
@main.route('/textlist/save', methods=['POST',])
def savetextlist():
    x = request.form.getlist("cb")
    fn= request.form["filename"]
    user=session['user']
    load = request.form.getlist("load")
    token=session['token']
    gh=Github(token)
    ws=gh.get_repo("%s/%s" % (user, "KR-Workspace"))
    fx = [redis_store.hgetall("%s%s" % (zbmeta, a)) for a in x]
    lines = ["%s\t%s"% (a['ID'], a['TITLE']) for a in fx]
    try:
        lib.ghsave(u"Texts/%s.txt" % (urllib.quote_plus(fn.encode("utf-8"))), "\n".join(lines), ws, new=True)
        flash(gettext("Saved text list for %(value)s with %(len)d texts", value=fn, len=len(lines)))
    except:
        flash(gettext("There was a problem saving the text list."))
    if len(load) > 0:
        try:
            lib.ghfilterfile2redis("%s$%s" % (user, fn))
            flash(gettext("Loaded the text list for %(value)s with %(len)d texts into the internal database.", value=fn, len=len(lines)))
        except:
            flash(gettext("There was a problem loading the text list."))
    return redirect(request.form.get('next') or '/')

@main.route('/bytext', methods=['GET',])
def bytext():
    ld = defaultdict(list)
    key = request.values.get('query', '')
    sort = request.values.get('sort', '+count')
    total = redis_store.llen(key)
    [ld[(a.split('\t')[1].split(':')[0].split("_")[0])].append(1) for a in redis_store.lrange(key, 0, total-1) if len(a) > 0]
    ox = [(a, len(ld[a])) for a in ld]
    if "txtid" in sort:
        ox = sorted(ox, key=lambda x : x[0], reverse= "-" in sort)
    elif "count":
        ox = sorted(ox, key=lambda x : x[1], reverse= "+" in sort)
    ids = [(redis_store.hgetall("%s%s" % (zbmeta, a[0])), a[1]) for a in ox]
    if "title" in sort:
        ids= sorted(ids, key=lambda x : x[0]['TITLE'])
    return render_template('bytext.html',  key=key, ret=ids, total=total, uniq = len(ids))

    
@main.route('/<coll>/search', methods=['GET', 'POST',])
@main.route('/search', methods=['GET', 'POST',])
def searchtext(count=20, page=1):
    rsort=""
    sort = request.values.get('sort', '')
    q = request.values.get('query', '')
    keys = q.split()
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    tpe = request.values.get('type', '')
    #store the search key, we retrieve this in the profile page
    if 'user' in session:
        user=session['user']
        sa=redis_store.sadd("%s%s:searchkeys" % (kr_user, user), q)
        ud=redis_store.hgetall("%s%s:settings" % (kr_user,user))
        if len(ud) < 1:
            lib.ghuserdata(user)
            ud=redis_store.hgetall("%s%s:settings" % (kr_user,user))
    else:
        ud={}
    if len(sort) < 1:
        try:
            sort = ud['sort']
        except:
            try:
                sort = session['sort']
            except:
                sort = ""
    if "date" in sort:
        #make sure we have the dates loaded
        if "textdates" in ud:
            td = ud["textdates"]
        else:
            td = "kanripo"
        rsort="%s%s:bydate" % (kr_user, td)
        if not redis_store.keys(rsort):
            ret=lib.ghtextdates(user, rsort)
    if len(filters) < 1:
        try:
            filter = ud['filter']
        except:
            pass
    if 'pinned' in ud:
        pinned=ud['pinned']
    if len(keys) > 0:
        for key in keys:
            if not redis_store.exists(key): 
                lib.doftsearch(key)
    else:
        return render_template("error_page.html", code="400", name = "Search Error", description = "No search term. Please submit the search term as parameter 'query'.")
    start = (page - 1) * count 
    fs = filters.split(';')
    fs = [a for a in fs if len(a) > 0]
    if "filter" in session:
        fs.append(session["filter"])
    # do we allow filters for AND search?  not for the moment...
    if len(keys) > 1:
        #so it seems that we cant have filter and AND at the same time...
        d1=defaultdict(list)
        d2=defaultdict(list)
        klen = ""
        sm=0
        ## find the key with fewest matches
        for key in keys:
            kl = redis_store.llen(key)
            if sm == 0 or sm > kl:
                sm = kl
                klen = key
        #get the results for the key with fewest matches
        total = redis_store.llen(klen)
        ox1 = [(a.split('\t')[1].split(':')[0]+'_'+a.split('\t')[1].split(':')[-1],
                ([a.split()[0].split(',')[1],klen[0], a.split()[0].split(',')[0]], a.split("\t")[1]))
               for a in redis_store.lrange(klen, 0, total-1) if len(a) > 0]
        for b,a in ox1:
            d1[b].extend(a)
        #now see what the other keys yield
        #print "d1:", len(d1)
        for key in keys:
            if key == klen:
                continue
            total = redis_store.llen(key)
            #print "key: ", key
            try:
                ox2 = [(a.split('\t')[1].split(':')[0]+'_'+a.split('\t')[1].split(':')[-1],
                    ([a.split()[0].split(',')[1],key[0], a.split()[0].split(',')[0]], "\t".join(a.split("\t")[1:])))
                   #(a.split()[0].split(','),key[0], a.split()[1]))
                   for a in redis_store.lrange(key, 0, total-1) if len(a) > 0]
            except:
                ox2 = []
            for b,a in ox2:
                if d1.has_key(b):
                    if not d2.has_key(b):
                        d2[b].append(d1[b])
                    d2[b].append(a)
        total = len(d2)
        #print "d2:", total, d2[d2.keys()[0]]
        #        ox = [("".join(d2[a][0][0]), d2[a][0][1], redis_store.hgetall(u"%s%s" %( zbmeta, a.split('_')[0][0:8])), " /".join(["".join([b[0][0] ]) for b in d2[a][1:][0]])) for a in d2.keys()]
        ox = [("".join(d2[a][0][0]), d2[a][0][1], redis_store.hgetall(u"%s%s" %( zbmeta, a.split('_')[0][0:8])), "　・　"+"/".join(["".join(b[0]) for b in d2[a][1:2]])) for a in d2.keys()]
    elif len(fs) < 1:
        key = keys[0]
        total = redis_store.llen(key)
            #first: sort, rsort is the redis key for
        rkey="key:%s" % (key)
        rkey = key
        if len(sort) > 0:
            ks = lib.sortres(rkey, sort, rsort)
            ox = [("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), "\t".join(k.split("\t")[1:]), redis_store.hgetall(u"%s%s" %( zbmeta, k.split("\t")[1].split(':')[0][0:8]))) for k, j in ks[start:start+count-1]]
        else:
            ox = [("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), "\t".join(k.split("\t")[1:]), redis_store.hgetall(u"%s%s" %( zbmeta, k.split("\t")[1].split(':')[0][0:8]))) for k in redis_store.lrange(rkey, start, start+count-1)]
        # except:
        #     ox = []
    else:
        key = keys[0]
        ox1 = lib.applyfilter(key, fs, tpe)
        total = len(ox1)
        ox = [("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), "\t".join(k.split("\t")[1:]), redis_store.hgetall(u"%s%s" %( zbmeta, k.split('\t')[1].split(':')[0][0:8]))) for k in ox1[start:start+count+1]]
    p = lib.Pagination(key, page, count, total, ox)
    return render_template('result.html', sr={'list' : p.items, 'total': total }, key=q, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' }, start=start, count=count, n = min(start+count, total), filter=";".join(fs), tpe=tpe, sort=sort)



@main.route('/text/<coll>', methods=['GET',] )
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
@main.route('/read/<branch>/<id>/<juan>', methods=['GET',])
@main.route('/read/<id>/<juan>', methods=['GET',])
@main.route('/read/<id>/', methods=['GET',])
def read(juan="Readme.org", id=0, seq=0, branch="master"):
    session['pinned']=id
    if "user" in session:
        user = session['user']
    else:
        return render_template("error_page.html", code="400", name = "Authentication Error", description = "User must be logged in for this function.")
    try:
        juan = "%3.3d" % (int(juan))
    except:
        showtoc = False
    if juan.startswith("Readme"):
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s" % (user, id, branch, juan)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s" % (user, id, branch, juan,)
    else:
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s_%s.txt" % (user, id, branch,  id, juan,)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s_%s.txt" % (user, id, branch,  id, juan,)
    r = requests.get(url)
    if r.status_code == 200:
        fn = r.content
    else:
        return render_template("error_page.html", code="400", name = "Authentication Error", description = "Please create a fork of this document before using this function.")
    md = mandoku_view.mdDocument(fn, id, juan)
    try:
        res = redis_store.hgetall("%s%s" % ( zbmeta, id[0:8]))
    except:
        res = {}
    res['ID'] = id
    try:
        title = res['TITLE'].decode('utf-8')
    except:
        title = ""
    return render_template('read.html', ct={'mtext': Markup("<br/>\n".join(md.md)), 'doc': res}, doc=res, title=title, txtid=res['ID'], juan=juan, editurl=xediturl)
#return Response ("\n%s" % ( "\n".join(md.md)),  content_type="text/html;charset=UTF-8")

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
def showtext(juan="Readme.org", id=0, coll=None, seq=0, branch="master", user="kanripo"):
    editurl=False
    showtoc = True
    doc = {}
    uid = user
    token = ""
    fn = ""
    key = request.values.get('query', '')
    if len(juan) == 4:
        templ = "%4.4d"
    else:
        templ = "%3.3d"
    try:
        juan = templ % (int(juan))
    except:
        showtoc = False
    if coll:
        #TODO: allow for different repositories, make this configurable
        if coll.startswith('KR'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            #TODO need to find the canonical id for this, go to redis, pull it out
            id="Not Implemented"
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    if "user" in session:
        user = session['user']
        uid = user
        user_settings=redis_store.hgetall("%s%s:settings" % (kr_user, user))
        if user_settings.has_key(id):
            uidbranch = user_settings[id].split("/")
            branch=uidbranch[-1]
            uid = uidbranch[0]
            token="%s" % (session['token'])
    #print user
    if juan.startswith("Readme"):
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s" % (uid, id, branch, juan)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s" % (uid, id, branch, juan,)
    else:
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s_%s.txt" % (uid, id, branch,  id, juan)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s_%s.txt" % (uid, id, branch,  id, juan,)
    # url =  "https://raw.githubusercontent.com/kanripo/%s/%s/%s_%s.txt?client_id=%s&client_secret=%s" % (id, branch,  id, juan,
    #     current_app.config['GITHUB_OAUTH_CLIENT_ID'],
    #     current_app.config['GITHUB_OAUTH_CLIENT_SECRET'])
    r = requests.get(url, auth=(user, token))
    print url, r.status_code
    if r.status_code == 200:
        fn = r.content
        editurl = xediturl
    else:
        if juan.startswith("Readme"):
            url =  "https://raw.githubusercontent.com/%s/%s/%s/%s" % (current_app.config['GHKANRIPO'], id, branch, juan,)
        else:
            url =  "https://raw.githubusercontent.com/%s/%s/%s/%s_%s.txt" % (current_app.config['GHKANRIPO'], id, branch,  id, juan,)
        r = requests.get(url)
        if r.status_code == 200:
            fn = r.content
        else:
            pass
            #print "Not retrieved from Gitlab!", id
    #print "fn, " , len(fn)
    tockey="%s%s:toc:%s:%s" % (kr_user, user, branch, id)
    if redis_store.hgetall(tockey):
        toc = redis_store.hgetall(tockey)
    else:
        if juan.startswith("Readme"):
            ftoc=fn
        else:
            tocurl = re.sub(r"KR[^/]+txt", "Readme.org", url)
            r = requests.get(tocurl)
            if r.status_code == 200:
                ftoc = r.content
            else:
                ftoc = ""
        toc = defaultdict(list)
        [re.sub(r"\[\[file:([^_]+)[^:]+::([^-]+)-([^]]+)\]\[([^]]+)\]", lambda x : toc[x.group(2)].append(x.groups()), l) for l in ftoc.split("\n") if "file" in l]
        if len(toc) < 1:
            [re.sub(r"\[\[file:([^_]+)_([^\.]+)\.([^]]+)\]\[([^]]+)\]", lambda x : toc[x.group(2)].append(x.groups()), l) for l in ftoc.split("\n") if "file" in l]
            
        try:
            redis_store.hmset(tockey, toc)
        except:
            pass
    tk = toc.keys()
    tk.sort()
    #print tockey
    #print tk
    try:
        t2 = [[(a, b[2], b[3].split()[-1]) for b in eval(toc[a])] for a in tk]
    except:
        try:
            t2 = [[(a, b[2], b[3].split()[-1]) for b in toc[a]] for a in tk]
        except:
            t2 = ""
    if branch == "master":
        #url =  "%s/%s/%s/raw/%s/%s_%s.txt?private_token=%s" % (current_app.config['GITLAB_HOST'], id[0:4], id,  id, juan, current_app.config['GITLAB_TOKEN'])

        filename = "%s/%s/%s_%s.txt" % (id[0:4], id[0:8], id, juan)
    else:
        filename = "%s/%s/_branches/%s/%s_%s.txt" % (id[0:4], id[0:8], branch, id, juan)
    datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
    rpath = "%s/%s/%s" % (current_app.config['TXTDIR'], id[0:4], id[0:8])
    #get branches  -- we could get this from github, but it counts against the limit...
    try:
        g=Github()
        if editurl:
            rp=g.get_repo(user + "/" +id)
        else:
            rp=g.get_repo("kanripo/" +id)
        branches=[(a.name, lib.brtab[a.name.decode('utf-8')]) for a in rp.get_branches() if not a.name in ['_data', 'master']]
        #print branches
    except:
        try:
            repo=git.Repo(rpath)
            branches=[(a.name.decode('utf-8'), lib.brtab[a.name.decode('utf-8')]) for a in repo.branches if not a.name in ['_data', 'master']]
        except:
            branches=[]
    if len(fn) == 0:
        try:
            datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
            fn = codecs.open(datei).read(-1)
            fn.close()
        except:
            return "File Not found: %s" % (filename)
    md = mandoku_view.mdDocument(fn, id, juan)
    try:
        res = redis_store.hgetall("%s%s" % ( zbmeta, id[0:8]))
    except:
        res = {}
    res['ID'] = id
    try:
        title = res['TITLE'].decode('utf-8')
    except:
        title = ""
    # else:
    #     md = mandoku_view.mdDocument(r.content.decode('utf-8'))
    #print "url: ", url
    return render_template('showtext.html', ct={'mtext': Markup("<br/>\n".join(md.md)), 'doc': res}, doc=res, key=key, title=title, txtid=res['ID'], juan=juan, branches=branches, edition=branch, toc=t2, showtoc=showtoc, editurl=editurl, ed=md.ed)
#return Response ("\n%s" % ( "\n".join(md.md)),  content_type="text/html;charset=UTF-8")


@main.route('/tlskr/<txtid>', methods=['GET',])
def tlskr(txtid):
    return Response(kr2tls.convert_text(txtid), content_type="text/xml;charset=UTF-8")

def showtextredis(juan, id=0, coll=None, seq=0):
    juan = "%3.3d" % (int(juan))
    if coll:
        if coll.startswith('KR'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            #TODO need to find the canonical id for this, go to redis, pull it out
            id="Not Implemented"
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    filename = "%s/%s/%s_%s.txt" % (id[0:4], id, id, juan)
    datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
    mr = mandoku_redis.RedisMandoku(redis_store, None, 100000, datei)
    
    return render_template('', ct={'mtext': md.md, 'doc' : doc} )
    

## image

@main.route('/getimage', methods=['GET',])
def getimage():
    filename = request.values.get('filename', '')
    try:
        datei = "%s/%s" % (current_app.config['IMGDIR'], filename)
        fn = codecs.open(datei)
    except:
        return "Not found"
    return Response ("\n%s" % (fn.read(-1)),  content_type="text/plain;charset=UTF-8")

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
def catalog(page=1, count=20, coll="", label=""):
    env.globals['session'] = session 
    page=int(request.values.get('page', page))
    count=int(request.values.get('count', count))
    label=request.values.get('label', label)
    r=redis_store
    coll = request.values.get('coll', '')
    subcoll = request.values.get('subcoll', '')
    if len(coll) < 1 and len(subcoll) < 1:
        cat = [r.hgetall(a) for a in r.keys("kr:meta*") if len(a.split(":")[-1]) < 8 and "KR" in a]
        cat.sort(key=lambda t : t['ID'])
    else:
        cat = [r.hgetall("%s%s" %( zbmeta, k.split(':')[-1])) for k in r.keys(zbmeta+coll+"*")]
        if coll in ['DZ', 'JY', 'T', 'X', 'SB']:
            cat.sort(key=lambda t : t['EXTRAID'])
        else:
            cat.sort(key=lambda t : t['ID'])
            cat = [a for a in cat if a['STATUS'] == "READY"]
    total = len(cat)
    tits = cat[(page-1)*count:page*count]
    p = lib.Pagination(coll, page, count, total, tits)
    return render_template('catalog.html', cat = cat, sr={'total': 0, 'coll': coll}, pagination=p, count=count, label=label, allc=len(cat))

@main.route('/titlesearch', methods=['GET',])
def titlesearch(count=20, page=1):
    lg=get_locale()
    key = request.values.get('query', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    fs = filters.split(';')
    fs = [a for a in fs if len(a) > 1]
    if len(key) > 0:
        if not redis_store.exists(titpref+key):
            if not(lib.dotitlesearch(titpref, key)):
                print "lg: ", lg
                if lg == 'ja':
                    return render_template("error_page.html", description = u"タイトル検索 %s: 該当するタイトルはありません。" % (key), key=key)
                else:
                    return render_template("error_page.html", description = "Title search for %s: Nothing found" % (key), key=key)
    else:
        return render_template("error_page.html", code="400", name = "Search Error", description = "No search term. Please submit the search term as parameter 'query'.")
    start = (page - 1) * count
    total = redis_store.llen(titpref+key)
    tits = redis_store.lrange(titpref+key, start, start+count)
    p = lib.Pagination(key, page, count, total, tits)
    return render_template('titles.html', sr={'list' : p.items, 'total': total }, key=key, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' }, start=start, count=count, n = min(start+count, total), filter=";".join(fs), prefix=titpref)

## filter
@main.route('/getfacets', methods=['GET', ])
def getfacets():
    f = []
    key = request.values.get('query', '')
    tpe = request.values.get('type', 'ID')
    prefix = request.values.get('prefix', '')
    # length of the ID
    ln = int(request.values.get('len', '3'))
    # number of top_most entries, 0 = all
    cnt = int(request.values.get('cnt', '3'))
    if 'user' in session:
        user = session['user']
    else:
        user = False
    if cnt == 0:
        cnt = None
    if tpe == 'ID':
        f = [a.split('\t')[1][0:ln] for a in redis_store.lrange(prefix+key, 1, redis_store.llen(prefix+key))]
    elif tpe == 'FILTER':
        fs = []
        if user:
            tf = redis_store.keys("%s%s$*" % (kr_user, user))
            for f in tf:
                fk, ft = f.split("$")
                fs.append(("$"+ft, {'TITLE': ft}, "", ft))
    elif tpe == 'DYNASTY':
        f = [redis_store.hgetall("%s%s" % (zbmeta, a.split('\t')[1].split('_')[0])) for a in redis_store.lrange(prefix+key, 1, redis_store.llen(prefix+key))]
        f = [a['DYNASTY'] for a in f if a.has_key('DYNASTY')]
    c = Counter(f)
    if tpe == 'ID':
        if ln == 4:
            fs = [(a[0], {'TITLE' : "%s/%s" % (redis_store.hgetall("%s%s" %(zbmeta, a[0][:-1]))['TITLE'], redis_store.hgetall("%s%s" %(zbmeta, a[0]))['TITLE'])}, a[1], tpe) for a in c.most_common(cnt)]
        else:
            fs = [(a[0], redis_store.hgetall("%s%s" %(zbmeta, a[0])), a[1], tpe) for a in c.most_common(cnt)]
    elif tpe == 'DYNASTY':
        fs = [(a[0], {'TITLE': a[0]}, a[1], tpe) for a in c.most_common(cnt)]
    return render_template('facets.html', fs=fs, key=key)
#    return Response("%s" % (c.most_common(cnt)))

@main.route('/addfilter', methods=['GET',])
def addfilter(count=20, page=1):
    key = request.values.get('query', '')
    add = request.values.get('newfilter', '')
    filters = request.values.get('filter', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    fs = filters.split(';')
    fs.append(add)
    start = (page - 1) * count  + 1
    ox = lib.applyfilter(key, fs)
    total = len(ox)
    ox = ox[start:start+count]
    oy = [  (k.split("\t")[0].split(','), k.split("\t")[1], redis_store.hgetall("%s%s" %( zbmeta, k.split("\t")[1].split(':')[0][0:8]))) for k in ox]
    p = lib.Pagination(key, page, count, total, oy)
    return render_template('result.html', sr={'list' : p.items, 'total': total, 'head' : '', 'link' : '' }, key=key, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' })
    

@main.route('/remfilter', methods=['GET',])
def remfilter():
    query = request.values.get('query', '')
    rem = request.values.get('remove', '')
    filters = request.values.get('filter', '')
    print filters
    
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
    print "user:", user
    #implement some logic to
    # - see if we have the KR-Workspace on the user account, getting it if not.
    # - displaying some info and offering to change settings.
    pass

@main.route('/login',methods=['GET',])
def login():
    flash("Login is not available at this moment.")
    return redirect(request.values.get('next') or '/')
    if not github.authorized:
        #print url_for("github.login")
        #return redirect("/")
        return redirect(url_for("github.login"))
    resp = github.get("/user")
    assert resp.ok
    session['user'] = resp.json()["login"]
    session['token'] = github.token["access_token"]
    #this is mainly to make sure we have a fork of the workspace
    ret = lib.ghclone(session['user'], session['token'])
    if len(ret) > 0:
        flash(ret)
    else:
        flash(gettext("Welcome to the Kanseki Repository, user %(value)s! ", value= (session['user'])))
    return redirect(request.values.get('next') or '/')


@main.route('/profile/signout')
def signout():
    try:
        del(session['user'])
        del(session['token'])
    except:
        pass
    flash(gettext("You have been logged out."))
    return redirect(request.values.get('next') or '/')

@main.route('/profile/<uid>/settings/reload')
def reloadsettings(uid):
    redis_store.delete("%s%s:settings" % (kr_user, uid))
    ret=lib.ghuserdata(uid)
    if ret == 1:
        flash(gettext("User data have been loaded into internal database."))
    else:
        flash(gettext("Could not load user data."))
    userdata=redis_store.hgetall("%s%s:settings" % (kr_user,uid))
    return redirect(request.values.get('next') or '/')

@main.route('/profile/<uid>/settings/save', methods=['POST',])
def saveuserdata(uid):
    sort = request.form.getlist("sort")[0]
    url = "{url}{user}/KR-Workspace/{user}/Settings/kanripo.cfg".format(url=current_app.config['GHRAWURL'], user=uid)
    r = requests.get(url)
    ol=[]
    if r.status_code == 200:
        for line in r.content.split("\n"):
            if line.startswith("sort"):
                line="sort=%s" % (sort)
            ol.append(line)
    token=session['token']
    gh=Github(token)
    ws=gh.get_repo("%s/%s" % (uid, "KR-Workspace"))
    try:
        lib.ghsave(u"Settings/kanripo.cfg", "\n".join(ol), ws)
        flash(gettext("The settings have been saved."))
    except:
        flash(gettext("There was a problem saving the settings."))
    return redirect(request.form.get('next') or '/')


@main.route('/profile/<uid>')
def profile(uid):
    #for the moment, load settings every time, later maybe expire after some minutes and then reload if necessary
    redis_store.delete("%s%s:settings" % (kr_user, uid))
    ret=lib.ghuserdata(uid)
    # if not redis_store.key("%s%s:settings" % (kr_user,uid)):
    # else:
    #     ret = 0
    r=[]
    for d in ["Texts", "Notes"]:
        r.append([d, lib.ghlistcontent("KR-Workspace", d, ext="txt")])
    try:
        loaded=[a.split("$")[-1] for a in redis_store.keys("%s%s$*" % (kr_user,uid))]
    except:
        loaded=[]
    try:
        searchkeys=[a for a in redis_store.smembers("%s%s:searchkeys" % (kr_user, uid))]
    except:
        searchkeys=[]
    if ret == 1:
        flash(gettext("User data have been loaded into internal database."))
    elif ret == -1:
        flash(gettext("Could not load user data."))
    userdata=redis_store.hgetall("%s%s:settings" % (kr_user,uid))
    return render_template('profile.html', user=uid, ret=r, loaded=loaded, searches=searchkeys, userdata=userdata)
    

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
    ima=datetime.now()
    help="Under construction."
    if request.method == 'GET':
        return render_template('advsearch.html', res=[], help=help)
    else:
        return render_template('advsearch.html', res=[], help=help)
        keys = [request.form["key0"],request.form["key1"],request.form["key2"]]
        conn = ['or', request.form["conn1"], request.form["conn2"]]
        acc = request.form["acc"]
        rt = [[],[],[]]
        for j, k in enumerate(keys):
            rx = []
            if len(k) > 0 (j == 0 or conn[j] in ["and", "or"]):
                if j == 0 or acc != "line":
                    if not redis_store.exists(k): 
                        lib.doftsearch(k)
                rx = [k[0:1]+a for a in redis_store.lrange(k, 0, -1)]
            rt[j] = rx
        out = []
        for j, k in enumerate(rt):
            for g in k:
                if conn[j] == 'or':
                    # now construct the key
                    out.append
                
        if acc == "line":
            for r in rx:
                pass
        for j in [1, 2]:
            pass
        ld = defaultdict(list)
        for o in out:
            kx = o[2].split(":")
            if acc == "para":
                akey = kx[0]+":"+kx[-1]
            else:
                akey = kx[0]
            ld[akey].append((o))
        if acc != "line":
            out = lib.consorted(ld)
            
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
        if request.form.has_key("br"):
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
            print inp
            for s in strs:
                #we take the first n chars
                key = s[:n]
                if len(key) > 0:
                    pos = inp.index(s)
                    #print key, s
                    if not redis_store.exists(key): 
                        lib.doftsearch(key, exp=False)
                    res = [key[0:1]+a for a in redis_store.lrange(key, 0, -1)]
                    res = [img_re.sub(u"〓",a) for a in res]
                    res = [a.split("\t") for a in res]
                    tbl.append((key, s, len(res)))
                    for r in res:
                        if br or (r[-1].startswith("KR") or r[-1].startswith("n")):
                            t = r[0].split(",")[0]
                            c = lib.cscore(t, inp[pos:pos+len(t)])
                            if c > cutoff:
                                out.append((c, t, r[1], key))
        out = sorted(out, key = lambda k : lib.kformat(k[2]))
        out = lib.kcondense(out, kf=lambda x : x[2])
        out = sorted(out, key = lambda k : len(k), reverse = True)
        o2 = []
        for o in out:
            c = sum([a[0] for a in o])
            c = 0
            s = lib.kcombine([lib.krestore(a[1]) for a in o])
            for k in [a[3] for a in o]:
                if k in s:
                    c += 1
            o2.append((c, s, o[0][2], ",".join([a[3] for a in o])))
        out = [(a, redis_store.hgetall(u"%s%s" %( zbmeta, a[2].split(":")[0][0:8]))) for a in o2]
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
