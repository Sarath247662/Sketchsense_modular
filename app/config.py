# app/config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY               = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI  = os.getenv("DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY           = SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=0.5)
    JWT_TOKEN_LOCATION       = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT  = False

    CORS_ORIGINS             = ["http://10.245.146.151:5002"]
    #CORS_ORIGINS             = ["http://localhost:5000","http://127.0.0.1:5000"]
    MAX_CONTENT_LENGTH       = 50 * 1024 * 1024
