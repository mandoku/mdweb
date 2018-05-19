#    -*- coding: utf-8 -*-
from flask import jsonify
from flask import Response, render_template, redirect, url_for, abort, flash, request,\
    current_app, make_response, send_file
from app.exceptions import ValidationError
from . import api
from .. import redis_store
from .. import lib


import codecs, re, os
#from . import mandoku_view

import gitlab, requests


@api.route('/index', methods=['GET',])
def index():
    print request.values.has_key("query")
    return "INDEX"


@api.route('/procline', methods=['GET',])
def procline():
    l = request.values.get('query', '')
    l = lib.md_re.sub("", l)
    de = []
    for i in range(0, len(l)):
        j = i+1
        try:
            res = lib.dicentry(l[i:j], current_app.config['DICURL'])
        except:
            res = ""
        de.append(res)
        while res and j < len(l):
            j += 1
            try:
                res = lib.dicentry(l[i:j], current_app.config['DICURL'])
            except:
                res = ""
            de.append(res)
    return "\n%s" % ("".join(de))
    # except:
    #     return "Not Found: %s " % (l)

# for the moment, we are just dumping out all matches
@api.route('/search', methods=['GET', 'POST',])
def searchtext(count=20, start=None, n=20):
    zbmeta = "kr:meta:"
    key = request.values.get('query', '')
    force = request.values.has_key("force")
    titles = request.values.has_key('with-titles')
    ready = request.values.has_key('kwic-ready')
    link = request.values.has_key('with-link')
    if request.values.has_key("start"):
        start=int(request.values.get('start', 0))
    if request.values.has_key("count"):
        count=int(request.values.get('count', count))
        if not start:
            start = 0
    else:
        count = None
    if len(key) > 0:
        if (not redis_store.exists(key)) or force:
            lib.doftsearch(key)
    else:
        return Response("""400 please submit searchkey as parameter 'query'.
Other parameters are:
  'force‘： This parameter, set to any value, will force a rerun of the search, by passing the cache.
  'count':  (integer) Number of items to transmit.
  'start':  (integer) Position of first item to transmit.
  'with-titles': This parameter, if present, will cause the results to include the titles in a tab-separated text format, this also implies 'kwic-ready'.
  'kwic-ready' : This parameter, if present, will cause the keyword in context format to be formated to be directly usable.
""",  content_type="text/plain;charset=UTF-8")
    total = redis_store.llen(key)
    ox = redis_store.lrange(key, 1, total)
    if titles:
        ox = [("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), redis_store.hgetall(u"%s%s" %( zbmeta, k.split('\t')[1].split(':')[0][0:8])), "\t".join(k.split("\t")[1:])) for k in ox]
        out = []
        for k in ox:
            l = list(k)
            if l[1].has_key('TITLE'):
                l[1] = l[1]['TITLE']
            else:
                l[1] = 'no title'
            l2 = l[2].split(":")
            l[2] = "https://raw.githubusercontent.com/kanripo/%s/master/%s.txt\t%s" % (l2[0][0:8], l2[0], l2[1])
            l="\t".join(l)
            l=re.sub(r"<img[^>]*>", u"●", l)
            l=l.split("\t")
            if len(l) == 4 or l[-1] == "n":
                out.append("\t".join(l))
        ox=out
    elif ready:
        ox = ["\t".join(("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), k.split('\t')[1])) for k in ox]
    if count:
        if count > len(ox):
            count = len(ox)
        ox = ox[start:count+1]
    return Response ("\n%s" % ("\n".join(ox).decode('utf-8')),  content_type="text/plain;charset=UTF-8")

    
## file

@api.route('/getfile', methods=['GET',])
def getfile():
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    # and now:
    # http://gl.kanripo.org/ZB1a/ZB1a0118/raw/master/ZB1a0118_001.txt
    # or even
    # http://gl.kanripo.org/ZB1a/ZB1a0118/raw/WYG/ZB1a0118_001.txt
    # ==> for this we need to use the API and a TOKEN, except for public projects
    # https://raw.githubusercontent.com/kanripo/KR5a0328/master/KR5a0328_002.txt
    filename = request.values.get('filename', '')
    try:
        datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
        fn = codecs.open(datei)
    except:
        try:
            datei="%s/%s/Readme.org" % (current_app.config['TXTDIR'],"/".join(filename.split("/")[:-1]))
            fn = codecs.open(datei)
        except:
            return "Not found"
    return Response ("\n%s" % (fn.read(-1)),  content_type="text/plain;charset=UTF-8")

@api.route('/dic', methods=['GET',])
def searchdic():
    key = request.values.get('query', '')
    return lib.dicentry(key, current_app.config['DICURL'])

@api.route('/dicpage/<dic>/<page>', methods=['GET',])
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

## images
@api.route('/getimage', methods=['GET',])
def getimage():
    filename = request.values.get('filename', '')
    datei = "%s/%s" % (current_app.config['IMGDIR'], filename)
    mtype = filename[-3:]
    try:
        return send_file(datei, mimetype='image/%s' % (mtype), attachment_filename=filename)
    except:
        return "404 Not found"
#    return Response ("\n%s" % (fn.read(-1)),  content_type="image/%s" % (mtype))
@api.route('/getimgdata', methods=['GET',])
def getimgdata():
    filename = request.values.get('filename', '')
    type = request.values.get('type', 'imglist')
    ghlink = "https://raw.githubusercontent.com/kanripo/"
    local = "%s/%s/%s" % (current_app.config['TXTDIR'], filename[0:4], filename)
    mtype = filename[-3:]
    if os.path.isfile(local):
        fd=codecs.open(local, 'r', 'utf-8')
        return Response ("%s" % (fd.read(-1)),  content_type="text/%s" % (mtype))
    else:
        url="%s%s" % (ghlink, filename)
        print url
        try:
            r = requests.get(url)
        except:
            return Response ("%s" % ("\tres\tNo facsimile available"),  content_type="text/%s" % (mtype))
        if r.status_code == 200:
            return Response ("%s" % (r.content),  content_type="text/%s" % (mtype))
        else:
            return Response ("%s" % ("\tres\tNo facsimile available"),  content_type="text/%s" % (mtype))
        

## github api: get branches
## GET /repos/:owner/:repo/branches
# [
#   {
#     "name": "master",
#     "commit": {
#       "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
#       "url": "https://api.github.com/repos/octocat/Hello-World/commits/c5b97d5ae6c19d5c5df71a34c7fbeeda2479ccbc"
#     }
#   }
# ]
# this is for【大→原】
# https://raw.githubusercontent.com/kanripo/KR6q0003/%E3%80%90%E5%A4%A7%E2%86%92%E5%8E%9F%E3%80%91/KR6q0003_005.txt
