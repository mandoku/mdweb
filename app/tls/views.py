#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
from flask import Response, session, render_template, redirect, url_for, abort, flash, Markup, request,\
    current_app, make_response, send_from_directory, g
from flask.ext.login import current_user
from flask.ext.babel import gettext, ngettext
#from flask.ext.sqlalchemy import get_debug_queries
## github authentication [2015-10-03T17:08:15+0900]
from werkzeug.contrib.fixers import ProxyFix
from flask_dance.contrib.github import make_github_blueprint, github
from jinja2 import Environment, PackageLoader
from github import Github
import urllib

from . import tls
# from .forms import EditProfileForm, EditProfileAdminForm, PostForm,\
#     CommentForm
from .. import db
from .. import redis_store
from .. import tlsdb
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
import git, requests, sys


reload(sys)
sys.setdefaultencoding('utf-8')
kr_user = "kr_user:"
zbmeta = "kr:meta:"
titpref = "kr:title:"

tls_root = "/home/chris/tlsdev/krp/tls/lexicon/"
swl_txt = tls_root + "index/swl.txt"
swl_key = "swl::"
syl_txt = tls_root + "index/syllables.txt"
syl_key = "syl::"
syn_txt = tls_root + "index/syn-func.txt"
funx = {"syn-func" : "syn-func::", "sem-feat" : "sem-feat::"}
char_txt = tls_root + "core/characters.tab"
char_key = "char::"
con_dir = tls_root + "concepts/"
con_key = "con::"
zhu_dir = tls_root + "notes/zhu/"
zhu_key = "zhu::"

link_re = re.compile(r'\[\[([^\]]+)\]\[([^\]]+)')
hd = re.compile(r"^(\*+) (.*)$")
#env = Environment(loader=PackageLoader('__tls__', 'templates'))


def static_from_root():
    return send_from_directory(current_app.static_folder, request.path[1:])

#@tls.route('/concept/<id>', methods=['GET', 'POST',])
#def display_concept(id):
#    c=redis_store.hgetall("%s%s" % (con_key,id))

@tls.route('/index', methods=['GET',])
def tls_index():
    """Show the start page for tls"""
    return


# @tls.route('/<coll>/search', methods=['GET', 'POST',])
# @tls.route('/search', methods=['GET', 'POST',])
# def searchconcept(count=20, page=1):
#     rsort=""
#     sort = request.values.get('sort', '')
#     q = request.values.get('query', '')

@tls.route('/concept', methods=['GET'],)
@tls.route('/concept/<concept_id>', methods=['GET'],)
def showconcept(concept_id=None):
    if concept_id:
        print "id:", concept_id
    else:
        concept_id=request.values.get('id', 'ADMIRE')
    print "id:, ", concept_id
    res = tlsdb.hgetall(con_key + concept_id)
    print len(res)
    for k in res.keys():
        kn = k.replace("+", "")
        try:
            res[kn] = eval(res[k])
        except:
            pass
    return render_template('concept.html', c=res)



@tls.route('/index', methods=['GET',])
@tls.route('/', methods=['GET',])
def index():
    return render_template('tls.html', concept="START")
#    return "INDEX"
@tls.route('/concepts/browse', methods=['GET',])
def concepttree():
    s=request.values.get("query", "N/A")
    r=tlsdb.hgetall(con_key+s)
    try:
        p = eval(r['pointers'])
    except:
        p = {'NO POINTER' : []}
    res = p
    t = []
    # get the tree for s
    while p.has_key("KIND OF"):
        t.append(p["KIND OF"][0])
        r=tlsdb.hgetall(con_key + p["KIND OF"][0])
        print r
        try:
            p = eval(r['pointers'])
        except:
            p = {'NO POINTER' : []}
    # search for concepts, 
    return render_template('tlstaxtree.html', res=res, q=s, tree=t)

@tls.route('/search', methods=['GET',])
def conceptsearch():
    # give the start of the concept tree, at the given concept
    s=request.values.get("query", "N/A")
    res={}
    if len(res) == 0:
        pass
    # search for concepts, 
    return render_template('tlssearch.html', res=res)


