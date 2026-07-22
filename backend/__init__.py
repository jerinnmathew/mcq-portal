import os
from datetime import datetime, timezone
from flask import Flask, send_from_directory, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from sqlalchemy import text

from backend.config import Config
from backend.models import db, MCQ, User, Stats

jwt = JWTManager()

def create_app(config_class=Config):
    # Map static folder to frontend for easy single-origin hosting
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    app.config.from_object(config_class)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    jwt.init_app(app)

    # Register blueprints
    from backend.blueprints.auth import auth_bp
    from backend.blueprints.quiz import quiz_bp
    from backend.blueprints.stats import stats_bp
    from backend.blueprints.admin import admin_bp
    from backend.blueprints.sso import sso_bp
    from backend.models import Subject, SUBJECTS

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(quiz_bp, url_prefix='/api/quiz')
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(sso_bp)

    @app.route('/api/subjects', methods=['GET'])
    def list_subjects():
        subjects = Subject.query.order_by(Subject.semester.asc(), Subject.name.asc()).all()
        return {
            "subjects": [
                {"id": s.id, "name": s.name, "semester": s.semester}
                for s in subjects
            ]
        }, 200

    @app.route('/admin')
    @app.route('/admin.html')
    def serve_admin():
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id)) if user_id else None
            admin_user = os.environ.get('ADMIN_USERNAME')
            if not admin_user:
                return redirect('/login.html')
            if not user or user.username != admin_user:
                return redirect('/login.html')
            if request.path.endswith('.html'):
                return redirect('/admin')
            return send_from_directory(app.static_folder, 'admin.html')
        except Exception:
            return redirect('/login.html')

    @app.route('/login')
    def serve_login():
        return send_from_directory(app.static_folder, 'login.html')

    @app.route('/dashboard')
    def serve_dashboard():
        return send_from_directory(app.static_folder, 'dashboard.html')

    # Serve index.html at root
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    # Initialize database and seed sample data
    with app.app_context():
        run_migrations()
        db.create_all()
        seed_subjects()
        seed_admin()
        seed_demo_user()

    return app

def run_migrations():
    """Add missing columns to existing tables without dropping data.
    This handles schema updates for deployments where db.create_all() won't alter existing tables."""
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    
    # Get existing columns in the users table
    existing_columns = {col['name'] for col in inspector.get_columns('users')}
    
    # Define migrations: (column_name, sql_type, nullable, default)
    migrations = [
        ('email', 'VARCHAR(255)', True, None),
        ('name', 'VARCHAR(255)', True, None),
        ('college', 'VARCHAR(255)', True, None),
        ('sso_id', 'INTEGER', True, None),
        ('is_sso_user', 'BOOLEAN', False, 'false'),
        ('last_sso_login', 'TIMESTAMP', True, None),
    ]

    for col_name, col_type, nullable, default in migrations:
        if col_name not in existing_columns:
            try:
                null_clause = "" if nullable else "NOT NULL"
                default_clause = f"DEFAULT {default}" if default is not None else ""
                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type} {null_clause} {default_clause}"
                db.session.execute(text(sql.strip()))
                db.session.commit()
                print(f"Migration: Added column '{col_name}' to users table.")
            except Exception as e:
                db.session.rollback()
                # Column may have been added by another process, ignore
                print(f"Migration note: Could not add column '{col_name}': {str(e)}")
    
    # Also check the stats table for new columns if needed
    try:
        stats_columns = {col['name'] for col in inspector.get_columns('stats')}
        # Stats table currently matches the model, but let's ensure user_id exists
        if 'user_id' not in stats_columns:
            db.session.execute(text(
                "ALTER TABLE stats ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE"
            ))
            db.session.commit()
            print("Migration: Added column 'user_id' to stats table.")
    except Exception:
        pass  # stats table might not exist yet, which is fine


def seed_subjects():
    """Seeds the subject table ONLY if the table is completely empty (first run)."""
    from backend.models import Subject, SUBJECTS

    # Only seed if the table has zero subjects (first-time setup)
    count = Subject.query.count()
    if count > 0:
        return

    for name, semester in SUBJECTS:
        subject = Subject(name=name, semester=semester)
        db.session.add(subject)
    try:
        db.session.commit()
        print(f"Seeded {len(SUBJECTS)} subjects into empty database.")
    except Exception as e:
        db.session.rollback()
        print(f"Failed to seed subjects: {str(e)}")


def seed_demo_user():
    """Seeds a demo user account for Semester 1 practice without SSO."""
    demo_username = "demo_student"
    demo_user = User.query.filter_by(username=demo_username).first()
    if demo_user:
        return

    try:
        demo = User(
            username=demo_username,
            email="demo@mcq-portal.local",
            name="Demo Student",
            password_hash=None,
            is_sso_user=False,
            streak=0,
            xp_points=0,
            badge="Bronze",
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(demo)
        db.session.flush()

        demo_stats = Stats(
            user_id=demo.id,
            highest_score=0,
            average_score=0.0,
            total_attempts=0,
            win_ratio=0.0,
            current_streak=0,
        )
        db.session.add(demo_stats)
        db.session.commit()
        print(f"Seeded demo user: {demo_username}")
    except Exception as e:
        db.session.rollback()
        print(f"Failed to seed demo user: {str(e)}")


def seed_admin():
    """Seeds default admin user if configured in environment and upgrades legacy admin accounts."""
    import os
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_pass = os.environ.get('ADMIN_PASSWORD')
    
    if not admin_user or not admin_pass:
        print("Warning: ADMIN_USERNAME or ADMIN_PASSWORD environment variables not set. Skipping admin account setup.")
        return
    
    # 1. Check for legacy 'admin' user and upgrade it
    legacy_admin = User.query.filter_by(username='admin').first()
    if legacy_admin:
        try:
            legacy_admin.username = admin_user
            legacy_admin.set_password(admin_pass)
            db.session.commit()
            print(f"Successfully upgraded legacy admin account to: {admin_user}")
            return
        except Exception as e:
            db.session.rollback()
            print(f"Failed to upgrade legacy admin: {str(e)}")
            
    # 2. If no legacy admin, make sure the new admin exists
    admin_record = User.query.filter_by(username=admin_user).first()
    if not admin_record:
        try:
            new_admin = User(username=admin_user)
            new_admin.set_password(admin_pass)
            db.session.add(new_admin)
            db.session.flush()

            admin_stats = Stats(
                user_id=new_admin.id,
                highest_score=0,
                average_score=0.0,
                total_attempts=0,
                win_ratio=0.0,
                current_streak=0
            )
            db.session.add(admin_stats)
            db.session.commit()
            print(f"Successfully seeded admin account: {admin_user}")
        except Exception as e:
            db.session.rollback()
            print(f"Failed to seed admin: {str(e)}")

def seed_questions():
    """No-op placeholder. All questions are imported through the admin interface."""
    return


def seed_design_thinking_questions():
    """No-op placeholder. All questions are imported through the admin interface."""
    return
