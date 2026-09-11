from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FloatField, SelectField, DateField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from models import User
from flask_login import current_user

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, message="Password must be at least 6 characters")])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message="Passwords must match")])
    submit = SubmitField('Create Account')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower().strip()).first()
        if user:
            raise ValidationError('Email is already registered. Please login or use another.')


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class SubjectForm(FlaskForm):
    subject_name = StringField('Subject Name', validators=[DataRequired(), Length(min=2, max=100)])
    color = SelectField('Badge Color', choices=[
        ('#4f46e5', 'Indigo Blue'),
        ('#06b6d4', 'Cyan Teal'),
        ('#10b981', 'Emerald Green'),
        ('#f59e0b', 'Amber Orange'),
        ('#ef4444', 'Ruby Red'),
        ('#8b5cf6', 'Royal Purple'),
        ('#ec4899', 'Rose Pink')
    ], default='#4f46e5')
    submit = SubmitField('Save Subject')


class TaskForm(FlaskForm):
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    task_name = StringField('Task Description', validators=[DataRequired(), Length(min=3, max=200)])
    deadline = DateField('Target Deadline', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('High', 'High Priority 🔥'),
        ('Medium', 'Medium Priority ⚡'),
        ('Low', 'Low Priority ☕')
    ], default='Medium')
    status = SelectField('Status', choices=[
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed')
    ], default='Pending')
    estimated_hours = FloatField('Estimated Hours', validators=[DataRequired(), NumberRange(min=0.25, max=24.0)], default=1.0)
    submit = SubmitField('Save Task')


class ProgressLogForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    study_hours = FloatField('Study Hours Spent', validators=[DataRequired(), NumberRange(min=0.1, max=24.0)])
    notes = TextAreaField('Session Reflections & Notes', validators=[Length(max=255)])
    submit = SubmitField('Log Study Session')


class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    study_goal_hours = FloatField('Daily Study Goal (Hours)', validators=[DataRequired(), NumberRange(min=0.5, max=16.0)])
    submit = SubmitField('Update Profile')

    def validate_email(self, email):
        if email.data.lower().strip() != current_user.email:
            user = User.query.filter_by(email=email.data.lower().strip()).first()
            if user:
                raise ValidationError('Email is already in use by another account.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password', message="New passwords must match")])
    submit = SubmitField('Update Password')
