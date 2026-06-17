import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
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
    from backend.blueprints.ai_generator import ai_gen_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(quiz_bp, url_prefix='/api/quiz')
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(ai_gen_bp, url_prefix='/api/admin')

    # Serve index.html at root
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    # Initialize database and seed sample data
    with app.app_context():
        db.create_all()
        seed_admin()
        seed_questions()

    return app

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
    """Seeds initial high-quality MCQ questions if table is empty."""
    if MCQ.query.first() is not None:
        return # Already seeded

    sample_questions = [
        MCQ(
            question="Which database type is PostgreSQL classified as?",
            option_a="NoSQL Key-Value",
            option_b="Object-Relational DBMS",
            option_c="Graph Database",
            option_d="Wide-column Store",
            correct_answer="B",
            category="Databases",
            difficulty="Easy"
        ),
        MCQ(
            question="In Python Flask, what is a Blueprint used for?",
            option_a="To configure PostgreSQL connection pools",
            option_b="To package application routes into modular components",
            option_c="To encrypt JWT authorization payloads",
            option_d="To automate database migrations",
            correct_answer="B",
            category="Web Development",
            difficulty="Medium"
        ),
        MCQ(
            question="What is the primary function of Flask-JWT-Extended in a REST API?",
            option_a="Caching responses on the client side",
            option_b="Securing routes using JSON Web Tokens",
            option_c="Performing cross-origin resource sharing configuration",
            option_d="Validating SQL database transactions",
            correct_answer="B",
            category="Security",
            difficulty="Medium"
        ),
        MCQ(
            question="Which of the following describes the SQL Injection security vulnerability?",
            option_a="Running arbitrary client-side Javascript inside index.html",
            option_b="Injecting malicious SQL commands into database queries via user input",
            option_c="Overloading the backend server with consecutive HTTPS requests",
            option_d="Intercepting plain-text passwords over an insecure connection",
            correct_answer="B",
            category="Security",
            difficulty="Hard"
        ),
        MCQ(
            question="What is the time complexity of searching for an element in a balanced Binary Search Tree (BST)?",
            option_a="O(1)",
            option_b="O(n)",
            option_c="O(log n)",
            option_d="O(n log n)",
            correct_answer="C",
            category="Data Structures",
            difficulty="Medium"
        ),
        MCQ(
            question="Which HTTP header is commonly used to transmit JWT authorization tokens?",
            option_a="Content-Type",
            option_b="Accept",
            option_c="Authorization",
            option_d="X-Frame-Options",
            correct_answer="C",
            category="Web Development",
            difficulty="Easy"
        ),
        MCQ(
            question="What does CORS stand for in modern web security configurations?",
            option_a="Cross-Origin Resource Sharing",
            option_b="Client-Oriented Route Security",
            option_c="Centralized Object Relational Schema",
            option_d="Cached Online Request Storage",
            correct_answer="A",
            category="Security",
            difficulty="Easy"
        ),
        MCQ(
            question="Which protocol does WebSockets use for the initial connection handshake?",
            option_a="FTP",
            option_b="SMTP",
            option_c="HTTP",
            option_d="SSH",
            correct_answer="C",
            category="Web Development",
            difficulty="Hard"
        ),
        MCQ(
            question="In a relational database, what does ACID compliance guarantee?",
            option_a="High performance through indexing",
            option_b="Safe execution of transactions and data reliability",
            option_c="Automatic backup and replication",
            option_d="Dynamic scaling and schema-free writes",
            correct_answer="B",
            category="Databases",
            difficulty="Medium"
        ),
        MCQ(
            question="What is the purpose of the 'git merge' command?",
            option_a="Creates a new local repository",
            option_b="Integrates changes from one branch into another",
            option_c="Uploads local commits to a remote server",
            option_d="Deletes an unwanted commit permanently",
            correct_answer="B",
            category="Software Engineering",
            difficulty="Easy"
        )
    ]

    for q in sample_questions:
        db.session.add(q)
    db.session.commit()
    print("Successfully seeded 10 default high-quality MCQs.")
