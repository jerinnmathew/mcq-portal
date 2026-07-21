from datetime import datetime
from functools import wraps

import jwt as pyjwt
from flask import current_app, request, jsonify
from backend.models import User


def get_current_user():
    """Return the currently authenticated user from our session_token cookie."""
    token = request.cookies.get("session_token")
    if not token:
        return None

    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        current_app.logger.error("SECRET_KEY is not configured for session JWT decoding")
        return None

    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.PyJWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def login_required(fn):
    """Decorator that requires a valid session_token cookie."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"msg": "Unauthorized"}), 401
        return fn(user, *args, **kwargs)
    return wrapper


def calculate_streak_and_xp(user, score, total_questions, last_attempt):
    """
    Calculates updated streak, XP rewards, and badges for a user.
    Returns:
        (updated_streak, xp_earned, badge_awarded)
    """
    # 1. Calculate accuracy
    accuracy = (score / total_questions) * 100 if total_questions > 0 else 0.0

    # 2. Calculate streak updates
    now = datetime.utcnow()
    today = now.date()
    
    current_streak = user.streak
    streak_updated = False
    
    if not last_attempt:
        # First attempt ever starts a streak
        current_streak = 1
        streak_updated = True
    else:
        last_date = last_attempt.submitted_at.date()
        delta = (today - last_date).days
        
        if delta == 1:
            # Consecutive day: increment streak
            current_streak += 1
            streak_updated = True
        elif delta > 1:
            # Missed a day: reset streak to 1
            current_streak = 1
            streak_updated = True
        # If delta == 0, they already completed a quiz today; streak is maintained but not double-incremented

    # 3. Calculate XP earned
    # Base XP: 10 XP per correct answer
    base_xp = score * 10
    
    # Streak bonus
    streak_bonus = 0
    if current_streak >= 10:
        streak_bonus = 30
    elif current_streak >= 5:
        streak_bonus = 15
    elif current_streak >= 3:
        streak_bonus = 10

    # Accuracy bonus
    accuracy_bonus = 0
    if accuracy == 100.0:
        accuracy_bonus = 50
    elif accuracy >= 80.0:
        accuracy_bonus = 20
    elif accuracy >= 50.0:
        accuracy_bonus = 5

    xp_earned = base_xp + streak_bonus + accuracy_bonus

    # 4. Calculate badge promotions
    total_xp = user.xp_points + xp_earned
    
    if total_xp >= 1500:
        badge = 'Platinum'
    elif total_xp >= 500:
        badge = 'Gold'
    elif total_xp >= 100:
        badge = 'Silver'
    else:
        badge = 'Bronze'

    return current_streak, xp_earned, badge
