#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
from flask import Response, render_template, redirect, url_for, abort, flash, request,\
    current_app, make_response
from flask.ext.login import login_required, current_user
from flask.ext.sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm,\
    CommentForm
from .. import db
from .. import redis_store
from .. import lib
from ..models import Permission, Role, User, Post, Comment
from ..decorators import admin_required, permission_required

from datetime import datetime
import subprocess


import codecs, re
from . import mandoku_view

import gitlab, requests
gitlab_host  = "http://gl.kanripo.org"
gitlab_token = "HrNL4a42ZDnyjaHpXty2"



md_re = re.compile(ur"<[^>]*>|[　-㄀＀-￯\n¶]+|\t[^\n]+\n|\$[^;]+;")

dictab = {'hydcd1' : u'漢語大詞典',
          'hydcd' : u'漢語大詞典',
          'hydzd' : u'漢語大字典',
          'sanli' : u'三禮辭典',
          'daikanwa' : u'大漢和辞典',
          'koga' : u'禅語字典',
          'guoyu' : u'國語辭典',
          'abc' : u'ABC漢英詞典',
          'lyt' : u'林語堂當代漢英詞典',
          'cedict' : u'漢英詞典',
          'daojiao' : u'道教大辭典',
          'fks' : u'佛光佛學大辭典',
          'handedic' : u'漢德詞典',
          'dfb' : u'丁福報佛學大辭典',
          'unihan' : u'Unicode 字典',
          'kanwa' : u'發音',
          'kangxi' : u'康熙字典',
          'pinyin' : u'羅馬拼音',
          'loc' : u'其他詞典',
          'je' : u'日英仏教辞典',
          'kg' : u'葛藤語箋',
          'ina' : u'稲垣久雄:Zen Glossary',
          'iwa' : u'岩波仏教辞典',
          'zgd' : u'禪學大辭典',
          'oda' : u'織田佛教大辭典',
          'mz' : u'望月佛教大辭典',
          'matthews' : u'Matthews Chinese English Dictionary',
          'naka' : u'佛教語大辭典',
          'yo' : u'横井日英禪語辭典',
          'zgo' : u'禅の語録',
          'zhongwen' : u'中文大辭典',
          'bsk' : u'佛書解説大辭典',
          'bcs' : u'佛教漢梵大辭典',
          'zd' : u'Zen Dust',
          'ku' : u'ku',
          'sks' : u'sks',
          'guxun' : u'故訓匯纂',
          } 

try:
    import redis
except:
    pass

try:
    r = redis.StrictRedis(host='localhost', port=6379, db=0, charset="utf-8", decode_responses=True)
except:
    r = nil

## helper routines
# dic
def formatle(l, e):
    "formats the location entry"
    ec = e.split('-')
    if l == "daikanwa":
        #V01-p00716-172
        return "[[%sdkw/p%s-%s#%s][%s : %s]]" % (current_app.config['DICURL'], ec[0][1:], ec[1][1:], ec[-1], dictab[l], e)
    elif l == "hydzd" :
        return "[[%shydzd/hydzd-%s][%s : %s]]" % (current_app.config['DICURL'], ec[1], dictab[l], e)
    #comment the next two lines to link to the cached files on the server
    elif l == "kangxi":
        return "[[http://www.kangxizidian.com/kangxi/%4.4d.gif][%s : %s]]" % (int(e), dictab[l], e)
    elif l in ["koga", "ina", "bcs", "naka", "zgd", "sanli", "kangxi"] :
        if "," in e:
            v = e.split(',')[0]
        else:
            v = e
        v = re.sub('[a-z]', '', v)
        try:
            return "[[%s%s/%s-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], l, l, int(v), dictab[l], e)
        except:
            return "%s : %s" % (dictab[l], e)
            
    elif l == "yo":
        ec = e.split(',')
        return "[[%syokoi/yokoi-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], int(ec[0]), dictab[l], e)
    elif l == "mz":
        v = e.split(',')[0]
        v = v.split('p')
#        return "[[%smz/vol%2.2d/mz-v%2.2d-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], int(v[0][1:]), int(v[0][1:]), int(re.sub('[a-z]', '', v[1])),  dictab[l], e)
        return "[[%smz/mz-v%2.2d-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], int(v[0][1:]), int(re.sub('[a-z]', '', v[1])),  dictab[l], e)
    elif l == "je":
        ec = e.split('/')
        if ec[0] == '---':
            v = re.sub('[a-z]', '', ec[1])
        else:
            v = re.sub('[a-z]', '', ec[0])
        return "[[%sjeb/jeb-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], int(v), dictab[l], e)
    elif l == "zhongwen":
        # zhongwen : V09-p14425-1
        return "[[%szhwdcd/zhwdcd-p%5.5d][%s : %s]]" % (current_app.config['DICURL'], int(ec[1][1:]), dictab[l], e)
    elif l == "oda" :
        ec = e.split('*')
        pg = int(ec[-1].split('-')[0])
        return "[[%soda/oda-p%4.4d][%s : %s]]" % (current_app.config['DICURL'], pg, dictab[l], e)
    else:
        try:
            return "%s : %s" % (dictab[l], e)
        except:
            return "%s : %s" % (l, e)
            
