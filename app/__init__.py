# app/__init__.py

# import os
# from flask import Flask, send_from_directory, abort
# from .config import Config
# from .extensions import db, bcrypt, jwt, cors, migrate
# from .blueprints.auth import auth_bp
# from .blueprints.compare import compare_bp

# def create_app():
#     # Calculate absolute path to your dist folder
#     # Assumes your project layout is:
#     #   modular/
#     #   ├── app/
#     #   ├── dist/          ← your React build here
#     #   └── run.py
#     project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
#     dist_dir = os.path.join(project_root, 'dist')

#     # Create Flask and point static_folder at the dist directory
#     app = Flask(
#         __name__,
#         static_folder=dist_dir,
#         static_url_path=''    # serve static files at root, e.g. '/static.js'
#     )
#     app.config.from_object(Config)

#     # Initialize extensions
#     db.init_app(app)
#     migrate.init_app(app, db)
#     bcrypt.init_app(app)
#     jwt.init_app(app)
#     cors.init_app(app, resources={r"/*": {"origins": Config.CORS_ORIGINS}})

#     # Register your API blueprints
#     app.register_blueprint(auth_bp)
#     app.register_blueprint(compare_bp)

#     # Catch-all route to serve your React app
#     @app.route('/', defaults={'path': ''})
#     @app.route('/<path:path>')
#     def serve_frontend(path):
#         # If the requested file exists in dist, serve it; otherwise index.html
#         file_path = os.path.join(dist_dir, path)
#         if path and os.path.isfile(file_path):
#             return send_from_directory(dist_dir, path)
#         elif os.path.isfile(os.path.join(dist_dir, 'index.html')):
#             return send_from_directory(dist_dir, 'index.html')
#         else:
#             # dist or index.html missing
#             abort(404)

#     return app




# # app/__init__.py

# from flask import Flask
# from .config import Config
# from .extensions import db, bcrypt, jwt, cors, migrate
# from .blueprints.auth import auth_bp
# from .blueprints.compare import compare_bp

# def create_app():
#     # Instantiate Flask without serving any static folder
#     app = Flask(__name__, static_folder=None)
#     app.config.from_object(Config)

#     # Initialize extensions
#     db.init_app(app)
#     migrate.init_app(app, db)
#     bcrypt.init_app(app)
#     jwt.init_app(app)
#     cors.init_app(app, resources={r"/*": {"origins": Config.CORS_ORIGINS}})

#     # Register blueprints for your API routes
#     app.register_blueprint(auth_bp)
#     app.register_blueprint(compare_bp)

#     return app
import os
from flask import Flask, send_from_directory, abort
from .config import Config
from .extensions import db, bcrypt, jwt, cors, migrate
from .blueprints.auth import auth_bp
from .blueprints.compare import compare_bp

def create_app():
    # Get absolute path to React's built dist folder
    project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    dist_dir = os.path.join(project_root, 'dist')

    app = Flask(
        __name__,
        static_folder=dist_dir,
        static_url_path=''
    )
    app.config.from_object(Config)

    app.config["JWT_SECRET_KEY"] = Config.JWT_SECRET_KEY
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, supports_credentials=True, resources={
        r"/*": {"origins": Config.CORS_ORIGINS}
    })

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(compare_bp)

    # Serve React frontend (production build)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        file_path = os.path.join(dist_dir, path)
        if path and os.path.isfile(file_path):
            return send_from_directory(dist_dir, path)
        elif os.path.isfile(os.path.join(dist_dir, 'index.html')):
            return send_from_directory(dist_dir, 'index.html')
        else:
            abort(404)

    return app
