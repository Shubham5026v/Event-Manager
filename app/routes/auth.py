from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Team, Event
from app.forms import LoginForm, TeamRegistrationForm, JudgeRegistrationForm

bp = Blueprint('auth', __name__)
auth_bp = bp

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'judge':
            return redirect(url_for('judge.dashboard'))
        elif current_user.role == 'team':
            return redirect(url_for('team.dashboard'))
        return redirect(url_for('public.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Welcome back, {user.username}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'judge':
                return redirect(url_for('judge.dashboard'))
            elif user.role == 'team':
                return redirect(url_for('team.dashboard'))
            else:
                return redirect(url_for('public.index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('public.index'))

@bp.route('/register/team', methods=['GET', 'POST'])
def register_team():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    
    form = TeamRegistrationForm()
    
    # Populate events dynamically
    if form.is_submitted():
        form.event_id.choices = [(e.id, e.name) for e in Event.query.filter_by(status='upcoming').all()]
    else:
        form.event_id.choices = [(e.id, e.name) for e in Event.query.filter_by(status='upcoming').all()]
    
    if form.validate_on_submit():
        # Check if username already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('auth.register_team'))
        
        # Check if email already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please login or use a different email.', 'danger')
            return redirect(url_for('auth.register_team'))
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            role='team'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # Flush to get the user ID without committing
        
        # Create team registration
        team = Team(
            name=form.team_name.data,
            institution=form.institution.data,
            leader_name=form.leader_name.data,
            leader_email=form.email.data,
            leader_phone=form.leader_phone.data,
            event_id=form.event_id.data,
            user_id=user.id
        )
        db.session.add(team)
        db.session.commit()
        
        flash('Team registration successful! You can now login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register_team.html', form=form)

@bp.route('/register/judge', methods=['GET', 'POST'])
def register_judge():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = JudgeRegistrationForm()

    if form.validate_on_submit():
        # Check if username already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('auth.register_judge'))

        # Check if email already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please login or use a different email.', 'danger')
            return redirect(url_for('auth.register_judge'))

        # Create new judge user
        user = User(
            username=form.username.data,
            email=form.email.data,
            role='judge'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Judge registration successful! You can now login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_judge.html', form=form)