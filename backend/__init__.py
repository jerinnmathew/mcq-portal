import os
from flask import Flask, send_from_directory, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from sqlalchemy import text

from backend.config import Config
from backend.models import db, User, Stats
from backend.extensions import cache

jwt = JWTManager()


def create_app(config_class=Config):
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    app.config.from_object(config_class)

    if not app.config.get('DEBUG'):
        config_class.validate()

    CORS(app)
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)

    from backend.blueprints.auth import auth_bp
    from backend.blueprints.quiz import quiz_bp
    from backend.blueprints.stats import stats_bp
    from backend.blueprints.admin import admin_bp
    from backend.blueprints.sso import sso_bp
    from backend.models import Subject

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(quiz_bp, url_prefix='/api/quiz')
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(sso_bp)

    @app.route('/api/subjects', methods=['GET'])
    @cache.cached(timeout=300, key_prefix='subjects_list')
    def list_subjects():
        subjects = Subject.query.order_by(Subject.semester.asc(), Subject.name.asc()).all()
        return {
            "subjects": [{"id": s.id, "name": s.name, "semester": s.semester} for s in subjects]
        }, 200

    padikkunnundo_url = app.config.get("PADIKKUNNUNDO_URL", "https://padikkunnundo.app").rstrip("/")

    def _get_authenticated_user():
        from backend.utils.helpers import get_current_user
        return get_current_user()

    def _serve_protected(filename, clean_route):
        if request.path.endswith('.html'):
            return redirect(clean_route, code=301)
        user = _get_authenticated_user()
        if not user:
            return redirect(padikkunnundo_url, code=302)
        resp = app.make_response(send_from_directory(app.static_folder, filename))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    @app.route('/login')
    @app.route('/login.html')
    @app.route('/register')
    @app.route('/register.html')
    def serve_login():
        return redirect(padikkunnundo_url, code=302)

    @app.route('/dashboard')
    @app.route('/dashboard.html')
    def serve_dashboard():
        return _serve_protected('dashboard.html', '/dashboard')

    @app.route('/admin')
    @app.route('/admin.html')
    def serve_admin():
        if request.path.endswith('.html'):
            return redirect('/admin', code=301)
        user = _get_authenticated_user()
        admin_username = os.environ.get('ADMIN_USERNAME')
        if not user or not admin_username or user.username != admin_username:
            return redirect(padikkunnundo_url, code=302)
        resp = app.make_response(send_from_directory(app.static_folder, 'admin.html'))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    @app.route('/quiz')
    @app.route('/quiz.html')
    def serve_quiz():
        return _serve_protected('quiz.html', '/quiz')

    @app.route('/results')
    @app.route('/results.html')
    def serve_results():
        return _serve_protected('results.html', '/results')

    @app.route('/about')
    @app.route('/about.html')
    def serve_about():
        if request.path.endswith('.html'):
            return redirect('/about', code=301)
        return send_from_directory(app.static_folder, 'about.html')

    @app.route('/')
    @app.route('/index.html')
    def serve_index():
        if request.path.endswith('.html'):
            return redirect('/', code=301)
        return send_from_directory(app.static_folder, 'index.html')

    with app.app_context():
        run_migrations(app)
        db.create_all()
        seed_subjects(app)
        seed_admin(app)
        remove_demo_user(app)

    return app


