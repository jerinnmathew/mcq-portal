import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from sqlalchemy.orm import joinedload, load_only
from datetime import datetime, timedelta

from backend.models import db, User, Attempt, Stats
from backend.extensions import cache

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Returns aggregated student statistics and recent attempt history for dashboard charts."""
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"msg": "User not found"}), 404

    stats = db.session.get(Stats, user.id)
    if not stats:
        stats = Stats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()

    recent_attempts = (
        Attempt.query
        .filter_by(user_id=user.id)
        .order_by(Attempt.submitted_at.desc())
        .limit(10)
        .all()
    )
    recent_attempts.reverse()

    return jsonify({
        "user": user.to_dict(),
        "stats": stats.to_dict(),
        "recent_attempts": [a.to_dict() for a in recent_attempts],
    }), 200


@stats_bp.route('/leaderboard', methods=['GET'])
@cache.cached(timeout=60, key_prefix=lambda: f"leaderboard_{request.args.get('filter', 'all-time')}")
def get_leaderboard():
    """Returns global leaderboard ranks with Today, Weekly, and All-Time filters.

    Results are cached for 60 seconds — leaderboard does not need real-time precision
    and caching eliminates the most expensive query on the platform.
    """
    time_filter = request.args.get('filter', 'all-time').lower()
    now = datetime.utcnow()

    admin_user = os.environ.get('ADMIN_USERNAME', '')
    leaderboard = []

    if time_filter == 'today':
        start_date = datetime(now.year, now.month, now.day)
    elif time_filter == 'weekly':
        start_date = now - timedelta(days=7)
    else:
        time_filter = 'all-time'
        start_date = None

    if time_filter == 'all-time':
        # Single JOIN query — no N+1 on stats
        top_users = (
            User.query
            .options(
                load_only(User.id, User.username, User.xp_points, User.streak, User.badge),
                joinedload(User.stats).load_only(Stats.win_ratio),
            )
            .filter(User.username != admin_user)
            .order_by(User.xp_points.desc(), User.streak.desc())
            .limit(50)
            .all()
        )
        for idx, u in enumerate(top_users):
            leaderboard.append({
                "rank": idx + 1,
                "username": u.username,
                "xp_points": u.xp_points,
                "streak": u.streak,
                "accuracy": round(u.stats.win_ratio, 1) if u.stats else 0.0,
                "badge": u.badge,
            })
    else:
        # Period leaderboard via aggregate join — one query
        results = (
            db.session.query(
                User.id,
                User.username,
                User.streak,
                User.badge,
                func.sum(Attempt.score).label('period_score'),
                func.avg(Attempt.accuracy).label('period_accuracy'),
            )
            .join(Attempt, User.id == Attempt.user_id)
            .filter(Attempt.submitted_at >= start_date)
            .filter(User.username != admin_user)
            .group_by(User.id, User.username, User.streak, User.badge)
            .order_by(func.sum(Attempt.score).desc())
            .limit(50)
            .all()
        )

        for idx, res in enumerate(results):
            leaderboard.append({
                "rank": idx + 1,
                "username": res.username,
                "xp_points": int(res.period_score) * 10,
                "streak": res.streak,
                "accuracy": round(float(res.period_accuracy), 1) if res.period_accuracy else 0.0,
                "badge": res.badge,
            })

        # Fallback to all-time when no activity exists for the period
        if not leaderboard:
            top_users = (
                User.query
                .options(
                    load_only(User.id, User.username, User.xp_points, User.streak, User.badge),
                    joinedload(User.stats).load_only(Stats.win_ratio),
                )
                .filter(User.username != admin_user)
                .order_by(User.xp_points.desc())
                .limit(10)
                .all()
            )
            for idx, u in enumerate(top_users):
                leaderboard.append({
                    "rank": idx + 1,
                    "username": u.username,
                    "xp_points": u.xp_points,
                    "streak": u.streak,
                    "accuracy": round(u.stats.win_ratio, 1) if u.stats else 0.0,
                    "badge": u.badge,
                })

    return jsonify(leaderboard), 200
