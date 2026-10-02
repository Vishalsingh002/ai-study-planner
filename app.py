import os
import uuid
import json
import secrets
import urllib.request
import cloudinary
from cloudinary.uploader import upload
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from sqlalchemy import text
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from models import db, User, Subject, Task, Progress
from forms import (RegistrationForm, LoginForm, SubjectForm, TaskForm, 
                   ProgressLogForm, ProfileForm, ChangePasswordForm, ContactForm,
                   RequestResetForm, ResetPasswordForm)
from utils.recommendation_engine import AIStudyRecommendationEngine
from utils.mailer import send_reset_email


load_dotenv()  # local dev ke liye .env file se env vars load karega; Render pe ye no-op rahega

# Cloudinary configuration (if environment variables are present)
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

is_cloudinary_configured = bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)
if is_cloudinary_configured:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-insecure-secret-change-me')

# --- Database config: PostgreSQL (Render) / Local SQLite ---
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Standard Render PostgreSQL fix (postgres:// -> postgresql://)
    clean_db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = clean_db_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    print("Database: Using PostgreSQL database.")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    print("Database: Using SQLite database.")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your study planner.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Firebase Authentication Configuration & Helper ---
FIREBASE_CONFIG = {
    'apiKey': os.environ.get('FIREBASE_API_KEY', 'AIzaSyB9O-7D_yfeOUicy4znCzIm0ybne62tI0k'),
    'authDomain': os.environ.get('FIREBASE_AUTH_DOMAIN', 'studyai-academic.firebaseapp.com'),
    'projectId': os.environ.get('FIREBASE_PROJECT_ID', 'studyai-academic'),
    'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET', 'studyai-academic.firebasestorage.app'),
    'messagingSenderId': os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '185231950007'),
    'appId': os.environ.get('FIREBASE_APP_ID', '1:185231950007:web:e0a7ef780287d4149a8d32'),
    'measurementId': os.environ.get('FIREBASE_MEASUREMENT_ID', 'G-REEZJW3M8L')
}

@app.context_processor
def inject_firebase():
    return {'firebase_config': FIREBASE_CONFIG}

