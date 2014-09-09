#    -*- coding: utf-8 -*-
from flask import jsonify
from flask import Response, render_template, redirect, url_for, abort, flash, request,\
    current_app, make_response
from app.exceptions import ValidationError
from . import api
from .. import redis_store
from .. import lib
from datetime import datetime
import subprocess


import codecs, re
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
    try:
        for i in range(0, len(l)):
            j = i+1
            res = lib.dicentry(l[i:j], current_app.config['DICURL'])
            de.append(res)
            while res and j < len(l):
                j += 1
                res = lib.dicentry(l[i:j], current_app.config['DICURL'])
                de.append(res)
        return "\n%s" % ("".join(de))
    except:
        return "Not Found: %s " % (l)


@api.route('/search', methods=['GET', 'POST',])
def searchtext(count=20, start=None, n=20):
    key = request.values.get('query', '')
#    rep = "\n%s:" % (request.values.get('rep', 'ZB'))
    count=int(request.values.get('count', count))
    start=int(request.values.get('start', 0))
    #/Users/Shared/md/index"
    #subprocess.call(['bzgrep -H ^龍二  /Users/Shared/md/index/79/795e*.idx*'], stdout=of, shell=True )
    #ox = subprocess.check_output(['bzgrep -H ^%s  /Users/Shared/md/index/%s/%s*.idx*' % (key[1:], ("%4.4x" % (ord(key[0])))[0:2], "%4.4x" % (ord(key[0])))], shell=True )
    if len(key) > 0:
        if not redis_store.exists(key):
            lib.doftsearch(key)
    else:
        return "400 please submit searchkey as parameter 'query'."
    total = redis_store.llen(key)
    ox = redis_store.lrange(key, 1, total)
    return Response ("\n%s" % ("\n".join(ox).decode('utf-8')),  content_type="text/plain;charset=UTF-8")
#    return "\n".join(ox)
    
## file

@api.route('/getfile', methods=['GET',])
def getfile():
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    # and now:
    # http://gl.kanripo.org/ZB1a/ZB1a0118/raw/master/ZB1a0118_001.txt
    # or even
    # http://gl.kanripo.org/ZB1a/ZB1a0118/raw/WYG/ZB1a0118_001.txt
    # ==> for this we need to use the API and a TOKEN, except for public projects
    filename = request.values.get('filename', '')
    try:
        datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
        print datei
        fn = codecs.open(datei)
    except:
        return "Not found"
    return Response ("\n%s" % (fn.read(-1)),  content_type="text/plain;charset=UTF-8")

