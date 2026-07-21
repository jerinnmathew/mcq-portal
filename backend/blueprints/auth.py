from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, set_access_cookies, unset_jwt_cookies
from backend.models import db, User, Stats
import time
from functools import wraps

auth_bp = Blueprint('auth', __name__)

# Lightweight in-memory rate-limiter for brute-force attack prevention
_rate_tracker = {}

def rate_limit(limit=5, period=60):
    """
    Lightweight, custom API Rate Limiting decorator.
    Restricts request frequency per IP address to prevent brute-force attacks.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            if ip not in _rate_tracker:
                _rate_tracker[ip] = []
                
            # Filter timestamps to keep only those within the active tracking window
            _rate_tracker[ip] = [t for t in _rate_tracker[ip] if now - t < period]
            
            if len(_rate_tracker[ip]) >= limit:
                return jsonify({
                    "msg": "Too many requests. Please wait a moment before trying again."
                }), 429
                
            _rate_tracker[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator


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
@jwt_required()
def get_profile():
    """Gets details of the logged in user."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    
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
    return response, 200
