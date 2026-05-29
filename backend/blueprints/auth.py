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
    """Registers a new user, hashes password, and creates standard stats."""
    data = request.get_json() or {}
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    # Input sanitization and validations
    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({"msg": "Username must be between 3 and 30 characters"}), 400

    if len(password) < 6:
        return jsonify({"msg": "Password must be at least 6 characters long"}), 400

    # SQL Injection protection & duplicate check
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"msg": "Username already exists"}), 409

    try:
        # Create User
        new_user = User(username=username)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.flush() # Populate new_user.id for stats foreign key

        # Create user Stats
        user_stats = Stats(
            user_id=new_user.id,
            highest_score=0,
            average_score=0.0,
            total_attempts=0,
            win_ratio=0.0,
            current_streak=0
        )
        db.session.add(user_stats)
        db.session.commit()

        return jsonify({"msg": "Registration successful. You can now login.", "user": new_user.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"An error occurred: {str(e)}"}), 500


@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=5, period=60)
def login():
    """Logs in user and sets secure, HttpOnly JWT cookies."""
    data = request.get_json() or {}
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        current_app.logger.warning(f"SECURITY ALERT: Failed login attempt for username '{username}' from IP {request.remote_addr}")
        return jsonify({"msg": "Invalid username or password"}), 401
    
    # Generate token
    # Flask-JWT-Extended stores the identity as a string
    access_token = create_access_token(identity=str(user.id))

    # Build response and attach HttpOnly access cookies
    response = jsonify({
        "msg": "Login successful",
        "user": user.to_dict()
    })
    set_access_cookies(response, access_token)

    return response, 200


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
