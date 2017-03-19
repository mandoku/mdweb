#    -*- coding: utf-8 -*-
from flask import Blueprint

tls = Blueprint('tls', __name__,
                template_folder='templates',
                static_folder='static'
)

from . import views, errors
#from ..models import Permission


# @main.app_context_processor
# def inject_permissions():
#     return dict(Permission=Permission)