def run_migrations(app):
    """Apply additive schema changes to existing tables without dropping data."""
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    existing_columns = {col['name'] for col in inspector.get_columns('users')}

    user_migrations = [
        ('email',          'VARCHAR(255)', True,  None),
        ('name',           'VARCHAR(255)', True,  None),
        ('college',        'VARCHAR(255)', True,  None),
        ('sso_id',         'INTEGER',      True,  None),
        ('is_sso_user',    'BOOLEAN',      False, 'false'),
        ('last_sso_login', 'TIMESTAMP',    True,  None),
    ]

    for col_name, col_type, nullable, default in user_migrations:
        if col_name not in existing_columns:
            try:
                null_clause    = "" if nullable else "NOT NULL"
                default_clause = f"DEFAULT {default}" if default is not None else ""
                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type} {null_clause} {default_clause}"
                db.session.execute(text(sql.strip()))
                db.session.commit()
                app.logger.info(f"Migration: added '{col_name}' to users.")
            except Exception as e:
                db.session.rollback()
                app.logger.debug(f"Migration skip '{col_name}': {e}")

    try:
        stats_columns = {col['name'] for col in inspector.get_columns('stats')}

        if 'user_id' not in stats_columns:
            db.session.execute(text(
                "ALTER TABLE stats ADD COLUMN user_id INTEGER NOT NULL "
                "REFERENCES users(id) ON DELETE CASCADE"
            ))
            db.session.commit()
            app.logger.info("Migration: added 'user_id' to stats.")

        for col_name in ('total_correct', 'total_answered'):
            if col_name not in stats_columns:
                try:
                    db.session.execute(text(
                        f"ALTER TABLE stats ADD COLUMN {col_name} INTEGER NOT NULL DEFAULT 0"
                    ))
                    db.session.commit()
                    app.logger.info(f"Migration: added '{col_name}' to stats.")
                except Exception as e:
                    db.session.rollback()
                    app.logger.debug(f"Migration skip '{col_name}': {e}")

        _backfill_running_totals(app)

    except Exception:
        pass


def _backfill_running_totals(app):
    """Populate total_correct/total_answered for existing users from historical attempts."""
    from sqlalchemy import func
    from backend.models import Attempt

    try:
        stale = (
            db.session.query(Stats.user_id)
            .filter(Stats.total_answered == 0, Stats.total_attempts > 0)
            .all()
        )
        if not stale:
            return

        stale_ids = [row[0] for row in stale]
        aggregates = (
            db.session.query(
                Attempt.user_id,
                func.sum(Attempt.score).label('tc'),
                func.sum(Attempt.total_questions).label('ta'),
            )
            .filter(Attempt.user_id.in_(stale_ids))
            .group_by(Attempt.user_id)
            .all()
        )

        for user_id, tc, ta in aggregates:
            db.session.query(Stats).filter(Stats.user_id == user_id).update(
                {"total_correct": int(tc or 0), "total_answered": int(ta or 0)},
                synchronize_session=False,
            )

        if aggregates:
            db.session.commit()
            app.logger.info(f"Backfilled running totals for {len(aggregates)} users.")
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Running-total backfill skipped: {e}")


def seed_subjects(app):
    """Seed subjects only on a completely empty table (first deploy)."""
    from backend.models import Subject, SUBJECTS

    if Subject.query.count() > 0:
        return
    for name, semester in SUBJECTS:
        db.session.add(Subject(name=name, semester=semester))
    try:
        db.session.commit()
        app.logger.info(f"Seeded {len(SUBJECTS)} subjects.")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to seed subjects: {e}")


def remove_demo_user(app):
    """Remove the demo student account if it still exists."""
    try:
        demo = User.query.filter_by(username="demo_student").first()
        if demo:
            db.session.delete(demo)
            db.session.commit()
            app.logger.info("Purged demo_student.")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error purging demo user: {e}")


def seed_admin(app):
    """Create or update the admin account from ADMIN_USERNAME / ADMIN_PASSWORD env vars."""
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_pass = os.environ.get('ADMIN_PASSWORD')

    if not admin_user or not admin_pass:
        app.logger.warning("ADMIN_USERNAME or ADMIN_PASSWORD not set — skipping admin setup.")
        return

    legacy_admin = User.query.filter_by(username='admin').first()
    if legacy_admin:
        try:
            legacy_admin.username = admin_user
            legacy_admin.set_password(admin_pass)
            db.session.commit()
            app.logger.info(f"Migrated legacy admin → {admin_user}")
            return
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to migrate legacy admin: {e}")

    if not User.query.filter_by(username=admin_user).first():
        try:
            new_admin = User(username=admin_user)
            new_admin.set_password(admin_pass)
            db.session.add(new_admin)
            db.session.flush()
            db.session.add(Stats(
                user_id=new_admin.id,
                highest_score=0, average_score=0.0, total_attempts=0,
                win_ratio=0.0, current_streak=0, total_correct=0, total_answered=0,
            ))
            db.session.commit()
            app.logger.info(f"Seeded admin: {admin_user}")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to seed admin: {e}")
