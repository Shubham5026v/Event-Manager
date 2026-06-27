from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Event, Team, Score

bp = Blueprint('judge', __name__, url_prefix='/judge')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'judge':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('public.index'))
    
    # Get all ongoing events for judging
    events = Event.query.filter_by(status='ongoing').all()
    
    # Get scores submitted by this judge
    submitted_scores = Score.query.filter_by(judge_id=current_user.id).all()
    
    # Get teams for the first event (or None)
    teams = []
    selected_event = None
    if events:
        selected_event = events[0]
        teams = Team.query.filter_by(event_id=selected_event.id).all()
    
    return render_template('judge/dashboard.html', 
                         events=events, 
                         teams=teams,
                         submitted_scores=submitted_scores,
                         selected_event=selected_event)

@bp.route('/panel')
@login_required
def panel():
    if current_user.role != 'judge':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('public.index'))
    return render_template('judge/panel.html')
