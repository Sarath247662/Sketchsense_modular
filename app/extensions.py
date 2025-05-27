# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt       import Bcrypt
from flask_jwt_extended import JWTManager
from flask_cors         import CORS
from flask_migrate import Migrate

db     = SQLAlchemy()
bcrypt = Bcrypt()
jwt    = JWTManager()
cors   = CORS(resources={r"/*": {"origins": None}})

# app/extensions.py

# from flask_sqlalchemy import SQLAlchemy
# from flask_bcrypt import Bcrypt
# from flask_jwt_extended import JWTManager
# from flask_cors import CORS
# from flask_migrate import Migrate

# # Core extensions
# db      = SQLAlchemy()
# bcrypt  = Bcrypt()
# jwt     = JWTManager()
# cors    = CORS()

# Migrations
migrate = Migrate()
