#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re, git, codecs, os
from jinja2 import Markup
# re.M is multiline

config_parser_re=re.compile(r"#\+(.*): (.*)", re.M) 
hd = re.compile(r"^(\*+) (.*)$")
vs = re.compile(r"^#\+([^_]+)_V")
gaiji = re.compile(r"&([^;]+);")
pb = re.compile(r"<pb:([^_]+)_([^_]+)_([^>]+)>")
pby = re.compile(r"<pb:YP-C_([^_]+)_([^-]+)-([^>]+)>")
# <pb:CK-KZ_KR5i0011_01p001a>¶
pbk = re.compile(r"<pb:CK-KZ_([^_]+)_([^>]+)>")
pbx = re.compile(r"<pb:([^_]+)_([^_]+)_([^p]+)p([^>]+)>")
# <pb:KR5a0174_CK-KZ_02p002a>
imgbase = "<img height='20' width='20' alt='&amp;{gaiji}' title='{gaiji}' src='https://raw.githubusercontent.com/kanripo/KR-Gaiji/master/images/{gaiji}.png'/>"
class mdDocument(object):
    def __init__(self, fn, txtid, juan, rep=None):
        self.raw = fn
        # the repository to which this file belongs
        self.txtid = txtid
        self.juan = juan
        self.rep = rep
        if rep:
            repo = git.Repo(self.rep)
        self._config = None
        self._md = None
        self._toc = None
        self._ed = None
    
    @property
    def ed(self):
        if not isinstance(self._md, list):
            self._md = self.parse(self.raw)
        return self._ed
    @property
    def config(self):
        if not isinstance(self._config, dict):
            self._config = {}
            for m in config_parser_re.finditer(self.raw):
                if m.group(1) == "PROPERTY":
                    m1 = m.group(2).split(' ', 1)
                    self._config[m1[0]] = m1[1]
                else:
                    self._config[m.group(1)] = m.group(2)
        if not self._config.has_key('ID'):
            self._config['ID'] = self.txtid
        return self._config

    @property
    def md(self):
        if not isinstance(self._md, list):
            self._md = self.parse(self.raw)
        return self._md

    @property
    def toc(self):
        if not isinstance(self._md, list):
            self._md = self.parse(self.raw)
        return self._toc
    
    @property
    def title(self):
        return Markup(self.config['TITLE']).striptags()

    @property
    def body(self):
        return Markup("".join(self.md))

    def __repr__(self):
        return "<mdDocument %s>" % (self.title)

    def parse(self, content):
        vs_flag = 0
        cnt = 0
        llen = 0
        self._toc=[]
        s = ["<p>"]
        o = ""
        lines = content.split('\n')
        for l in lines:
            oldlen = llen
            llen += len(l) + 1
            cnt += 1
            l = l.replace('¶', '')
            l = re.sub(r'@[a-z]+', '', l)
            l = l.replace("(", "<span class='krp-note'>")
            l = l.replace(")", "</span>")
            if l.startswith('#'): continue
            if not self._ed and "<pb" in l:
                self._ed = re.findall(r"<pb[^_]+_([^_]+)_", l)[0]
            if pby.search(l):
                l = pby.sub(r'''<a onclick="displayPageImage('%s', 'YP-C', '\2-\3' );" name="\2-\3" class="pb">[\2-\3] <img width="20"  src="/static/img/kanseki-5.png"/></a>''' % (self.txtid), l)
            if pbk.search(l):
                l = pbk.sub(r'''<a onclick="displayPageImage('%s', 'CK-KZ', '\2' );" name="\1-\2" class="pb">[\2] <img width="20"  src="/static/img/kanseki-5.png"/></a>''' % (self.txtid), l)
            elif pb.search(l):
                l = pb.sub(r'''<a onclick="displayPageImage('\1', '\2', '\3' );" name="\3" class="pb">[\3] <img width="20"  src="/static/img/kanseki-5.png"/></a>''', l)
            elif pbx.search(l):
                l = pbx.sub(r'''<a onclick="displayPageImage('%s', '\2', '%s-\3p\4' );" name="\4" class="pb">[\3-\4] <img width="20"  src="/static/img/kanseki-5.png"/></a>''' % (self.txtid, self.juan), l)
            if vs.search(l):
                tmp = vs.findall(l)[0]
                if tmp.upper() == "BEGIN":
                    vs_flag = 1
                else:
                    vs_flag = 0
            elif l.startswith(':'): continue
            elif hd.search(l):
#                print l
                tmp = hd.findall(l)[0]
                lev = len(tmp[0])
                self._toc.append( (lev, '<li><a name="#%s-%d">%s</a></li>' % (self.config['ID'], cnt, tmp[1]))) 
                o = '</p>\n<h%d><a name="%s-%d">%s</a></h%d>\n<p>' % (lev, self.config['ID'], cnt, tmp[1], lev)
            elif len(l) == 0:
                o = "</p>\n<p>"
            elif vs_flag == 1:
                o = "%s<br/>" % (l)
            else:
                o = gaiji.sub(lambda x : imgbase.format(gaiji=x.group(1)), l)
                o = "<span class='tline' id='l%d' data-llen='%d:%d'>%s</span>" % (cnt, oldlen, llen, o)
                o = o.replace("\t", "</span><span class='tline_right'>")
                #o = gaiji.sub(u"⬤", l)
            #this is for the links in readme files.. we are in the same folder, so do not need the ID
            o=re.sub(r"\[\[file:([^_]+)[^:]+::([^-]+)-([^]]+)\]\[([^]]+)\]\]", "<a href='\\2#\\3'>\\4</a>", o)
            o=re.sub(r"\[\[file:([^_]+)_([^\.]+)\.([^]]+)\]\[([^]]+)\]\]", "<a href='\\2'>\\4</a>", o)
            if o.strip()==u"目次":
                o = "<h1>%s</h1>" % (o)
            lx = o.strip().split("|")
            if len(lx) == 4:
                o = "<p><a href='/edition/%s/%s/'>%s</a></p>" % (lx[1].strip(), self.config['ID'], lx[2].strip())
            s.append(o)
        s.append("</p>")
        return s
    