def dicentry(key):
    if r:
        try:
            d = r.hgetall(key)
        except:
            return "no result"
        try:
            d.pop('dummy')
        except:
            pass
        if len(d) > 0:
            ks = d.keys()
            ks.sort()
            s = "** %s (%s)" % (key, len(d))
            xtr = ""
            ytr = ""
            df=[]
            lc=[]
            hy=[]
            seen=[]
            for a in ks:
                k = a.split('-')
                if k[0] == 'loc':
                    lc.append(formatle(k[1], d[a]))
                else:
                    if k[1] == 'kanwa':
                        xtr +=  " " + d[a]
                    if k[1] == 'abc':
                        ytr += " " + d[a]
                    if k[1] == 'hydcd1':
                        hy.append("**** %s: %s\n" % ("".join(k[2:]), d[a]))
                    elif k[1] in seen:
                        df.append("%s: %s\n" % ("".join(k[2:]), d[a]))
                    else:
                        if len(k) > 1:
                            df.append("*** %s\n%s: %s\n" % (dictab[k[1]], "".join(k[2:]), d[a]))
                        else:
                            df.append("*** %s\n%s\n" % (dictab[k[1]],  d[a]))
                        seen.append(k[1])
            if len(hy) > 0:
                hyr = "*** %s\n%s\n" % (dictab['hydcd1'],  "".join(hy))
            else:
                hyr = ""
            if len(df) > 0:
                dfr = "%s\n" % ("".join(df))
            else:
                dfr = ""
            if len(s) + len(xtr) + len(ytr) > 100:
                dx = 100 - len(s) - len(xtr) 
#                print dx
                ytr = ytr[0:dx]
            xtr = ytr = ""
            return u"%s%s%s\n%s%s*** %s\n%s\n" % (s, xtr, ytr, hyr , dfr, dictab['loc'] , "\n".join(lc))
        else:
            return ""
    else:
        return "no redis"

def prevnext(page):
    p = page.split('-')
    if p[-1].startswith ('p'):
        n= int(p[-1][1:])
        fn = fn = "%%%d.%dd" % (len(p[-1]) - 1, len(p[-1]) - 1)
        prev = "%s-p%s" % ("-".join(p[:-1]), fn % (n - 1) )
        next = "%s-p%s" % ("-".join(p[:-1]), fn % (n + 1) )
    else:
        n= int(p[-1])
        fn = fn = "%%%d.%dd" % (len(p[-1]), len(p[-1]))
        prev = "%s-%s" % ("-".join(p[:-1]), fn % (n - 1) )
        next = "%s-%s" % ("-".join(p[:-1]), fn % (n + 1) )
    return prev, next


@main.route('/procline', methods=['GET',])
def procline():
    l = request.values.get('query', '')
    l = md_re.sub("", l)
    de = []
    try:
        for i in range(0, len(l)):
            j = i+1
            res = dicentry(l[i:j])
            de.append(res)
            while res and j < len(l):
                j += 1
                res = dicentry(l[i:j])
                de.append(res)
        return "\n%s" % ("".join(de))
    except:
        return "Not Found: %s " % (l)


def doftsearch(key):
    try:
    #subprocess.call(['bzgrep -H ^龍二  /Users/Shared/md/index/79/795e*.idx*'], stdout=of, shell=True )
    #ox = subprocess.check_output(['bzgrep -H ^%s  /Users/Shared/md/index/%s/%s*.idx*' % (key[1:], ("%4.4x" % (ord(key[0])))[0:2], "%4.4x" % (ord(key[0])))], shell=True )
        ox = subprocess.check_output(['bzgrep -H ^%s  %s/%s/%s*.idx* | cut -d : -f 2-' % (key[1:],
              current_app.config['IDXDIR'],  ("%4.4x" % (ord(key[0])))[0:2], "%4.4x" % (ord(key[0])))], shell=True )
    except subprocess.CalledProcessError:
        return False
    ux = ox.decode('utf8')
    s=ux.split('\n')
    s.sort()
    redis_store.rpush(key, *s)
    return True
    
@main.route('/search', methods=['GET', 'POST',])
def searchtext(count=20, page=1):
    key = request.values.get('query', '')