def verify_firebase_token(id_token):
    """
    Verifies Firebase JWT ID token directly against Google Identity Toolkit endpoint.
    Returns decoded user dictionary on success, or None on failure.
    """
    api_key = FIREBASE_CONFIG.get('apiKey')
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    payload = json.dumps({"idToken": id_token}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            users = data.get('users', [])
            if users:
                return users[0]
    except Exception as e:
        app.logger.warning(f"Firebase token verification failed: {e}")
    return None

# Auto-add profile_image column if missing (works safely for SQLite and PostgreSQL)
with app.app_context():
    try:
        db.create_all()
        with db.engine.connect() as conn:
            try:
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
                if cols and 'profile_image' not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_image TEXT DEFAULT 'avatar-1'"))
                    conn.commit()
            except Exception:
                pass
    except Exception as e:
        print(f"Database schema notice: {e}")
    finally:
        try:
            db.engine.dispose()
        except Exception:
            pass

# --- Landing & Auth ---

@app.route('/api/firebase-login', methods=['POST'])
def api_firebase_login():
    """
    Authenticates a user via Firebase Auth ID token and establishes Flask-Login session.
    Automatically creates the user in the database and seeds starter subjects if new.
    """
    data = request.get_json() or {}
    id_token = data.get('idToken')
    if not id_token:
        return jsonify({'success': False, 'message': 'Missing Firebase ID token'}), 400

    verified_user = verify_firebase_token(id_token)
    if not verified_user:
        return jsonify({'success': False, 'message': 'Invalid or expired Firebase authentication token'}), 401

    email = verified_user.get('email', '').lower().strip()
    if not email:
        return jsonify({'success': False, 'message': 'Firebase user does not have an associated email'}), 400

    name = data.get('name') or verified_user.get('displayName') or email.split('@')[0].capitalize()

    # Look up existing user in SQLite / PostgreSQL
    user = User.query.filter_by(email=email).first()
    if not user:
        try:
            user = User(
                name=name.strip(),
                email=email
            )
            # Secure random hash for internal DB field
            user.set_password(uuid.uuid4().hex)
            db.session.add(user)
            db.session.flush()

            # Seed default starter subjects
            default_subjects = [
                ("Machine Learning", "#4f46e5"),
                ("Data Structures & Algorithms", "#06b6d4"),
                ("Operating Systems", "#10b981")
            ]
            for sub_name, color in default_subjects:
                db.session.add(Subject(user_id=user.id, subject_name=sub_name, color=color))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating Firebase user in DB: {e}")
            return jsonify({'success': False, 'message': 'Failed to create student account in database.'}), 500

    # Sync photo URL if Google account has one and user has default avatar
    photo_url = verified_user.get('photoUrl')
    if photo_url and (not user.profile_image or user.profile_image.startswith('avatar-')):
        try:
            user.profile_image = photo_url
            db.session.commit()
        except Exception:
            db.session.rollback()

    remember = bool(data.get('remember', True))
    login_user(user, remember=remember)
    flash(f'Welcome, {user.name}!', 'success')
    return jsonify({
        'success': True,
        'redirect': url_for('dashboard'),
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
    })

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
        try:
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower().strip()
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            # Seed initial subjects
            default_subjects = [
                ("Machine Learning", "#4f46e5"),
                ("Data Structures & Algorithms", "#06b6d4"),
                ("Operating Systems", "#10b981")
            ]
            for name, color in default_subjects:
                db.session.add(Subject(user_id=user.id, subject_name=name, color=color))
            db.session.commit()

            # Ensure user is provisioned in Firebase Auth so Forgot Password works seamlessly
            api_key = FIREBASE_CONFIG.get('apiKey')
            if api_key:
                try:
                    signup_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}'
                    payload = {
                        'email': user.email,
                        'password': form.password.data,
                        'displayName': user.name,
                        'returnSecureToken': False
                    }
                    req = urllib.request.Request(
                        signup_url,
                        data=json.dumps(payload).encode('utf-8'),
                        headers={'Content-Type': 'application/json'}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=5):
                            pass
                    except urllib.error.HTTPError:
                        pass
                except Exception as fb_err:
                    app.logger.warning(f"Firebase auto-registration sync notice: {fb_err}")

            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Registration error: {e}")
            flash('Error creating account. Please verify database connection or try another email.', 'danger')
    elif request.method == 'POST' and form.errors:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{err}", 'danger')
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower().strip()).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                flash(f'Welcome back, {user.name}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
        except Exception as e:
            app.logger.error(f"Login database error: {e}")
            flash('Database connectivity issue. Please try again in a few moments.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Password Reset Flow ---

def get_reset_serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'])

def generate_reset_token(email):
    s = get_reset_serializer()
    return s.dumps(email, salt='studyai-password-reset')

def verify_reset_token(token, max_age=900):
    """Verifies timed token (default expiry: 15 minutes / 900 seconds)."""
    s = get_reset_serializer()
    try:
        email = s.loads(token, salt='studyai-password-reset', max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RequestResetForm()
    if form.validate_on_submit():
        submitted_email = form.email.data.lower().strip()
        user = User.query.filter_by(email=submitted_email).first()
        if user:
            # 1. Ensure user exists in Firebase Auth and dispatch reset email via Firebase REST API
            api_key = FIREBASE_CONFIG.get('apiKey')
            if api_key:
                try:
                    signup_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}'
                    payload = {'email': user.email, 'password': f'Sync_{secrets.token_hex(8)}!', 'returnSecureToken': False}
                    req_sign = urllib.request.Request(signup_url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    try:
                        with urllib.request.urlopen(req_sign, timeout=5): pass
                    except urllib.error.HTTPError: pass

                    # Dispatch reset email
                    oob_url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}'
                    oob_data = {'requestType': 'PASSWORD_RESET', 'email': user.email}
                    req_oob = urllib.request.Request(oob_url, data=json.dumps(oob_data).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req_oob, timeout=6): pass
                except Exception as fb_err:
                    app.logger.warning(f"Firebase REST dispatch notice: {fb_err}")

            # 2. Also trigger standard SMTP reset if configured
            token = generate_reset_token(user.email)
            reset_url = url_for('reset_password', token=token, _external=True)
            send_reset_email(recipient_email=user.email, recipient_name=user.name, reset_url=reset_url)

            flash(f"A password reset link has been dispatched to your registered email ({user.email}). Please check your inbox and spam folder. Link expires in 15 minutes.", 'success')
            return redirect(url_for('login'))
        else:
            flash("No student account found with this email address. Please double-check your spelling or create a new account.", 'warning')
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password', defaults={'token': None}, methods=['GET', 'POST'])
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # If legacy token-based URL
    if token:
        email = verify_reset_token(token, max_age=900)
        if not email:
            flash("The password reset link is invalid or has expired (valid for 15 minutes). Please request a new link.", 'danger')
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Account not found. Please register or try again.", 'danger')
            return redirect(url_for('forgot_password'))
        
        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.set_password(form.password.data)
            db.session.commit()
            flash("Your password has been reset successfully! You can now log in with your new password.", 'success')
            return redirect(url_for('login'))
        
        return render_template('reset_password.html', form=form, token=token, email=email)
    
    # If Firebase Custom Action URL (/reset-password?mode=resetPassword&oobCode=...)
    form = ResetPasswordForm()
    return render_template('reset_password.html', form=form, token=None)

@app.route('/api/sync-reset-password', methods=['POST'])
def api_sync_reset_password():
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Missing email or password'}), 400
    user = User.query.filter_by(email=email).first()
    if user:
        user.set_password(password)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not found in DB'}), 404

@app.route('/api/check-reset-email', methods=['POST'])
def api_check_reset_email():
    """
    Verifies that the requested email belongs to an existing student in our database.
    If yes, ensures the user is also registered in Firebase Auth so sendPasswordResetEmail
    actually delivers the reset email instead of silently dropping it due to enumeration protection.
    """
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    if not email:
        return jsonify({'exists': False, 'message': 'Please enter a valid email address.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            'exists': False,
            'message': f'No account found with <strong>{email}</strong>. Please check your spelling or create a new student account.'
        })

    # Ensure provisioned in Firebase Auth
    api_key = FIREBASE_CONFIG.get('apiKey')
    if api_key:
        try:
            signup_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}'
            payload = {
                'email': user.email,
                'password': f'Sync_{secrets.token_hex(8)}!',
                'displayName': user.name,
                'returnSecureToken': False
            }
            req = urllib.request.Request(
                signup_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            try:
                with urllib.request.urlopen(req, timeout=5):
                    pass
            except urllib.error.HTTPError as e:
                # If EMAIL_EXISTS, that is expected and good
                pass
        except Exception as e:
            app.logger.warning(f"Could not provision user to Firebase: {e}")

    return jsonify({'exists': True})

# --- Public Marketing & Legal Pages ---

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if request.method == 'GET' and current_user.is_authenticated:
        form.name.data = current_user.name
        form.email.data = current_user.email

    if form.validate_on_submit():
        flash(f'Thank you, {form.name.data}! Your message has been received. Our academic support team will respond to {form.email.data} within 24 hours.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html', form=form)

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

        goal = current_user.study_goal_hours if (current_user.study_goal_hours and current_user.study_goal_hours > 0) else 4.0
        record.completion_percentage = min(100.0, round((record.study_hours / goal) * 100, 1))
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
    thirty_days_ago = today - timedelta(days=29)

    # Single batch fetch for all past 30 days to eliminate query storm & latency
    recent_records = Progress.query.filter(
        Progress.user_id == user_id,
        Progress.date >= thirty_days_ago,
        Progress.date <= today
    ).all()
    progress_map = {r.date: r.study_hours for r in recent_records}

    weekly_labels = []
    weekly_study_data = []
    weekly_goal_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        weekly_labels.append(day.strftime("%a"))
        weekly_study_data.append(progress_map.get(day, 0.0))
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
        monthly_hours_data.append(progress_map.get(day, 0.0))

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
                    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                    if ext in allowed_exts:
                        if is_cloudinary_configured:
                            try:
                                result = upload(
                                    file,
                                    folder="ai-study-planner/profile"
                                )
                                if result and "secure_url" in result:
                                    current_user.profile_image = result["secure_url"]
                            except Exception as e:
                                flash(f'Cloudinary upload warning: {str(e)}', 'warning')
                        else:
                            unique_filename = f"user_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                            upload_folder = os.path.join(app.root_path, 'static', 'profile_pics')
                            os.makedirs(upload_folder, exist_ok=True)
                            file.save(os.path.join(upload_folder, unique_filename))
                            current_user.profile_image = unique_filename
                    else:
                        flash('Invalid image format. Supported formats: PNG, JPG, JPEG, WEBP, GIF.', 'warning')

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
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
