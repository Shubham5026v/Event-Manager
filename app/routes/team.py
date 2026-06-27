from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Team

bp = Blueprint('team', __name__, url_prefix='/team')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'team':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('public.index'))
    
    # Get the team associated with this user
    team = Team.query.filter_by(user_id=current_user.id).first()
    
    return render_template('team/dashboard.html', team=team)

@bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.role != 'team':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('public.index'))
    
    # Check if team is already registered
    team = Team.query.filter_by(user_id=current_user.id).first()
    if team:
        flash('Your team is already registered for an event', 'info')
        return redirect(url_for('team.dashboard'))
    
    return render_template('team/register.html')
