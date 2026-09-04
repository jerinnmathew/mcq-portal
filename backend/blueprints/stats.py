from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models import db, User, Stats

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Returns aggregated student statistics for the dashboard."""
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"msg": "User not found"}), 404

    stats = db.session.get(Stats, user.id)
    if not stats:
        stats = Stats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()

    return jsonify({
        "user": user.to_dict(),
        "stats": stats.to_dict(),
    }), 200
