#    -*- coding: utf-8 -*-
from flask import Response, url_for, request, current_app, send_file
from . import api
from .. import lib


import codecs, re, os
#from . import mandoku_view

import gitlab, requests

import functools

# decorator for Mimetype handling, see https://bitbucket.org/snippets/audriusk/4ARz and https://stackoverflow.com/questions/28791613/route-requests-based-on-the-accept-header-in-flask
def accept(func_or_mimetype=None):
    """Decorator which allows to use multiple MIME type handlers for a single
    endpoint.
    """

    # Default MIME type.
    mimetype = 'text/html'

    class Accept(object):
        def __init__(self, func):
            self.default_mimetype = mimetype
            self.accept_handlers = {mimetype: func}
            functools.update_wrapper(self, func)

        def __call__(self, *args, **kwargs):
            default = self.default_mimetype
            mimetypes = request.accept_mimetypes
            best = mimetypes.best_match(self.accept_handlers.keys(), default)
            # In case of Accept: */*, choose default handler.
            if best != default and mimetypes[best] == mimetypes[default]:
                best = default
            return self.accept_handlers[best](*args, **kwargs)

        def accept(self, mimetype):
            """Register a MIME type handler."""

            def decorator(func):
                self.accept_handlers[mimetype] = func
                return func
            return decorator

    # If decorator is called without argument list, return Accept instance.
    if callable(func_or_mimetype):
        return Accept(func_or_mimetype)

    # Otherwise set new MIME type (if provided) and let Accept act as a
    # decorator.
    if func_or_mimetype is not None:
        mimetype = func_or_mimetype
    return Accept



@api.route('/index', methods=['GET',])
def index():
    print("query" in request.values)
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


@api.route('/titles', methods=['GET', 'POST',])
@accept
def searchtitle(count=20, start=0, n=20):
    mime=True
    return searchtitle_internal(mime, count, start, n)

@searchtitle.accept('application/json')
def searchtitle_json(count=20, start=0, n=20):
    mime='application/json'
    print("returning JSON")
    return searchtitle_internal(mime, count, start, n)
    
def searchtitle_internal(mime, count=20, start=0, n=20, force=False):
    titpref = "kr:title:"
    count=int(request.values.get('count', count))
    start=int(request.values.get('start', start))
    key = request.values.get('query', '')
    if len(key) > 0:
        if (not redis_store.exists(titpref+key)) or force:
            lib.dotitlesearch(titpref, key)
    total = redis_store.llen(titpref+key)
    print (total)
    tits = redis_store.lrange(titpref+key, start, start+count)
    if mime == 'application/json':
        out = [{"textid": k.split()[0],
                "title" : k.split()[1].split("-")[0],
                "dynasty" : k.split()[1].split("-")[1],
                "responsible" : k.split()[1].split("-")[2],
        } for k in tits]
        return jsonify({"query" : key, "total": total, "start": start, "count" : len(out), "matches" : out})
    else:
        return Response("\n".join(tits))


# for the moment, we are just dumping out all matches
@api.route('/search', methods=['GET', 'POST',])
@accept
def searchtext(count=20, start=None, n=20):
    mime=True
    return searchtext_internal(mime, count, start, n)

@searchtext.accept('application/json')
def searchtext_json(count=20, start=None, n=20):
    mime='application/json'
    print("returning JSON")
    return searchtext_internal(mime, count, start, n)
    
def searchtext_internal(mime, count=20, start=None, n=20):
    zbmeta = "kr:meta:"
    key = request.values.get('query', '')
    count = int(request.values.get('count', count))
    start = int(request.values.get('start', 0))
    if not key:
        return "400 please submit searchkey as parameter 'query'."
    rows, total = lib.doftsearch(key, offset=start, limit=count)
    body = "\n".join(f"{content}\t{location}" for (content, location, _) in rows)
    return Response("\n%s" % body, content_type="text/plain;charset=UTF-8")

def proc_loc(location):
    """prepare location for json"""
    if "$" in location:
        lt, pos = location.split("$")
    else:
        pos = "0"
    l = lt.split(":")
    return {"position" : pos, "fn" : l[0], "juan" : l[0].split("_")[-1], "page" : l[1], "line" : l[2], "char" : l[3]}
    
def proc_meta(meta):
    """Process the metadata returned from redis to the format required for returning"""
    retd = {}
    if ("RESP" in meta):
        retd.update({"resp" : meta["RESP"]})
    else:
        retd.update({"resp" : ""})
    if ("TPUR" in meta):
        retd.update({"title" : meta["TPUR"]})
    else:
        retd.update({"title" : ""})
    if ("DYNASTY" in meta):
        retd.update({"dynasty" : meta["DYNASTY"]})
    else:
        retd.update({"dynasty" : ""})
    return retd

def addtitles(ox, key, var, zbmeta):
    ox = [("".join([k.split("\t")[0].split(',')[1],key[0], k.split("\t")[0].split(',')[0]]), redis_store.hgetall(u"%s%s" %( zbmeta, k.split('\t')[1].split(':')[0][0:8])), "\t".join(k.split("\t")[1:])) for k in ox]
    out = []
    for k in ox:
        l = list(k)
        if l[1].has_key('TITLE'):
            l[1] = l[1]['TITLE']
        else:
            l[1] = 'no title'
        l2 = l[2].split(":")
        if var:
            v=[a for a in l2[-1].split("\t")[1:] if (a != 'n')]
            # arbitrarily we select the edition with the shortest sigle, but not including @
            try:
                v=min([a for a in v[0].split() if not '@' in a], key=len)
            except:
                v='master'
            l[2] = "https://raw.githubusercontent.com/kanripo/%s/%s/%s.txt\t%s" % (l2[0][0:8], v, l2[0], ":".join(l2[1:]))
        else:
            l[2] = "https://raw.githubusercontent.com/kanripo/%s/master/%s.txt\t%s" % (l2[0][0:8], l2[0], ":".join(l2[1:]))
        l="\t".join(l)
        #l=re.sub(r"<img[^>]*>", u"●", l)
        l=l.split("\t")
        # we ignore other editions!
        if len(l) == 4 or l[-1] == "n":
            out.append("\t".join(l))
    return out
    
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
        print(datei)
        fn = open(datei, encoding='utf-8')
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
        return send_file(datei, mimetype='image/%s' % (mtype), download_name=filename)
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
        print(url)
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
