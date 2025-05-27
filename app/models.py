# app/models.py
from .extensions import db
from uuid import uuid4

def get_uuid():
    return uuid4().hex

class User(db.Model):
    __tablename__ = "users"
    id       = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    email    = db.Column(db.String(345), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