#    rep = "\n%s:" % (request.values.get('rep', 'ZB'))
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    #/Users/Shared/md/index"
    if len(key) > 0:
        if not redis_store.exists(key):
            doftsearch(key)
    else:
        return "400 please submit searchkey as parameter 'query'."
    total = redis_store.llen(key)
    start = (page - 1) * count  + 1
    ox = [  (k.split()[0].split(','), k.split()[1]) for k in redis_store.lrange(key, start, start+count)]
    p = lib.Pagination(key, page, count, total, ox)
    return render_template('result.html', sr={'list' : p.items, 'total': total, 'head' : '', 'link' : '' }, key=key, pagination=p)
    return ox

@main.route('/searchw', methods=['GET', 'POST',])
def searchtextw(count=20, start=None, n=20):
    key = request.values.get('query', '')
#    rep = "\n%s:" % (request.values.get('rep', 'ZB'))
    count=int(request.values.get('count', count))
    start=int(request.values.get('start', 0))
    #/Users/Shared/md/index"
    #subprocess.call(['bzgrep -H ^龍二  /Users/Shared/md/index/79/795e*.idx*'], stdout=of, shell=True )
    #ox = subprocess.check_output(['bzgrep -H ^%s  /Users/Shared/md/index/%s/%s*.idx*' % (key[1:], ("%4.4x" % (ord(key[0])))[0:2], "%4.4x" % (ord(key[0])))], shell=True )
    if len(key) > 0:
        total, ox = doftsearch(key)
    else:
        return "400 please submit searchkey as parameter 'query'."
    return render_template('searchresult.html', sr={'list' : lx, 'total': total, 'head' : Markup(h), 'link' : Markup(t) }, key=key)
    return ox

@main.route('/text/<coll>', methods=['GET',] )
def showcoll(coll, edition=None, fac=False):
    return coll

#@main.route('/text/<coll>/<int:seq>/<int:juan>', methods=['GET',] )

@main.route('/text/<coll>/<seq>/<juan>', methods=['GET',] )
@main.route('/text/<id>/<juan>', methods=['GET',])
def showtext(juan, id=0, coll=None, seq=0):
    juan = "%3.3d" % (int(juan))
    if coll:
        if coll.startswith('ZB'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            #TODO need to find the canonical id for this, go to redis, pull it out
            id="Not Implemented"
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    url =  "%s/%s/%s/raw/master/%s_%s.txt?private_token=%s" % (gitlab_host, id[0:4], id,  id, juan, gitlab_token)
#    print url
    r = requests.get(url)
    if b"<!DOCTYPE html>" in r.content:
        print "Not retrieved from Gitlab!", id
        filename = "%s/%s/%s_%s.txt" % (id[0:4], id, id, juan)
        datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
        try:
            datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
            fn = codecs.open(datei)
        except:
            return "File Not found: %s" % (filename)
        md = mandoku_view.mdDocument(fn.read(-1))
    else:
        md = mandoku_view.mdDocument(r.content.decode('utf-8'))
#    print "\n".join(["%d,%s" % (m) for m in md.toc])
    return Response ("\n%s" % ( "\n".join(md.md)),  content_type="text/html;charset=UTF-8")


## file

@main.route('/getfile', methods=['GET',])
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

## image

@main.route('/getimage', methods=['GET',])
def getimage():
    filename = request.values.get('filename', '')
    try:
        datei = "%s/%s" % (current_app.config['IMGDIR'], filename)
        fn = codecs.open(datei)
    except:
        return "Not found"
    return Response ("\n%s" % (fn.read(-1)),  content_type="text/plain;charset=UTF-8")

## dic

@main.route('/dicpage/<dic>/<page>', methods=['GET',])
def dicpage(dic=None,page=None):
#    pn = "a", "b"
    pn = prevnext(page)
    us = url_for('static', filename='dic')
    return """<html>
<body>
<img src="%s/%s/%s.png" style="width:100%%;"/>
<a href="/dicpage/%s" type="button" id="btnPrev" >%s</a>
<a href="/dicpage/%s" type="button" id="btnNext">%s</a>
</body>
</html>""" % (us, dic, page, "%s/%s" % (dic, pn[0]), pn[0], "%s/%s" % (dic, pn[1]), pn[1])

@main.route('/dic', methods=['GET',])
def searchdic():
    key = request.values.get('query', '')
    return dicentry(key)



## unrelated:

@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['MDWEB_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'

## below is the SNS stuff

@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        post = Post(body=form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated():
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['MDWEB_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts,
                           show_followed=show_followed, pagination=pagination)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['MDWEB_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts,
                           pagination=pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) / \
            current_app.config['MDWEB_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['MDWEB_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['MDWEB_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['MDWEB_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['MDWEB_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,
                           pagination=pagination, page=page)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))

@main.route('/about/<id>')
def about(id):
    if id=='dzjy':
        return render_template('about_dzjy.html')
    else:
        return 'The about page'
@main.route('/contact')
def contact():
    return render_template('contact.html')

