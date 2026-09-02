from flask import Blueprint, jsonify
from flask_jwt_extended import unset_jwt_cookies
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
