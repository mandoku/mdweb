#    -*- coding: utf-8 -*-
import os, sys, redis, codecs
reload(sys)
sys.setdefaultencoding('utf-8')

db=5
r = redis.Redis(host='localhost', port=6379, db=db, charset='utf-8', errors='strict')



cbf="/Users/chris/projects/mandoku/lisp/mandoku-cbeta.el"
rflag = False
vol=""
tpref="taisho:"
for line in codecs.open(cbf, "r", "utf-8"):
    if 'subcoll "T"' in line:
        rflag = True
    elif 'subcoll' in line:
        rflag = False
    if rflag:
        if "vol" in line:
            vol="T"+line.split()[-1].replace(")", "")
        elif "page" in line:
            tmp=line.replace(")", "").split()
            p = tmp[-2][0:4]
            sec = chr(int(tmp[-2][4:5])+96)
            l = tmp[-2][5:7]
            fn = tmp[-1].replace('"', '')[:-4]
            r.zadd(tpref+vol, fn, int(tmp[-2]))
