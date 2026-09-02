from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

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
