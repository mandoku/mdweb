#    -*- coding: utf-8 -*-
import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    MDBASE="/Users/Shared/krp"
    TXTDIR="/Users/Shared/krpdev/src"
    IDXDIR="/Users/Shared/krp/index"
    IMGDIR="/Users/Shared/images/general/skqs/wyg"
    LANGUAGES = {
        'ja': '日本語',
        'en': 'English',
        }
    BABEL_DEFAULT_LOCALE='ja'
    DICURL = "dic:"
    REDIS_URL = "redis://localhost:6379/5"


    SECRET_KEY = os.environ.get('SECRET_KEY') or 'X and U and Z string'
    SSL_DISABLE = False
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MDWEB_MAIL_SUBJECT_PREFIX = '[Kanripo]'
    MDWEB_MAIL_SENDER = 'Kanripo Admin <admin@kanripo.org>'
    MDWEB_ADMIN = os.environ.get('MDWEB_ADMIN')
    MDWEB_POSTS_PER_PAGE = 20
    MDWEB_FOLLOWERS_PER_PAGE = 50
    MDWEB_COMMENTS_PER_PAGE = 30
    MDWEB_SLOW_DB_QUERY_TIME=0.5
    GITHUB_OAUTH_CLIENT_SECRET="96353df0ca6d6a4db5f5520e1b0b898ad4bab004"
    GITHUB_OAUTH_CLIENT_ID="32e5b9df1b848ffaa194"
    OAUTHLIB_INSECURE_TRANSPORT=True
    


    
    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data.sqlite')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # email errors to the administrators
        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, 'MAIL_USERNAME', None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, 'MAIL_USE_TLS', None):
                secure = ()
        mail_handler = SMTPHandler(
            mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
            fromaddr=cls.MDWEB_MAIL_SENDER,
            toaddrs=[cls.MDWEB_ADMIN],
            subject=cls.MDWEB_MAIL_SUBJECT_PREFIX + ' Application Error',
            credentials=credentials,
            secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


class HerokuConfig(ProductionConfig):
    SSL_DISABLE = bool(os.environ.get('SSL_DISABLE'))

    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # handle proxy server headers
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

        # log to stderr
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.WARNING)
        app.logger.addHandler(file_handler)


class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # log to syslog
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'heroku': HerokuConfig,
    'unix': UnixConfig,

    'default': DevelopmentConfig
}
