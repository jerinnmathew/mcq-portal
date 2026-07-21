import os
from flask import Flask, send_from_directory, redirect, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
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
        db.create_all()
        seed_subjects()
        seed_admin()

    return app

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
