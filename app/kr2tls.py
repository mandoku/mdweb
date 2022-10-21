# -*- coding: utf-8 -*-
# KR to TEI format.
#
import re, os, sys, requests, datetime
from github import Github
#from dotenv import load_dotenv
#load_dotenv()

puamagic = 1069056
scriptpath = os.path.dirname(os.path.abspath(__file__))
envpath = "%s/%s" % (scriptpath, ".env") 
if os.path.exists(envpath):
    print('Importing environment from .env...')
    for line in open(envpath):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

at=os.environ.get('at')
lang="zho"
# template for xml
# need the following vars:
# user, txtid, title, date, branch, today, body, lang
# body should contain the preformatted content for the body element
tei_template="""<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml"
	schematypens="http://purl.oclc.org/dsdl/schematron"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="{btxtid}">
  <teiHeader>
      <fileDesc>
         <titleStmt>
            <title>{title}</title>
         </titleStmt>
         <publicationStmt>
            <p>Published by @kanripo on GitHub.com</p>
         </publicationStmt>
         <sourceDesc>
            <p>{branch}</p>
         </sourceDesc>
      </fileDesc>
     <revisionDesc>
        <change resp="#chris"><p>Converted to TEI format for TLS on <date>{today}</date>.</p></change>
     </revisionDesc>
  </teiHeader>
      {sd}
</TEI>
"""

def get_property(p_in):
    p = p_in[2:]
    pp = p.split(": ")
    if pp[0] in ["DATE", "TITLE"]:
        return (pp[0], pp[1])
    elif pp[0] == "PROPERTY":
        p1 = pp[1].split()
        return (p1[0], " ".join(p1[1:]))
    return "Bad property: %s" % (p_in)

def combine_note(lines):
    for i, l in enumerate(lines):
        if l.endswith("</note>\n"):
            if i < len(l):
                if lines[i+1].startswith("<note>"):
                    lines[i] = l.replace("</note>\n", "\n")
                    lines[i+1] = lines[i+1][6:]
    return lines

# loop through the lines and return a dictionary of metadata and text content
# gjd is the dictionary to hold gaiji encountered, md is wether we want to care about <md: style tags.
# here we parse the text into paragraphs, instead of surface elements
def parse_text_to_p(lines, gjd, md=False):
    lx={'TEXT' : []}
    lcnt=0
    nl=[]
    np=[]
    pbxmlid=""
    for l in lines:
        #l=re.sub("¶", "<lb/>", l)
        lcnt += 1
        if l.startswith("#+"):
            p = get_property(l)
            lx[p[0]] = p[1]
            continue
        elif l.startswith("#"):
            continue
        elif "<pb:" in l:
            pbxmlid=re.sub("<pb:([^_]+)_([^_]+)_([^>]+)>", "\\1_\\2_\\3", l)
            l=re.sub("<pb:([^_]+)_([^_]+)_([^>]+)>", "<pb ed='\\2' n='\\3' xml:id='\\1_\\2_\\3'/>", l)
            lcnt = 0
        if "<md:" in l:
            l=re.sub("<md:([^_]+)_([^_]+)_([^>]+)>", "<pb ed='\\2' n='\\3' xml:id='\\1_\\2_\\3'/>", l)
        if "&KR" in l:
            # only for the sideeffect
            re.sub("&KR([^;]+);", lambda x : gjd.update({"KR%s" % (x.group(1)) : "%c" % (int(x.group(1)) + puamagic)}), l)
        l = re.sub("&KR([^;]+);", lambda x : "%c" % (int(x.group(1)) + puamagic ), l)
        # if md:
        #     pass
        #     #l=re.sub("¶", f"<!-- ¶ -->", l)
        # else:
        l = l.replace("(", "<note>")
        l = l.replace(")¶", "¶</note>")
        l = l.replace(")", "</note>")
  #      l=re.sub("¶", "<lb/>", l)
        if not re.match("^</p>", l) and len(l) > 0:
            l="%s\n" % (l)
        if l == "":
            nl=combine_note(nl)
            np.append(nl)
            nl=[]
        else:
            if md:
                l=l+"\n"
        nl.append(l)
    nl=combine_note(nl)
    np.append(nl)
    lx['TEXT'] = np
    return lx

