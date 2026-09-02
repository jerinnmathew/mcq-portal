import random

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import load_only

from backend.models import db, User, MCQ, Attempt, Stats
from backend.extensions import cache
from backend.utils.helpers import calculate_streak_and_xp, rate_limit

quiz_bp = Blueprint('quiz', __name__)


@quiz_bp.route('/questions', methods=['GET'])
@rate_limit(limit=30, period=60)
def get_questions():
    """Fetches a randomised set of MCQ questions. Correct answers are excluded for security.

    The full question ID pool for each subject is cached for 5 minutes. Random
    sampling happens in Python against the cached list, so only the N selected
    question rows are ever fetched from the database.
    """
    subject_id = request.args.get('subject_id', type=int)
    category = request.args.get('category')
    limit = max(10, min(request.args.get('limit', 10, type=int), 30))

    pool_ids = _get_question_pool(subject_id, category)

    if not pool_ids:
        return jsonify([]), 200

    sampled_ids = random.sample(pool_ids, k=min(limit, len(pool_ids)))
    questions = (
        MCQ.query
        .filter(MCQ.id.in_(sampled_ids))
        .all()
    )

    return jsonify([q.to_dict(include_correct=False) for q in questions]), 200


@cache.memoize(timeout=300)
def _get_question_pool(subject_id, category):
    """Return a list of MCQ IDs matching the filter. Cached for 5 minutes.

    Uses memoize (rather than cached) so each (subject_id, category) combination
    gets its own cache entry automatically.
    """
    query = db.session.query(MCQ.id)

    if subject_id:
        query = query.filter(MCQ.subject_id == subject_id)
    elif category and category != 'All':
        query = query.filter(MCQ.category == category)

    return [row[0] for row in query.all()]


@quiz_bp.route('/submit', methods=['POST'])
@jwt_required()
@rate_limit(limit=15, period=60)
def submit_quiz():
    """Submits student answers, grades the quiz server-side, awards XP, and updates statistics.

    Win-ratio is maintained as a running total (total_correct / total_answered)
    on the Stats row — no full aggregate query over all historical attempts.
    """
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"msg": "User not found"}), 404

    data = request.get_json() or {}
    user_answers = data.get('answers', {})

    if not user_answers:
        return jsonify({"msg": "No answers provided"}), 400

    mcq_ids = [int(qid) for qid in user_answers.keys()]
    mcq_rows = (
        MCQ.query
        .filter(MCQ.id.in_(mcq_ids))
        .options(load_only(
            MCQ.id, MCQ.question,
            MCQ.option_a, MCQ.option_b, MCQ.option_c, MCQ.option_d,
            MCQ.correct_answer, MCQ.category, MCQ.subject_id,
        ))
        .all()
    )
    mcq_map = {
        row.id: {
            "id": row.id,
            "question": row.question,
            "option_a": row.option_a,
            "option_b": row.option_b,
            "option_c": row.option_c,
            "option_d": row.option_d,
            "correct_answer": row.correct_answer,
            "category": row.category,
            "subject_id": row.subject_id,
        }
        for row in mcq_rows
    }

    correct_count = 0
    total_questions = len(mcq_ids)
    breakdown = []

    for qid in mcq_ids:
        mcq = mcq_map.get(qid)
        if not mcq:
            continue
        user_ans = user_answers.get(str(qid))
        is_correct = user_ans == mcq["correct_answer"]
        if is_correct:
            correct_count += 1
        breakdown.append({
            "id": mcq["id"],
            "question": mcq["question"],
            "option_a": mcq["option_a"],
            "option_b": mcq["option_b"],
            "option_c": mcq["option_c"],
            "option_d": mcq["option_d"],
            "user_answer": user_ans,
            "correct_answer": mcq["correct_answer"],
            "is_correct": is_correct,
        })

    accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0

    try:
        last_attempt = (
            Attempt.query
            .filter_by(user_id=user.id)
            .order_by(Attempt.submitted_at.desc())
            .first()
        )
        new_streak, xp_earned, new_badge = calculate_streak_and_xp(
            user, correct_count, total_questions, last_attempt
        )

        user.streak = new_streak
        user.xp_points += xp_earned
        user.badge = new_badge

        db.session.add(Attempt(
            user_id=user.id,
            score=correct_count,
            total_questions=total_questions,
            accuracy=accuracy,
        ))

        stats = user.stats
        if not stats:
            stats = Stats(
                user_id=user.id,
                total_correct=0,
                total_answered=0,
            )
            db.session.add(stats)

        if correct_count > stats.highest_score:
            stats.highest_score = correct_count

        old_attempts = stats.total_attempts
        new_attempts = old_attempts + 1
        stats.total_attempts = new_attempts
        stats.average_score = (
            (stats.average_score * old_attempts) + correct_count
        ) / new_attempts

        # O(1) running-total win ratio — no aggregate query needed
        stats.total_correct = (stats.total_correct or 0) + correct_count
        stats.total_answered = (stats.total_answered or 0) + total_questions
        stats.win_ratio = (
            stats.total_correct / stats.total_answered * 100
            if stats.total_answered > 0 else 0.0
        )
        stats.current_streak = new_streak

        db.session.commit()

        return jsonify({
            "msg": "Quiz submitted successfully",
            "score": correct_count,
            "total_questions": total_questions,
            "accuracy": round(accuracy, 2),
            "xp_earned": xp_earned,
            "new_streak": new_streak,
            "badge": new_badge,
            "breakdown": breakdown,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Submission failed: {str(e)}"}), 500
