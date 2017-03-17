#!/usr/bin/env python    -*- coding: utf-8 -*-
# import the tls to redis for mdweb
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

tls_root = "/home/chris/tlsdev/krp/tls/lexicon/"
swl_txt = tls_root + "index/swl.txt"
swl_key = "swl::"
syl_txt = tls_root + "index/syllables.txt"
syl_key = "syl::"
syn_txt = tls_root + "index/syn-func.txt"
syn_key = "syn::"
char_txt = tls_root + "core/characters.tab"
char_key = "char::"
con_dir = tls_root + "concepts/"
con_key = "con::"
zhu_dir = tls_root + "notes/zhu/"
zhu_key = "zhu::"

r.flushdb()

for line in codecs.open(swl_txt, "r", "utf-8"):
    #uuid-017e4a46-92e1-4c9a-a0c5-168e0d0ce644	KR1a0001_065:1a01:1::天尊##周易##--##--##天@tiān##天尊地卑	Heaven is exalted and Earth is humble,
    f = line[:-1].split("\t", 1)
    ff = f[1].split("##")
    res = {'loc' :  ff[0], 'title' : ff[1], 'char' : ff[4], 'line' : ff[5] }
    r.hmset(swl_key+f[0], res)

for line in codecs.open(syl_txt, "r", "utf-8"):
    #逳	uuid-ee853465-8441-4aec-8453-c00691fc312d	yù	luɡ	jiuk	余	六	入	歩也轉也行也
    f = line[:-1].split("\t")
    try:
        res = {'char' :  f[0], 'uuid' : f[1], 'pinyin' : f[2], 'oc' : f[3], 'mc' : f[4], "fq" : "%s%s切" % (f[5], f[6]),
           'diao' : f[7], 'gloss' : f[8]}
    except:
        print line
        print f
        sys.exit()
    r.hmset(syl_key+f[1], res)
    w = redis_hash_dict.RedisHashDict(syl_key+f[0])
    try:
        w['uuid'].append( f[0])
    except:
        w['uuid'] = [f[0]]
    try:
        w['pinyin'].append(f[2])
    except:
        w['pinyin'] = [f[0]]
cnt = 0    
fx = codecs.open(syn_txt, "r", "utf-8")
for line in fx.read().split("$$"):
    #uuid-2037d19a-5025-47a3-8213-544eb032a437	vt+npro.adN	transitive verb preceding its pronominal object, this whole phrase modifying a main nominal$$
    # cnt += 1
    # sys.stderr.write("cnt: %d\n" % ( cnt))
    f = line.split("\t")
    try:
        res = {'syn' :  f[1], 'uuid' : f[0], 'def' : f[2], }
    except:
        print line
        print f
        sys.exit()
    r.hmset(syn_key+f[0], res)
        
for line in codecs.open(char_txt, "r", "utf-8"):
    #4E00	一	1	0	1	1000.0
    f = line.split("\t")
    res = {'uni' : f[0], 'char' : f[1], 'rad' : f[2], 'st' : f[3], 'ts' : f[4]}
    r.hmset(char_key+f[0], res)

def read_drawer(el, d={}):
    "Reads a drawer element, returns a hash of all contents."
    for c in el.content:
        if c.name.endswith("+"):
            try:
                d[c.name].append(c.value)
            except:
                d[c.name] = [c.value]
        else:
             d[c.name] = c.value
    return d
    
def read_concept(con):
    base = PyOrgMode.OrgDataStructure()
    s = codecs.open(con, "r", "utf-8").read()
    base.load_from_string(s)
    try:
        concept = base.root.content[-1].heading.split("= ")[1]
    except:
        print base.root.content[-1].heading
        return {'concept' : 'unknown'}
    res = {'concept' : concept}
    for n in base.root.content[-1].content:
        if n.TYPE == 'DRAWER_ELEMENT':
            res = read_drawer(n, res)
        elif n.TYPE == 'NODE_ELEMENT':
            if n.heading == 'DEFINITION':
                res['def'] = "".join(n.content).strip()
            elif n.heading == 'POINTERS':
                px = {}
                for n1 in n.content:
                    if n1.TYPE == 'NODE_ELEMENT':
                        pt = n1.heading
                        px[pt] = []
                        for p in n1.content:
                            if "concept:" in p:
                                px[pt].append(re.findall("concept:([^]]+)", p)[0])
                res['pointers'] = px
            elif n.heading == 'WORDS':
                res['words'] = []
                for n1 in n.content:
                    if n1.TYPE == 'NODE_ELEMENT':
                        w = {'head' : n1.heading}
                        ws = []
                        for p in n1.content:
                            if type(p) is unicode:
                                w['sourceref'] = n1.output().strip()
                            elif p.TYPE == 'DRAWER_ELEMENT':
                                w = read_drawer(p, w)
                            elif p.TYPE == 'NODE_ELEMENT':
                                ch = {'head' : p.heading}
                                for dx in p.content:
                                    if dx.TYPE == 'DRAWER_ELEMENT':
                                        ch = read_drawer(dx, ch)
                                    if dx.TYPE == 'NODE_ELEMENT':
                                        if dx.heading == 'DEFINITION':
                                            ch['def'] = "".join(dx.content).strip()
                                        elif dx.heading == 'NOTES':
                                            ch['not'] = dx.output().strip()
                                ws.append(ch)
                        w['synwords'] = ws
                        res['words'].append(w)
    return res


ls = os.listdir(con_dir)
ls.sort()
for fx in ls:
    con = "%s%s" % (con_dir, fx)
    print fx
    res = read_concept(con)
    print res['concept']
    r.hmset(con_key+res['concept'], res)
