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
    key = request.values.get('query', '')
    force = request.values.get('force', None)
    count=int(request.values.get('count', count))
    start=int(request.values.get('start', 0))
    if len(key) > 0:
        if (not redis_store.exists(key)) or force:
            lib.doftsearch(key)
    else:
        return "400 please submit searchkey as parameter 'query'."
    total = redis_store.llen(key)
    ox = redis_store.lrange(key, 1, total)
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
