from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from datetime import datetime, timedelta
from backend.models import db, User, Attempt, Stats

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Returns aggregated student statistics and recent attempt history for dashboard charts."""
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Ensure stats entry exists
    stats = db.session.get(Stats, user.id)
    if not stats:
        stats = Stats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()

    # Fetch the latest attempts without loading extra relationships
    recent_attempts = Attempt.query.filter_by(user_id=user.id)\
                                   .order_by(Attempt.submitted_at.desc())\
                                   .limit(10).all()
    # Reverse so charts read left-to-right (chronologically)
    recent_attempts.reverse()

    attempts_data = [a.to_dict() for a in recent_attempts]

    # Calculate category strengths (Bonus analytics for dashboard!)
    # We can fetch categories user has attempted
    return jsonify({
        "user": user.to_dict(),
        "stats": stats.to_dict(),
        "recent_attempts": attempts_data
    }), 200


@stats_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """
    Returns global leaderboard ranks with Today, Weekly, and All-Time filters.
    Rank users by total correct answers in period or overall XP for All-Time.
    """
    time_filter = request.args.get('filter', 'all-time').lower()
    now = datetime.utcnow()
    
    leaderboard = []

    if time_filter == 'today':
        start_date = datetime(now.year, now.month, now.day)
    elif time_filter == 'weekly':
        start_date = now - timedelta(days=7)
    else:
        time_filter = 'all-time'
        start_date = None

    import os
    admin_user = os.environ.get('ADMIN_USERNAME', 'jerin_admin')

    if time_filter == 'all-time':
        # Rank by overall XP, excluding admin
        top_users = User.query.filter(User.username != admin_user).order_by(User.xp_points.desc(), User.streak.desc()).limit(50).all()
        for idx, u in enumerate(top_users):
            # Calculate accuracy from stats
            acc = u.stats.win_ratio if u.stats else 0.0
            leaderboard.append({
                "rank": idx + 1,
                "username": u.username,
                "xp_points": u.xp_points,
                "streak": u.streak,
                "accuracy": round(acc, 1),
                "badge": u.badge
            })
    else:
        # Join User and Attempt to rank by total score within the period, excluding admin
        results = db.session.query(
            User,
            func.sum(Attempt.score).label('period_score'),
            func.avg(Attempt.accuracy).label('period_accuracy')
        ).join(Attempt, User.id == Attempt.user_id)\
         .filter(Attempt.submitted_at >= start_date)\
         .filter(User.username != admin_user)\
         .group_by(User.id)\
         .order_by(func.sum(Attempt.score).desc())\
         .limit(50).all()

        for idx, res in enumerate(results):
            u, period_score, period_accuracy = res
            leaderboard.append({
                "rank": idx + 1,
                "username": u.username,
                # Convert active period score to display equivalent XP or points
                "xp_points": int(period_score) * 10, 
                "streak": u.streak,
                "accuracy": round(float(period_accuracy), 1) if period_accuracy else 0.0,
                "badge": u.badge
            })

        # Fallback: If no activity exists for today/weekly, load all-time so leaderboard is never blank, excluding admin
        if not leaderboard:
            top_users = User.query.filter(User.username != admin_user).order_by(User.xp_points.desc()).limit(10).all()
            for idx, u in enumerate(top_users):
                acc = u.stats.win_ratio if u.stats else 0.0
                leaderboard.append({
                    "rank": idx + 1,
                    "username": u.username,
                    "xp_points": u.xp_points,
                    "streak": u.streak,
                    "accuracy": round(acc, 1),
                    "badge": u.badge
                })

    return jsonify(leaderboard), 200
