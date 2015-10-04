#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re, git, codecs, os
from jinja2 import Markup
# re.M is multiline

config_parser_re=re.compile(r"#\+(.*): (.*)", re.M) 
hd = re.compile(r"^(\*+) (.*)$")
vs = re.compile(r"^#\+([^_]+)_V")
gaiji = re.compile(r"(&[^;]+;)")
pb = re.compile(r"<pb:([^_]+)_([^_]+)_([^-]+)-([^>]+)>")
pby = re.compile(r"<pb:YP-C_([^_]+)_([^-]+)-([^>]+)>")
pbx = re.compile(r"<pb:([^_]+)_([^_]+)_([^p]+)p([^>]+)>")
# <pb:KR5a0174_CK-KZ_02p002a>

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
        self._toc=[]
        s = ["<p>"]
        o = ""
        lines = content.split('\n')
        for l in lines:
            cnt += 1
            l = l.replace('¶', '')
            l = re.sub(r'@[a-z]+', '', l)
            if pby.search(l):
                l = pby.sub(r'''<a onclick="displayPageImage('%s', 'JY-C', '%s', '\2-\3' );" name="\2-\3" class="pb">[\2-\3]</a>''' % (self.txtid, self.juan), l)
            elif pb.search(l):
                l = pb.sub(r'''<a onclick="displayPageImage('\1', '\2', '\3', '\4' );" name="\4" class="pb">[\3-\4]</a>''', l)
            elif pbx.search(l):
                l = pbx.sub(r'''<a onclick="displayPageImage('%s', '\2', '%s', '\3p\4' );" name="\4" class="pb">[\3-\4]</a>''' % (self.txtid, self.juan), l)
            if vs.search(l):
                tmp = vs.findall(l)[0]
                if tmp.upper() == "BEGIN":
                    vs_flag = 1
                else:
                    vs_flag = 0
            elif l.startswith('#'): continue
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
                o = gaiji.sub(u"⬤", l)
            s.append(o)
        s.append("</p>")
        return s
    
