import os
import uuid
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Subject, Task, Progress
from forms import (RegistrationForm, LoginForm, SubjectForm, TaskForm, 
                   ProgressLogForm, ProfileForm, ChangePasswordForm)
from utils.recommendation_engine import AIStudyRecommendationEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'study-planner-secret-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your study planner.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Auto-add profile_image column if missing in SQLite
with app.app_context():
    db.create_all()
    try:
        db_path = os.path.join(app.root_path, 'database.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            cols = [col[1] for col in cursor.fetchall()]
            if 'profile_image' not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN profile_image TEXT DEFAULT 'avatar-1'")
                conn.commit()
            conn.close()
    except Exception as e:
        print(f"Auto-migration: {e}")

# --- Landing & Auth ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip()
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Seed initial subjects
        default_subjects = [
            ("Machine Learning", "#4f46e5"),
            ("Data Structures & Algorithms", "#06b6d4"),
            ("Operating Systems", "#10b981")
        ]
        for name, color in default_subjects:
            db.session.add(Subject(user_id=user.id, subject_name=name, color=color))
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Dashboard ---

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id
    subjects = Subject.query.filter_by(user_id=user_id).all()
    tasks = Task.query.join(Subject).filter(Subject.user_id == user_id).all()

    total_subjects = len(subjects)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == 'Completed')
    pending_tasks = sum(1 for t in tasks if t.status != 'Completed')

    today = date.today()
    today_rec = Progress.query.filter_by(user_id=user_id, date=today).first()
    daily_study_hours = today_rec.study_hours if today_rec else 0.0

    week_start = today - timedelta(days=6)
    week_records = Progress.query.filter(
        Progress.user_id == user_id,
        Progress.date >= week_start,
        Progress.date <= today
    ).all()
    weekly_hours = sum(r.study_hours for r in week_records)
    weekly_target = current_user.study_goal_hours * 7
    weekly_completion_pct = min(100.0, round((weekly_hours / weekly_target * 100), 1)) if weekly_target > 0 else 0

    streak = current_user.get_study_streak()
    ai_subject_rec = AIStudyRecommendationEngine.suggest_next_subject(user_id)
    prioritized_tasks = AIStudyRecommendationEngine.prioritize_tasks(user_id, limit=5)
    daily_schedule = AIStudyRecommendationEngine.generate_daily_schedule(user_id, current_user.study_goal_hours)
    productivity_tips = AIStudyRecommendationEngine.generate_productivity_tips(current_user)

    log_form = ProgressLogForm()
    log_form.date.data = today

    return render_template(
        'dashboard.html',
        total_subjects=total_subjects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        daily_study_hours=daily_study_hours,
        weekly_hours=weekly_hours,
        weekly_completion_pct=weekly_completion_pct,
        streak=streak,
        ai_subject_rec=ai_subject_rec,
        prioritized_tasks=prioritized_tasks,
        daily_schedule=daily_schedule,
        productivity_tips=productivity_tips,
        log_form=log_form,
        today=today
    )

# --- Tasks & Planner ---

@app.route('/planner')
@login_required
def planner():
    user_id = current_user.id
    subjects = Subject.query.filter_by(user_id=user_id).order_by(Subject.subject_name).all()

    subject_filter = request.args.get('subject_id', type=int)
    priority_filter = request.args.get('priority')
    status_filter = request.args.get('status')
    search_query = request.args.get('q', '').strip()

    task_query = Task.query.join(Subject).filter(Subject.user_id == user_id)

    if subject_filter:
        task_query = task_query.filter(Task.subject_id == subject_filter)
    if priority_filter and priority_filter != 'All':
        task_query = task_query.filter(Task.priority == priority_filter)
    if status_filter and status_filter != 'All':
        task_query = task_query.filter(Task.status == status_filter)
    if search_query:
        task_query = task_query.filter(Task.task_name.ilike(f'%{search_query}%'))

    tasks = task_query.order_by(Task.deadline.asc()).all()

    task_form = TaskForm()
    task_form.subject_id.choices = [(s.id, s.subject_name) for s in subjects] if subjects else [(0, 'No Subjects Available')]
    task_form.deadline.data = date.today() + timedelta(days=2)

    subject_form = SubjectForm()

    return render_template(
        'planner.html',
        subjects=subjects,
        tasks=tasks,
        task_form=task_form,
        subject_form=subject_form,
        subject_filter=subject_filter,
        priority_filter=priority_filter,
        status_filter=status_filter,
        search_query=search_query
    )

