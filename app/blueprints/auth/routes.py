# app/blueprints/auth/routes.py
from flask      import request, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime   import datetime
import socket
from ...extensions import bcrypt, db
from ...models     import User
from ...services.logging_service import write_login_log
from ...utils.time_utils        import get_ist_time
from . import auth_bp

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"message":"Email and password required"}), 400

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"message":"Invalid email or password"}), 401

    token = create_access_token(identity=user.id)
    resp  = make_response(jsonify({
        "message":"Login successful",
        "id": user.id,
        "email": user.email,
        "token": token
    }))
    resp.set_cookie("access_token_cookie", token, httponly=True, samesite="Lax", path="/")

    # log
    write_login_log(user.id, request.remote_addr)
    return resp, 200

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    # 1) Validate input
    if not data.get("email") or not data.get("password"):
        return jsonify({"message": "Email and password required"}), 400

    # 2) Check for existing user
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "User with that email already exists"}), 409

    # 3) Hash & save
    hashed = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    new_user = User(email=data["email"], password=hashed)
    db.session.add(new_user)
    db.session.commit()

    # 4) Return created user
    return jsonify({
        "id": new_user.id,
        "email": new_user.email
    }), 201


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    resp = make_response(jsonify({"message":"Logout successful"}))
    resp.delete_cookie("access_token_cookie", path="/")
    return resp, 200

@auth_bp.route("/@me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({"message":"User not found"}), 404
    return jsonify({"id":user.id,"email":user.email}), 200
