#!/usr/bin/env python    -*- coding: utf-8 -*-
# add the characters from the taxonomy file.
import sys, os, codecs, datetime, git, re, redis
from collections import defaultdict
from PyOrgMode import PyOrgMode
reload(sys)
sys.setdefaultencoding('utf-8')

db=3
CLIENT = redis.Redis(host='localhost', port=6379, db=db, charset='utf-8', errors='strict')
r=CLIENT
sys.path.insert(0, '/Users/chris/work/py')
import redis_hash_dict

## TLS settings

tls_root = "/Users/chris/tlsdev/krp/tls/lexicon/"
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
ft_key = "ft::"
uuid_key= "uuid:"
tax_key = "tax::"
concepts = {}
def parseline(l):
    """Extract information from a typical line"""
    pass

def addlink(l, urlbase=""):
    """All capital expressions are considered a concept worth linking
to. When found, also add to concepts hash."""
    cp = []
    for h in l.split():
        if len(cp) > 0 and h.isupper() and cp[-1].isupper():
            cp[-1] = cp[-1] + " " + h
        else:
            cp.append(h)
    for i, c in enumerate(cp):
        if c.isupper():
            # maybe check to see if this is existing?
            if r.exists(con_key + c):
                cp[i] = "<a href='%s%s'>%s</a>" % (urlbase, c, c)
            else:
                cp[i] = "<a style='color:red;' href='%s%s'>%s</a>" % (urlbase, c, c)
    return " ".join(cp)

bu = "http://tls.kanripo.org/tls/concept?id="
txf = "/home/chris/Dropbox-gmail/Dropbox/TLS/krp/tls/work/taxonomy-2017-02-20.txt"
curr = ""
ol = []
for line in codecs.open(txf, "r", "utf-8"):
    if line.startswith ("* "):
        if len(curr) > 0:
            r.hmset(tax_key + curr, {"tax" : "<h2>%s</h2>\n<div>%s</div>" % (curr, "".join(ol))})
            ol = []
        curr = line[1:-1].strip()
        oldlev = 1
    elif len(curr) > 0:
        if line.startswith("*"):
            lev, rest = line.split(" ", 1)
            if len(lev) > 2:
                s1 = "%s%s%s\n" % ("　" * len(lev), addlink(rest, bu), "<br/>")
            else:
                if ") " in rest:
                    r1, r2 = rest.split(") ", 1)
                else:
                    r1 = rest
                    r2 = ""
                s1 = "<h3>%s)</h3>\n<p>%s</p>\n" % (r1, r2)
            ol.append(s1)