@app.route('/subject/add', methods=['POST'])
@login_required
def add_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            user_id=current_user.id,
            subject_name=form.subject_name.data.strip(),
            color=form.color.data
        )
        db.session.add(subject)
        db.session.commit()
        flash(f'Subject "{subject.subject_name}" added.', 'success')
    return redirect(url_for('planner'))

@app.route('/subject/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted.', 'info')
    return redirect(url_for('planner'))

@app.route('/task/add', methods=['POST'])
@login_required
def add_task():
    form = TaskForm()
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    form.subject_id.choices = [(s.id, s.subject_name) for s in subjects]

    if form.validate_on_submit():
        task = Task(
            subject_id=form.subject_id.data,
            task_name=form.task_name.data.strip(),
            deadline=form.deadline.data,
            priority=form.priority.data,
            status=form.status.data,
            estimated_hours=form.estimated_hours.data
        )
        if task.status == 'Completed':
            task.completed_at = datetime.utcnow()
        db.session.add(task)
        db.session.commit()
        flash(f'Task "{task.task_name}" created.', 'success')
    else:
        flash('Failed to create task. Verify all fields.', 'danger')
    return redirect(url_for('planner'))

@app.route('/task/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task_status(task_id):
    task = Task.query.join(Subject).filter(Task.id == task_id, Subject.user_id == current_user.id).first_or_404()
    if task.status == 'Completed':
        task.status = 'Pending'
        task.completed_at = None
    else:
        task.status = 'Completed'
        task.completed_at = datetime.utcnow()
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': task.status})
    return redirect(request.referrer or url_for('planner'))

@app.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.join(Subject).filter(Task.id == task_id, Subject.user_id == current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'info')
    return redirect(url_for('planner'))

# --- Progress & Analytics ---

@app.route('/progress/log', methods=['POST'])
@login_required
def log_progress():
    form = ProgressLogForm()
    if form.validate_on_submit():
        record = Progress.query.filter_by(user_id=current_user.id, date=form.date.data).first()
        if record:
            record.study_hours += form.study_hours.data
            if form.notes.data:
                record.notes = (record.notes or "") + " " + form.notes.data
        else:
            record = Progress(
                user_id=current_user.id,
                date=form.date.data,
                study_hours=form.study_hours.data,
                notes=form.notes.data
            )
            db.session.add(record)

        record.completion_percentage = min(100.0, round((record.study_hours / current_user.study_goal_hours) * 100, 1))
        db.session.commit()
        flash(f'Logged {form.study_hours.data} hours successfully!', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/reports')
@login_required
def reports():
    user_id = current_user.id
    tasks = Task.query.join(Subject).filter(Subject.user_id == user_id).all()
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == 'Completed')
    completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0

    all_progress = Progress.query.filter_by(user_id=user_id).all()
    total_hours = sum(p.study_hours for p in all_progress)
    ai_recommendations = AIStudyRecommendationEngine.recommend_study_hours(user_id)

    return render_template(
        'reports.html',
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion_rate=completion_rate,
        total_hours=total_hours,
        ai_recommendations=ai_recommendations
    )

@app.route('/api/analytics-data')
@login_required
def analytics_data():
    user_id = current_user.id
    today = date.today()

    weekly_labels = []
    weekly_study_data = []
    weekly_goal_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        weekly_labels.append(day.strftime("%a"))
        rec = Progress.query.filter_by(user_id=user_id, date=day).first()
        weekly_study_data.append(rec.study_hours if rec else 0.0)
        weekly_goal_data.append(current_user.study_goal_hours)

    subjects = Subject.query.filter_by(user_id=user_id).all()
    subject_labels = [s.subject_name for s in subjects]
    subject_completion = [s.completion_rate for s in subjects]
    subject_colors = [s.color for s in subjects]

    tasks = Task.query.join(Subject).filter(Subject.user_id == user_id).all()
    completed_count = sum(1 for t in tasks if t.status == 'Completed')
    in_progress_count = sum(1 for t in tasks if t.status == 'In Progress')
    pending_count = sum(1 for t in tasks if t.status == 'Pending' and not t.is_overdue)
    overdue_count = sum(1 for t in tasks if t.is_overdue)

    monthly_labels = []
    monthly_hours_data = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        monthly_labels.append(day.strftime("%d %b"))
        rec = Progress.query.filter_by(user_id=user_id, date=day).first()
        monthly_hours_data.append(rec.study_hours if rec else 0.0)

    return jsonify({
        'weekly': {'labels': weekly_labels, 'study_hours': weekly_study_data, 'target_hours': weekly_goal_data},
        'subjects': {'labels': subject_labels, 'rates': subject_completion, 'colors': subject_colors},
        'task_breakdown': {'labels': ['Completed', 'In Progress', 'Pending', 'Overdue'], 'counts': [completed_count, in_progress_count, pending_count, overdue_count]},
        'monthly': {'labels': monthly_labels, 'hours': monthly_hours_data}
    })

# --- Profile & Settings (Avatar & Photo Update) ---

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    password_form = ChangePasswordForm()

    if request.method == 'POST' and 'update_profile' in request.form:
        new_name = request.form.get('name', '').strip()
        new_email = request.form.get('email', '').strip().lower()
        try:
            new_goal = float(request.form.get('study_goal_hours', 4.0))
        except ValueError:
            new_goal = current_user.study_goal_hours

        existing = User.query.filter(User.email == new_email, User.id != current_user.id).first()
        if existing:
            flash('This email is already registered by another account.', 'danger')
        elif not new_name or not new_email:
            flash('Name and Email cannot be empty.', 'danger')
        else:
            # 1. Check if user selected a Preset Avatar
            selected_avatar = request.form.get('selected_avatar')
            if selected_avatar:
                current_user.profile_image = selected_avatar

            # 2. Check if user uploaded a custom photo
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and file.filename != '':
                    allowed_exts = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
                    ext = file.filename.rsplit('.', 1)[-1].lower()
                    if ext in allowed_exts:
                        unique_filename = f"user_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                        upload_folder = os.path.join(app.root_path, 'static', 'profile_pics')
                        os.makedirs(upload_folder, exist_ok=True)
                        file.save(os.path.join(upload_folder, unique_filename))
                        current_user.profile_image = unique_filename
                    else:
                        flash('Invalid image format. Supported: PNG, JPG, WEBP.', 'warning')

            current_user.name = new_name
            current_user.email = new_email
            current_user.study_goal_hours = max(0.5, min(new_goal, 16.0))
            db.session.commit()
            flash('Profile & Avatar updated successfully! 🎉', 'success')
            return redirect(url_for('profile'))

    tasks = Task.query.join(Subject).filter(Subject.user_id == current_user.id).all()
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == 'Completed')
    all_progress = Progress.query.filter_by(user_id=current_user.id).all()
    total_hours = round(sum(p.study_hours for p in all_progress), 1)

    return render_template(
        'profile.html',
        password_form=password_form,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_hours=total_hours
    )

@app.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password changed successfully! 🔐', 'success')
        else:
            flash('Current password is incorrect.', 'danger')
    else:
        flash('Password change failed. Ensure passwords match and are at least 6 characters.', 'danger')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