# loop through the lines and return a dictionary of metadata and text content
# gjd is the dictionary to hold gaiji encountered, md is wether we want to care about <md: style tags.
# 
def parse_text(lines, gjd, md=False):
    lx={'TEXT' : []}
    lcnt=0
    nl=[]
    np=[]
    pbxmlid=""
    for l in lines:
        l=re.sub("¶", "", l)
        lcnt += 1
        if l.startswith("#+"):
            p = get_property(l)
            lx[p[0]] = p[1]
            continue
        elif l.startswith("#"):
            continue
        elif "<pb:" in l:            
            np.append(nl)
            nl=[]
            pbxmlid=re.sub("<pb:([^_]+)_([^_]+)_([^>]+)>", "\\1_\\2_\\3", l)
            l=re.sub("<pb:([^_]+)_([^_]+)_([^>]+)>", "</surface>\n<surface xml:id='\\1_\\2_\\3-z'>\n<pb ed='\\2' n='\\3' xml:id='\\1_\\2_\\3'/>", l)
#            l=re.sub("<pb:([^_]+)_([^_]+)_([^>]+)>", "</div></div><div type='p' n='\\3'><div type='l' n='x'>", l)
            lcnt = 0
        if "<md:" in l:
            l=re.sub("<md:([^_]+)_([^_]+)_([^>]+)>", "<!-- md: \\1-\\2-\\3-->", l)
        #l = re.sub("&([^;]+);", "<g ref='#\\1'/>", l)
        if "&KR" in l:
            # only for the sideeffect
            re.sub("&KR([^;]+);", lambda x : gjd.update({"KR%s" % (x.group(1)) : "%c" % (int(x.group(1)) + puamagic)}), l)
        l = re.sub("&KR([^;]+);", lambda x : "%c" % (int(x.group(1)) + puamagic ), l)
        # if md:
        #     pass
        #     #l=re.sub("¶", f"<!-- ¶ -->", l)
        # else:
        l = l.replace("(", "<note>")
        l = l.replace(")¶", "¶</note>")
        l = l.replace(")", "</note>")
        if not re.match("^</surface>", l) and len(l) > 0:
            sp=re.match("^　+", l)
            if sp:
                rend=" rend='space:%d'" % (sp.span()[1])
            else:
                rend=""
            l="<line xml:id='%s.%2.2d'%s>%s</line>\n" % (pbxmlid, lcnt, rend, l)
            #l=re.sub("¶", f"\n<lb n='{lcnt}'/>", l)
        # if l == "":
        #     np.append(nl)
        #     nl=[]
        # else:
        # if md:
        #     l=l+"\n"
        l = l.replace("KR", "KR")
        nl.append(l)
    np.append(nl)
    lx['TEXT'] = np
    return lx

def save_text_part(lx, txtid, branch, path, format):
    # do we need to change the ID?  At least for textformat, we just keep it as it was.
    if format=='xml':
        path = path.replace("KR", "KR")
        ntxtid = txtid.replace("KR", "KR")
    else:
        ntxtid = txtid
    if re.match("^[A-Z-@]+$", branch):
        bt = "/doc/"
    else:
        bt = "/int/"
    try:
        os.makedirs(ntxtid + bt + ntxtid + "_" + branch)
    except:
        pass
    if format=='xml':
        fname = "%s%s%s_%s/%s.xml" % (ntxtid, bt, ntxtid, branch, path[:-4])
    else:
        fname = "%s%s%s_%s/%s" % (ntxtid, bt, ntxtid, branch, path)

    of=open(fname, "w")
    if format == 'xml':
        localid=path[:-4].split("_")
        localid.insert(1, branch)
        lid = "_".join(localid)
        lid=lid.replace("KR", "KR")
        if bt == "/int/":
            of.write("<div xmlns='http://www.tei-c.org/ns/1.0'><p xml:id='%s'>" % (lid))
        else:
            of.write("<surfaceGrp xmlns='http://www.tei-c.org/ns/1.0' xml:id='%s'>\n<surface type='dummy'>" % (lid))
        for page in lx["TEXT"]:
            for line in page:
                line = line.replace("KR", "KR")
                of.write(line)

        if bt == "/int/":
            of.write("</p></div>\n")
        else:
            of.write("</surface>\n</surfaceGrp>\n")
    else:
        for l in lx:
            # replace gaiji with PUA -- since this is the standard KR procedure, we do not record the list here?!
            # re.sub("&KR([^;]+);", lambda x : gjd.update({"KR%s" % (x.group(1)) : "%c" % (int(x.group(1)) + puamagic)}), l)
            l = re.sub("&KR([^;]+);", lambda x : "%c" % (int(x.group(1)) + puamagic ), l)
            of.write("%s\n" % (l))