@tls.route('/func/<type>/<uuid>', methods=['GET',])
def showsynsem(type=None, uuid=None):
    res=tlsdb.hgetall(funx[type]+uuid)
    inst=eval(res['inst'])
    new=[]
    for i in inst:
        l = tlsdb.lrange(swl_key+i, 0, -1)
        for b in [a.split("##") for a in l]:
            f = {'loc': b[0], 'char': b[4], 'line': b[5], 'title' : b[1]}
            new.append(f)
    res['inst'] = new
    return render_template("funx.html", res=res)


#@main.route('/text/<id>/', methods=['GET',])
@tls.route('/text/<loc>', methods=['GET',])
@tls.route('/text/<id>/<juan>', methods=['GET',])
#@main.route('/edition/<branch>/<id>/<juan>', methods=['GET',])
#@main.route('/edition/<branch>/<id>/', methods=['GET',])
def showtext(juan="Readme.org", id=0, coll=None, seq=0, branch="master", user="kanripo", loc=""):
    rp = False
    editurl=False
    showtoc = True
    doc = {}
    uid = user
    token = ""
    fn = ""
    key = request.values.get('query', '')
    if user=='tls-kr':
        branch = "tls-annot"
    if len(loc) > 0:
        floc = loc.split(":")
        id = floc[0].split("_")[0]
        juan = floc[0].split("_")[1]
        if key == '':
            key = floc[-1]
        print id, juan, key
    try:
        juan = "%3.3d" % (int(juan))
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
    #print uid, user
    if juan.startswith("Readme"):
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s" % (uid, id, branch, juan)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s" % (uid, id, branch, juan,)
    else:
        url =  "https://raw.githubusercontent.com/%s/%s/%s/%s_%s.txt" % (uid, id, branch,  id, juan)
        xediturl =  "https://github.com/%s/%s/edit/%s/%s_%s.txt" % (uid, id, branch,  id, juan,)
    # url =  "https://raw.githubusercontent.com/kanripo/%s/%s/%s_%s.txt?client_id=%s&client_secret=%s" % (id, branch,  id, juan,
    #     current_app.config['GITHUB_OAUTH_CLIENT_ID'],
    #     current_app.config['GITHUB_OAUTH_CLIENT_SECRET'])
    if "token" in session:
        g=Github(session['token'])
        rp = g.get_repo("%s/%s" % (uid, id))
        try:
            rpn=rp.full_name
        except:
            try:
                rp = g.get_repo("tls-kr/%s" % (id))
                rpn=rp.full_name
            except:
                try:
                    rp = g.get_repo("kanripo/%s" % (id))
                    rpn=rp.full_name
                except:
                    rpn="No repository found!"
                    rp = False
    #print rpn
    if rp:
        fn = rp.get_file_contents("%s_%s.txt" % (id, juan), ref=branch).decoded_content.decode('utf-8')
    else:
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
    try:
        t2 = [[(a, b[2], b[3].split()[-1]) for b in eval(toc[a])] for a in tk]
    except:
        t2 = [[(a, b[2], b[3].split()[-1]) for b in toc[a]] for a in tk]
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
    md = mandoku_view.mdDocument(fn, id, juan, ignorepb=True)
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
    return render_template('showtext.html', ct={'mtext': Markup("<br/>\n".join(md.md)),
                                                'doc': res},
                           doc=res, key=key, title=title, txtid=res['ID'], juan=juan, branches=branches, edition=branch, toc=t2, showtoc=showtoc, editurl=editurl, ed=md.ed)

@tls.route('/lexicon/quotations/<uuid>', methods=['GET',])
def showex(uuid="uuid-39b00dce-3e66-4507-834f-1ec3eb135b29"):
    l = tlsdb.lrange(swl_key + uuid, 0, -1)
    res = ""
    for b in [a.split("##") for a in l]:
        txtloc = b[0].split(":")
        it_txtid, it_juan = txtloc[0].split("_")
        it_page = txtloc[1].split('a')[0] + 'a'
        href = url_for('tls.showtext', id=it_txtid, juan=it_juan, query=txtloc[-1], _anchor=it_juan+'-'+it_page, user='tls-kr')
        res += "<li>%s (<a href='%s'>%s</a>)</li>\n" % (b[5], href, b[1])
    if len(res) == 0:
        res = "<b>No attributions registered for this syntactic word.</b>"
    return res
    
