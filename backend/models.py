from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Active list of subjects used for seeding and subject-specific question grouping.
# Only the name and semester are required for the app-level subject list.
SUBJECTS = [
    ("Discrete Mathematics", 1),
    ("Digital Fundamentals", 1),
    ("Fundamentals of Programming Using C++", 1),
    ("English for Science", 1),
    ("Cyber Laws and Security", 1),
    ("Software Lab in C++", 1),
    ("Spanish 1", 1),
    ("French 1", 1),
    ("Indian Constitution: Legal and Ethical Perspectives", 2),
    ("Web Technology", 2),
    ("Operating Systems", 2),
    ("Data Structures", 2),
    ("Mathematics Foundations to Computer Science ", 2),
    ("AEC — English", 2),
    ("Spanish 2", 2),
    ("French 2", 2),
    ("Python Programming", 3),
    ("Database Management Systems", 3),
    ("Design and Analysis of Algorithms", 3),
    ("Software Engineering", 3),
    ("Quantitative Techniques", 3),
    ("Feature Engineering", 3),
    ("Introduction to Cyber Security", 3),
    ("Interactive Web Application Development Using PHP and MySQL ", 3),
    ("Basics of Data Analytics Using Spreadsheet ", 3),
    ("Object Oriented Programming Using Java", 4),
    ("Design Thinking and Innovation", 4),
    ("Entrepreneurship and Startup Ecosystem", 4),
    ("Probability Distributions and Statistical Inference", 4),
    ("Artificial Intelligence", 4),
    ("Network Simulation", 4),
    ("Intro to ML", 4),
    ("Data Visualization ", 4),
    ("Web Application Development Using Node.js and Express.js ", 4)
]

class User(db.Model):
    """User representation representing registered students."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    streak = db.Column(db.Integer, default=0, nullable=False)
    xp_points = db.Column(db.Integer, default=0, nullable=False)
    badge = db.Column(db.String(50), default='Bronze', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # SSO fields
    email = db.Column(db.String(255), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=True)
    college = db.Column(db.String(255), nullable=True)
    sso_id = db.Column(db.Integer, unique=True, nullable=True, index=True)
    is_sso_user = db.Column(db.Boolean, nullable=False, default=False)
    last_sso_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    attempts = db.relationship('Attempt', backref='user', lazy=True, cascade="all, delete-orphan")
    stats = db.relationship('Stats', backref='user', uselist=False, lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        """Hashes the password and saves it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Serializes user fields for JSON API consumption."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "name": self.name,
            "college": self.college,
            "sso_id": self.sso_id,
            "is_sso_user": self.is_sso_user,
            "streak": self.streak,
            "xp_points": self.xp_points,
            "badge": self.badge,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_sso_login": self.last_sso_login.isoformat() if self.last_sso_login else None
        }


class MCQ(db.Model):
    """Model for Multiple Choice Questions."""
    __tablename__ = 'mcqs'

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', or 'D'
    category = db.Column(db.String(150), default='General', nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True)

    subject = db.relationship('Subject', back_populates='questions')

    def to_dict(self, include_correct=False):
        """Serializes MCQ fields. Excludes correct answer for students during quiz."""
        data = {
            "id": self.id,
            "question": self.question,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
            "category": self.category,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
            "semester": self.subject.semester if self.subject else None
        }
        if include_correct:
            data["correct_answer"] = self.correct_answer
        return data


class Subject(db.Model):
    """Represents an academic subject and semester grouping."""
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    semester = db.Column(db.Integer, nullable=False)

    questions = db.relationship('MCQ', back_populates='subject', lazy=True)

    def to_dict(self):
        """Serializes Subject fields."""
        return {
            "id": self.id,
            "name": self.name,
            "semester": self.semester
        }


class Attempt(db.Model):
    """Represents a completed quiz attempt by a student."""
    __tablename__ = 'attempts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False) # Number of correct answers
    total_questions = db.Column(db.Integer, nullable=False)
    accuracy = db.Column(db.Float, nullable=False) # (score / total_questions) * 100
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Serializes attempt data."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "score": self.score,
            "total_questions": self.total_questions,
            "accuracy": round(self.accuracy, 2),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None
        }


class Stats(db.Model):
    """Aggregated statistics for each user."""
    __tablename__ = 'stats'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    highest_score = db.Column(db.Integer, default=0, nullable=False)
    average_score = db.Column(db.Float, default=0.0, nullable=False)
    total_attempts = db.Column(db.Integer, default=0, nullable=False)
    win_ratio = db.Column(db.Float, default=0.0, nullable=False) # (total correct answers / total attempted questions) * 100
    current_streak = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        """Serializes aggregate stats data."""
        return {
            "user_id": self.user_id,
            "highest_score": self.highest_score,
            "average_score": round(self.average_score, 2),
            "total_attempts": self.total_attempts,
            "win_ratio": round(self.win_ratio, 2),
            "current_streak": self.current_streak
        }