def save_gjd (txtid, branch, gjd, type="entity"):
    os.makedirs(txtid+"/aux/map", exist_ok=True)
    if (type=="entity"):
        fname = "%s/aux/map/%s_%s-entity-map.xml" % (txtid, txtid, branch)
    else:
        fname = "%s/aux/map/%s_%s-entity-g.xml" % (txtid, txtid, branch)        
    of=open(fname, "w")
    of.write("""<?xml version="1.0" encoding="UTF-8"?>
<stylesheet xmlns="http://www.w3.org/1999/XSL/Transform" version="2.0">
<character-map  name="krx-map">\n""")
    of.write("""  <xsl:output-character character="¶" string="&lt;lb/&gt;"/>""")
    k = [a for a in  gjd.keys()]
    k.sort()
    for kr in k:
        if (type=="entity"):
            of.write("""<output-character character="%s" string="&amp;%s;"/>\n""" % (gjd[kr], kr))
        else:
            of.write("""<output-character character="%s" string="&lt;g ref=&#34;%s&#34;/&gt;"/>\n""" % (gjd[kr], kr))
    of.write("""</character-map>\n</stylesheet>\n""")
    of.close()
    
def test(txtid):
    return at


def convert_text(txtid, user='kanripo', format='xml'):
    gh=Github(at)
    hs=gh.get_repo("%s/%s" % (user, txtid))
    #get the branches
    # only work with master for now
    branches=[a.name for a in hs.get_branches() if a.name.startswith("master")]
    res=[]
    for branch in branches:
        if re.match("^[A-Z-]+$", branch):
            bt = "/doc/"
        else:
            bt = "/int/"
        flist = [a.path for a in hs.get_contents("/", ref=branch)]
        print (branch, len(flist))
        pdic = {}
        md = False
        xi=[]
        gjd = {}
        of=[]
        for path in flist:
            # in case of txt, get readme as well!
            if path.startswith(txtid):
                r=requests.get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (user, txtid, branch, path))
                if r.status_code == 200:
                    cont=r.content.decode(r.encoding)
                    if "<md:" in cont:
                        md = True
                    lines=cont.split("\n")
                    lx = parse_text_to_p(lines, gjd, md)
                    localid=path[:-4].split("_")
                    localid.insert(1, branch)
                    lid = "_".join(localid)
                    lid=lid.replace("KR", "KR")
                    of.append("<div xmlns='http://www.tei-c.org/ns/1.0'><p xml:id='%s'>" % (lid))
                    for page in lx["TEXT"]:
                        for line in page:
                            line = line.replace("KR", "KR")
                            of.append(line)
                    of.append("</p></div>\n")
                    pdic[path] = lx
                else:
                    return "No valid content found."



        date=datetime.datetime.now()
        today=date
        sd="".join(of)
        if format=='xml':
            ntxtid = txtid.replace("KR", "KR")
            #os.makedirs(ntxtid+ bt + ntxtid + "_" + branch, exist_ok=True)
            #save_gjd (ntxtid, branch, gjd, "entity")
            #save_gjd (ntxtid, branch, gjd, "g")
            fname = "%s.xml" % (ntxtid)
            if branch == 'master':
                btxtid = ntxtid
            else:
                btxtid = "%s_%s" % (ntxtid, branch)
            out=tei_template.format(sd="<text><body>\n%s</body></text>" % (sd), today=today, user=user, btxtid=btxtid, title=lx['TITLE'], date=lx['DATE'], branch=branch)
            return out
        else:
            pass
        
if __name__ == '__main__':

    try:
        txtid=sys.argv[1]
    except:
        print ("Textid should be given as argument.")
        sys.exit()
    # xml, that is, tei is the default (sic), but txt , i.e. mandoku is also possible
    try:
        format=sys.argv[2]
    except:
        format='xml'
    if format == 'xml':
        ntxtid = txtid.replace("KR", "KR")
    else:
        ntxtid = txtid
    os.makedirs(ntxtid+"/aux/map", exist_ok=True)
    os.makedirs(ntxtid+"/doc", exist_ok=True)
    os.makedirs(ntxtid+"/int", exist_ok=True)

    convert_text(txtid)
