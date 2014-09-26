#    -*- coding: utf-8 -*-
from __future__ import unicode_literals
from flask import Response, render_template, redirect, url_for, abort, flash, Markup, request,\
    current_app, make_response, send_from_directory
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
from collections import Counter

from datetime import datetime
import subprocess


import codecs, re
from .. import mandoku_view

import gitlab, requests

zbmeta = "zb:meta:"
titpref = "zb:title:"
link_re = re.compile(r'\[\[([^\]]+)\]\[([^\]]+)')
hd = re.compile(r"^(\*+) (.*)$")

@main.route('/robots.txt')
@main.route('/googled78ca805afaa95df.html')
# @main.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

@main.route('/search', methods=['GET', 'POST',])
def searchtext(count=20, page=1):
    key = request.values.get('query', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    tpe = request.values.get('type', '')
    if len(key) > 0:
        if not redis_store.exists(key):
            if not lib.doftsearch(key):
                return render_template("error_page.html", description = "Text search for %s: Nothing found!" % (key), key=key)
    else:
        return render_template("error_page.html", code="400", name = "Search Error", description = "No search term. Please submit the search term as parameter 'query'.")
    fs = filters.split(';')
    fs = [a for a in fs if len(a) > 0]
    start = (page - 1) * count 
    if len(fs) < 1:
        total = redis_store.llen(key)
        ox = [  (k.split()[0].split(','), k.split()[1], redis_store.hgetall("%s%s" %( zbmeta, k.split()[1].split(':')[0][0:8]))) for k in redis_store.lrange(key, start, start+count-1)]
    else:
        ox1 = lib.applyfilter(key, fs, tpe)
        total = len(ox1)
        ox = [(k.split()[0].split(','), k.split()[1], redis_store.hgetall("%s%s" %( zbmeta, k.split()[1].split(':')[0][0:8]))) for k in ox1[start:start+count+1]]
    p = lib.Pagination(key, page, count, total, ox)
    return render_template('result.html', sr={'list' : p.items, 'total': total }, key=key, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' }, start=start, count=count, n = min(start+count, total), filter=";".join(fs), tpe=tpe)



@main.route('/text/<coll>', methods=['GET',] )
def showcoll(coll, edition=None, fac=False):
    return coll

@main.route('/text/<id>/', methods=['GET',])
def texttop(id=0, coll=None, seq=0):
    ct = {'toc' : [], 'id' : id}
    filename = "%s/%s/%s.org" % (id[0:4], id[0:8], id)
    datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
    try:
        datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
        fn = codecs.open(datei, 'r', 'utf-8')
    except:
        return "File Not found: %s" % (filename)
    for line in fn:
        if line.startswith('#+TITLE:'):
            ct['title'] = line[:-1].split(' ', 1)[-1]
        if hd.search(line):
            tmp = hd.findall(line)[0][0]
            lev = len(tmp[0])
        else:
            tmp = ""
        if link_re.search(line):
            l = [tmp]
            l.extend(re.findall(r'\[\[([^\]]+)\]\[([^\]]+)', line))
            ct['toc'].append(l)
    return  render_template('texttop.html', ct=ct)

#@main.route('/text/<coll>/<int:seq>/<int:juan>', methods=['GET',] )
@main.route('/text/<coll>/<seq>/<juan>', methods=['GET',] )
@main.route('/text/<id>/<juan>', methods=['GET',])
def showtext(juan, id=0, coll=None, seq=0):
    doc = {}
    key = request.values.get('query', '')
    try:
        juan = "%3.3d" % (int(juan))
    except:
        pass
    if coll:
        if coll.startswith('ZB'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            #TODO need to find the canonical id for this, go to redis, pull it out
            id="Not Implemented"
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    # url =  "%s/%s/%s/raw/master/%s_%s.txt?private_token=%s" % (current_app.config['GITLAB_HOST'], id[0:4], id,  id, juan, current_app.config['GITLAB_TOKEN'])
    # r = requests.get(url)
    # if b"<!DOCTYPE html>" in r.content:
    #     print "Not retrieved from Gitlab!", id
    filename = "%s/%s/%s_%s.txt" % (id[0:4], id[0:8], id, juan)
    datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
    try:
        datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
        fn = codecs.open(datei)
    except:
        return "File Not found: %s" % (filename)
    md = mandoku_view.mdDocument(fn.read(-1))
    try:
        res = redis_store.hgetall("%s%s" % ( zbmeta, id[0:8]))
    except:
        res = {}
    res['ID'] = id
    try:
        title = res['TITLE']
    except:
        title = ""
    # else:
    #     md = mandoku_view.mdDocument(r.content.decode('utf-8'))
    return render_template('showtext.html', ct={'mtext': Markup("<br/>".join(md.md)), 'doc': res}, doc=res, key=key, title=title, txtid=res['ID'] )
#return Response ("\n%s" % ( "\n".join(md.md)),  content_type="text/html;charset=UTF-8")

def showtextredis(juan, id=0, coll=None, seq=0):
    juan = "%3.3d" % (int(juan))
    if coll:
        if coll.startswith('ZB'):
            id = "%s%4.4d" % (coll, int(seq))
        else:
            #TODO need to find the canonical id for this, go to redis, pull it out
            id="Not Implemented"
    #the filename is of the form ZB1a/ZB1a0001/ZB1a0001_002.txt
    filename = "%s/%s/%s_%s.txt" % (id[0:4], id, id, juan)
    datei = "%s/%s" % (current_app.config['TXTDIR'], filename)
    mr = mandoku_redis.RedisMandoku(redis_store, None, 100000, datei)
    
    return render_template('', ct={'mtext': md.md, 'doc' : doc} )
    

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

## dic  these two also in api

@main.route('/dicpage/<dic>/<page>', methods=['GET',])
def dicpage(dic=None,page=None):
#    pn = "a", "b"
    pn = lib.prevnext(page)
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
    return lib.dicentry(key, current_app.config['DICURL'])


## catalog
@main.route('/catalog', methods=['GET',])
def catalog():
    r=redis_store
    coll = request.values.get('coll', '')
    subcoll = request.values.get('subcoll', '')
    if len(coll) < 1 and len(subcoll) < 1:
        cat = [r.hgetall(a) for a in r.keys("zb:catalog*")]
        cat.sort(key=lambda t : t['ID'])
    else:
        cat = [redis_store.hgetall("%s%s" %( zbmeta, k.split(':')[-1][0:8])) for k in r.keys(zbmeta+coll+"*")]
#        cat = [c for c in cat if coll in  c['ID']]
        cat.sort(key=lambda t : t['ID'])
    return render_template('catalog.html', cat = cat, sr={'total': 0, 'coll': coll})

@main.route('/titlesearch', methods=['GET',])
def titlesearch(count=20, page=1):
    key = request.values.get('query', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    filters = request.values.get('filter', '')
    fs = filters.split(';')
    fs = [a for a in fs if len(a) > 1]
    if len(key) > 0:
        if not redis_store.exists(titpref+key):
            if not(lib.dotitlesearch(titpref, key)):
                return render_template("error_page.html", description = "Title search for %s: Nothing found" % (key), key=key)
    else:
        return render_template("error_page.html", code="400", name = "Search Error", description = "No search term. Please submit the search term as parameter 'query'.")
    start = (page - 1) * count
    total = redis_store.llen(titpref+key)
    tits = redis_store.lrange(titpref+key, start, start+count)
    p = lib.Pagination(key, page, count, total, tits)
    return render_template('titles.html', sr={'list' : p.items, 'total': total }, key=key, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' }, start=start, count=count, n = min(start+count, total), filter=";".join(fs), prefix=titpref)

## filter
@main.route('/getfacets', methods=['GET', ])
def getfacets():
    key = request.values.get('query', '')
    tpe = request.values.get('type', 'ID')
    prefix = request.values.get('prefix', '')
    # length of the ID
    ln = int(request.values.get('len', '3'))
    # number of top_most entries, 0 = all
    cnt = int(request.values.get('cnt', '3'))
    if cnt == 0:
        cnt = None
    if tpe == 'ID':
        f = [a.split('\t')[1][0:ln] for a in redis_store.lrange(prefix+key, 1, redis_store.llen(prefix+key))]
    elif tpe == 'DYNASTY':
        f = [redis_store.hgetall("%s%s" % (zbmeta, a.split('\t')[1].split(':')[0])) for a in redis_store.lrange(prefix+key, 1, redis_store.llen(prefix+key))]
        f = [a['DYNASTY'] for a in f if a.has_key('DYNASTY')]
    c = Counter(f)
    if tpe == 'ID':
        fs = [(a[0], redis_store.hgetall("%s%s" %(zbmeta, a[0])), a[1], tpe) for a in c.most_common(cnt)]
    elif tpe == 'DYNASTY':
        fs = [(a[0], {'TITLE': a[0]}, a[1], tpe) for a in c.most_common(cnt)]
    return render_template('facets.html', fs=fs, key=key)
#    return Response("%s" % (c.most_common(cnt)))

@main.route('/addfilter', methods=['GET',])
def addfilter(count=20, page=1):
    key = request.values.get('query', '')
    add = request.values.get('newfilter', '')
    filters = request.values.get('filter', '')
    count=int(request.values.get('count', count))
    page=int(request.values.get('page', page))
    fs = filters.split(';')
    fs.append(add)
    start = (page - 1) * count  + 1
    ox = lib.applyfilter(key, fs)
    total = len(ox)
    print total, fs
    ox = ox[start:start+count]
    oy = [  (k.split()[0].split(','), k.split()[1], redis_store.hgetall("%s%s" %( zbmeta, k.split()[1].split(':')[0][0:8]))) for k in ox]
    p = lib.Pagination(key, page, count, total, oy)
    return render_template('result.html', sr={'list' : p.items, 'total': total, 'head' : '', 'link' : '' }, key=key, pagination=p, pl={'1': 'a', '2': 'b', '3': 'c', '4' :'d' })
    

@main.route('/remfilter', methods=['GET',])
def remfilter():
    query = request.values.get('query', '')
    rem = request.values.get('remove', '')
    filters = request.values.get('filter', '')
    print filters
    
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


@main.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

## below is the SNS stuff

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

