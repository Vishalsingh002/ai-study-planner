from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    study_goal_hours = db.Column(db.Float, default=4.0)
    profile_image = db.Column(db.String(255), default='avatar-1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subjects = db.relationship('Subject', backref='user', lazy=True, cascade="all, delete-orphan")
    progress_records = db.relationship('Progress', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def get_study_streak(self):
        records = Progress.query.filter_by(user_id=self.id).filter(Progress.study_hours > 0).order_by(Progress.date.desc()).all()
        if not records:
            return 0

        logged_dates = {r.date for r in records}
        today = date.today()
        streak = 0

        current_check = today if today in logged_dates else today - timedelta(days=1)
        if current_check not in logged_dates:
            return 0

        while current_check in logged_dates:
            streak += 1
            current_check -= timedelta(days=1)

        return streak


class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default='#4f46e5')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='subject', lazy=True, cascade="all, delete-orphan")

    @property
    def total_tasks(self):
        return len(self.tasks)

    @property
    def completed_tasks(self):
        return len([t for t in self.tasks if t.status == 'Completed'])

    @property
    def completion_rate(self):
        if self.total_tasks == 0:
            return 0.0
        return round((self.completed_tasks / self.total_tasks) * 100, 1)


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    task_name = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(20), default='Pending')
    estimated_hours = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_overdue(self):
        return self.status != 'Completed' and self.deadline < date.today()


class Progress(db.Model):
    __tablename__ = 'progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    study_hours = db.Column(db.Float, default=0.0)
    completion_percentage = db.Column(db.Float, default=0.0)
    date = db.Column(db.Date, default=date.today, nullable=False)
    notes = db.Column(db.String(255), nullable=True)
