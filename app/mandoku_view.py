#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re, git
from jinja2 import Markup
# re.M is multiline

config_parser_re=re.compile(r"#\+(.*): (.*)", re.M) 
hd = re.compile(r"^(\*+) (.*)$")
vs = re.compile(r"^#\+([^_]+)_V")
gaiji = re.compile(r"(&[^;]+;)")
pb = re.compile(r"<pb:([^_]+)_([^_]+)_([^-]+)-([^>]+)>")


class mdDocument(object):
    def __init__(self, content, rep=None):
        self.raw = content
        # the repository to which this file belongs
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
            if pb.search(l):
                l = pb.sub(r'''<a onclick="alert('clicked');" name="\4" class="pb">[\3-\4]</a>''', l)
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
    
