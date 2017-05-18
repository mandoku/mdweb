#!/usr/bin/env python    -*- coding: utf-8 -*-
# add keys for fulltext search.  Run this after tls2redis and tax2redis
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

# first delete the old keys
for k in r.keys(ft_key+"*"):
    r.delete(k)
# all ft_keys contains lists, with elements of the form type@key
# type is con, csyn, czh, coch def, sw, etc, key is the key used to retrieve the item
for k in r.keys(con_key+"*"):
    target = k.split("::")[-1]
    r.rpush(ft_key + target, "con@" + k)
    cp = r.hgetall(k)
    try:
        zh=cp['TR_ZH']
        r.rpush(ft_key + zh, "czh@" + k)
    except:
        pass
    try:
        zh=cp['TR_OCH']
        r.rpush(ft_key + zh, "coch@" + k)
    except:
        pass
    for d in [a for a in cp['def'].split() if a.isupper()]:
        r.rpush(ft_key + d, "def@" + k)
    if cp.has_key('SYNONYM+'):
        for sn in eval(cp['SYNONYM+']):
            r.rpush(ft_key + sn, "csyn@" + k)
    for w in eval(cp['words']):
        if w.has_key('head'):
            ch=w['head'].split(" / ")
            uuid = w['CUSTOM_ID']
            for c in ch:
                try:
                    cc = c.split()[0]
                    r.rpush(ft_key + cc, "sw=%s@%s" % (uuid, k))
                except:
                    print cc, c, target

            
for k in r.keys(funx["syn-func"]+"*"):
    sf=r.hgetall(k)
    pt = eval(sf['pointers'])
    syn = sf['syn']
    dex = sf['def']
    r.rpush(ft_key + "" + syn, "synf@" + k)
    for d in dex.split():
        r.rpush(ft_key + "" + d, "synd@%s@%s" % (syn,  k))
    # here we add reverse pointers to make it easier to traverse the tree
    for p in pt:
        mp=p[0]
        res = r.hgetall(funx["syn-func"]+mp)
        for a in res.keys():
            try:
                res[a] = eval(res[a])
            except:
                pass
        res['uplink'] = [k, syn]
        r.hmset(funx["syn-func"]+mp, res)
