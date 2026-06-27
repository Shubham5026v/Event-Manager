from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Event, Team, Score

bp = Blueprint('admin', __name__, url_prefix='/admin')


def _require_admin():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role != 'admin':
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('public.index'))
    return None


@bp.route('/')
@login_required
def index():
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    return redirect(url_for('admin.dashboard'))


@bp.route('/dashboard')
@login_required
def dashboard():
    admin_check = _require_admin()
    if admin_check:
        return admin_check

    events = Event.query.order_by(Event.event_date.desc()).all()
    teams = Team.query.order_by(Team.name.asc()).all()
    scores = Score.query.order_by(Score.id.desc()).all()

    upcoming_events = Event.query.filter_by(status='upcoming').order_by(Event.event_date).all()
    ongoing_events = Event.query.filter_by(status='ongoing').order_by(Event.event_date).all()
    completed_events = Event.query.filter_by(status='completed').order_by(Event.event_date.desc()).all()

    return render_template(
        'admin/dashboard.html',
        events=events,
        teams=teams,
        scores=scores,
        upcoming_events=upcoming_events,
        ongoing_events=ongoing_events,
        completed_events=completed_events
    )


@bp.route('/events')
@login_required
def events():
    admin_check = _require_admin()
    if admin_check:
        return admin_check

    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('admin/events.html', events=events)


@bp.route('/teams')
@login_required
def teams():
    admin_check = _require_admin()
    if admin_check:
        return admin_check

    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template('admin/teams.html', teams=teams)


@bp.route('/scores')
@login_required
def scores():
    admin_check = _require_admin()
    if admin_check:
        return admin_check

    scores = Score.query.order_by(Score.id.desc()).all()
    return render_template('admin/scores.html', scores=scores)
