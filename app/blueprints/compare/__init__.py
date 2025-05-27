# app/blueprints/compare/__init__.py
from flask import Blueprint

compare_bp = Blueprint("compare", __name__)

from . import routes
