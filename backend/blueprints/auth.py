import os
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from flask import Blueprint, current_app, jsonify, make_response, request
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies
from backend.models import User, db
from backend.utils.helpers import login_required, rate_limit

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
@rate_limit(limit=10, period=60)
def register():
    """Local registration is disabled; only SSO from padikkunnundo.app is supported."""
    return jsonify({
        "msg": "Registration is disabled. Please sign in with padikkunnundo.app."
    }), 403


@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=5, period=60)
def login():
    """Local password login is disabled; only SSO from padikkunnundo.app is supported."""
    return jsonify({
        "msg": "This site uses SSO only. Please sign in through padikkunnundo.app."
    }), 403


@auth_bp.route('/admin-login', methods=['POST'])
@rate_limit(limit=5, period=60)
def admin_login():
    """Authenticate the configured administrator for local admin-panel access."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    admin_username = os.environ.get('ADMIN_USERNAME', '').strip()
    admin_password = os.environ.get('ADMIN_PASSWORD', '')

    if not admin_username or not admin_password:
        return jsonify({"msg": "Admin login is not configured on the server."}), 503

    if username != admin_username or password != admin_password:
        return jsonify({"msg": "Invalid admin credentials."}), 401

    user = User.query.filter_by(username=admin_username).first()
    if not user or not user.check_password(password):
        return jsonify({"msg": "Admin account is not initialized. Restart the server."}), 503

    access_token = create_access_token(identity=str(user.id))
    session_token = pyjwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    response = make_response(jsonify({"msg": "Admin login successful"}))
    set_access_cookies(response, access_token)
    response.set_cookie(
        "session_token",
        session_token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=not current_app.debug,
    )
    return response, 200


@auth_bp.route('/profile', methods=['GET'])
@login_required
def get_profile(user):
    """Gets details of the logged in user."""
    if not user:
        return jsonify({"msg": "User not found"}), 404
        
    return jsonify({
        "user": user.to_dict(),
        "stats": user.stats.to_dict() if user.stats else None
    }), 200





@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logs out user by clearing the secure HttpOnly JWT cookies."""
    response = jsonify({"msg": "Logged out successfully"})
    unset_jwt_cookies(response)
    response.delete_cookie("session_token")
    return response, 200
