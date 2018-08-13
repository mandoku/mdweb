#    -*- coding: utf-8 -*-
from flask import Flask
from flask.ext.bootstrap import Bootstrap
from flask.ext.mail import Mail
from flask.ext.moment import Moment
from flask.ext.sqlalchemy import SQLAlchemy
#from flask.ext.login import LoginManager
from flask.ext.pagedown import PageDown
from flask.ext.redis import Redis
from flask.ext.babel import Babel
from flask_cors import CORS
from config import config
from flask_dance.contrib.github import make_github_blueprint
bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
pagedown = PageDown()
redis_store = Redis()
babel = Babel()
#login_manager = LoginManager()
#login_manager.session_protection = 'strong'
#login_manager.login_view = 'auth.login'
github_bp = make_github_blueprint(scope=["repo"])



def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    #login_manager.init_app(app)
    pagedown.init_app(app)
    
    redis_store.init_app(app)
    babel.__init__(app)
    cors = CORS(app, resources={r"/api/*": {"origins": "*"}})    
    if not app.debug and not app.testing and not app.config['SSL_DISABLE']:
        from flask.ext.sslify import SSLify
        sslify = SSLify(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # from .auth import auth as auth_blueprint
    # app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .api_1_0 import api as api_1_0_blueprint
    app.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')

    app.register_blueprint(github_bp, url_prefix="/login")

    return app
