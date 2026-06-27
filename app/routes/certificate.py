"""
Certificate Routes
Handles certificate generation, download, verification, and management
"""

import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, url_for, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, func

from app import db
from app.models import Event, Team, Score, Certificate, CertificateBatch, CertificateTemplate, User
from app.services.certificate_generator import CertificateGenerator

# Create blueprint
certificates_bp = Blueprint('certificates', __name__, url_prefix='/certificates')

# Initialize certificate generator
cert_gen = CertificateGenerator()

# ============================================
# Admin Routes
# ============================================

@certificates_bp.route('/admin')
@login_required
def admin_index():
    """Admin dashboard for certificate management"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('public.index'))
    
    # Get statistics
    total_certificates = Certificate.query.count()
    winner_certificates = Certificate.query.filter_by(certificate_type='winner').count()
    participation_certificates = Certificate.query.filter_by(certificate_type='participation').count()
    total_verifications = Certificate.query.filter_by(is_verified=True).count()
    
    # Get recent certificates
    recent_certificates = Certificate.query.order_by(desc(Certificate.generated_at)).limit(10).all()
    
    # Get events with certificate generation status
    events = Event.query.order_by(desc(Event.event_date)).all()
    events_data = []
    for event in events:
        cert_count = Certificate.query.filter_by(event_id=event.id).count()
        team_count = Team.query.filter_by(event_id=event.id).count()
        events_data.append({
            'event': event,
            'certificate_count': cert_count,
            'team_count': team_count,
            'generation_percentage': (cert_count / team_count * 100) if team_count > 0 else 0
        })
    
    return render_template('admin/certificates/index.html',
                         total_certificates=total_certificates,
                         winner_certificates=winner_certificates,
                         participation_certificates=participation_certificates,
                         total_verifications=total_verifications,
                         recent_certificates=recent_certificates,
                         events_data=events_data)


@certificates_bp.route('/admin/event/<int:event_id>/generate', methods=['GET', 'POST'])
@login_required
def generate_event_certificates(event_id):
    """Generate certificates for all teams in an event"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('public.index'))
    
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        try:
            # Get all teams for this event with their final scores
            teams = Team.query.filter_by(event_id=event_id).all()
            
            if not teams:
                flash('No teams found for this event.', 'warning')
                return redirect(url_for('certificates.admin_index'))
            
            # Calculate final scores and ranks for each team
            teams_data = []
            for team in teams:
                # Calculate total score from all criteria
                total_score = db.session.query(func.sum(Score.score)).filter_by(
                    team_id=team.id, 
                    event_id=event_id
                ).scalar() or 0
                
                teams_data.append({
                    'team': team,
                    'score': total_score,
                    'rank': None
                })
            
            # Sort by score and assign ranks
            teams_data.sort(key=lambda x: x['score'], reverse=True)
            for idx, team_data in enumerate(teams_data):
                if team_data['score'] > 0:
                    team_data['rank'] = idx + 1
            
            # Create batch record
            batch_code = f"BATCH_{event_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            batch = CertificateBatch(
                batch_code=batch_code,
                event_id=event_id,
                generated_by_id=current_user.id,
                total_teams=len(teams_data)
            )
            db.session.add(batch)
            db.session.commit()
            
            # Generate certificates
            generated = 0
            failed = 0
            
            for team_data in teams_data:
                try:
                    # Determine certificate type based on rank
                    rank = team_data['rank']
                    score = team_data['score']
                    
                    # Generate certificate
                    cert_result = cert_gen.generate_certificate(
                        team=team_data['team'],
                        event=event,
                        score=score,
                        rank=rank if rank and rank <= 3 else None,
                        custom_message=request.form.get('custom_message')
                    )
                    
                    # Save certificate record to database
                    certificate = Certificate(
                        verification_code=cert_result['verification_code'],
                        certificate_type=cert_result['certificate_type'],
                        team_id=team_data['team'].id,
                        event_id=event_id,
                        generated_by_id=current_user.id,
                        rank_position=rank if rank and rank <= 3 else None,
                        final_score=score,
                        filename=cert_result['filename'],
                        custom_message=request.form.get('custom_message'),
                        ip_address=request.remote_addr
                    )
                    
                    db.session.add(certificate)
                    generated += 1
                    
                    # Update team with final score and rank
                    team_data['team'].final_score = score
                    team_data['team'].final_rank = rank
                    
                except Exception as e:
                    current_app.logger.error(f"Certificate generation failed for team {team_data['team'].id}: {e}")
                    failed += 1
            
            # Update batch record
            batch.certificates_generated = generated
            batch.certificates_failed = failed
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()
            
            # Update event certificate generation flag
            event.certificates_generated = True
            event.certificates_generated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Certificates generated successfully! Generated: {generated}, Failed: {failed}', 'success')
            
            # Send emails if requested
            if request.form.get('send_emails'):
                send_certificate_emails.delay(batch.id)
                flash('Emails will be sent to teams shortly.', 'info')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch certificate generation failed: {e}")
            flash('An error occurred while generating certificates.', 'danger')
        
        return redirect(url_for('certificates.admin_index'))
    
    # GET request - show generation page
    teams = Team.query.filter_by(event_id=event_id).all()
    team_count = len(teams)
    existing_certificates = Certificate.query.filter_by(event_id=event_id).count()
    
    return render_template('admin/certificates/generate.html',
                         event=event,
                         teams=teams,
                         team_count=team_count,
                         existing_certificates=existing_certificates)


@certificates_bp.route('/admin/event/<int:event_id>/preview', methods=['GET'])
@login_required
def preview_certificate(event_id):
    """Preview certificate for a team before generation"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    team_id = request.args.get('team_id', type=int)
    rank = request.args.get('rank', type=int)
    
    if not team_id:
        return jsonify({'error': 'Team ID required'}), 400
    
    team = Team.query.get_or_404(team_id)
    event = Event.query.get_or_404(event_id)
    
    # Calculate team score
    total_score = db.session.query(func.sum(Score.score)).filter_by(
        team_id=team_id, event_id=event_id
    ).scalar() or 0
    
    # Generate preview (without saving)
    try:
        # This would need a preview method in certificate generator
        # For now, return certificate data
        preview_data = {
            'team_name': team.name,
            'event_name': event.name,
            'score': total_score,
            'rank': rank,
            'certificate_type': 'winner' if rank and rank <= 3 else 'participation'
        }
        return jsonify(preview_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@certificates_bp.route('/admin/certificate/<int:cert_id>/download')
@login_required
def admin_download_certificate(cert_id):
    """Download certificate (admin route)"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('public.index'))
    
    certificate = Certificate.query.get_or_404(cert_id)
    
    # Increment download count
    certificate.increment_download_count()
    db.session.commit()
    
    filepath = os.path.join(current_app.static_folder, 'certificates', certificate.filename)
    
    if not os.path.exists(filepath):
        flash('Certificate file not found.', 'danger')
        return redirect(url_for('certificates.admin_index'))
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"certificate_{certificate.verification_code}.pdf",
        mimetype='application/pdf'
    )


@certificates_bp.route('/admin/certificate/<int:cert_id>/delete', methods=['POST'])
@login_required
def delete_certificate(cert_id):
    """Delete a certificate"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    certificate = Certificate.query.get_or_404(cert_id)
    
    # Delete physical file
    filepath = os.path.join(current_app.static_folder, 'certificates', certificate.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete QR code file if exists
    if certificate.qr_code_filename:
        qr_path = os.path.join(current_app.static_folder, 'certificates', certificate.qr_code_filename)
        if os.path.exists(qr_path):
            os.remove(qr_path)
    
    # Delete from database
    db.session.delete(certificate)
    db.session.commit()
    
    flash('Certificate deleted successfully.', 'success')
    return redirect(request.referrer or url_for('certificates.admin_index'))


@certificates_bp.route('/admin/event/<int:event_id>/certificates')
@login_required
def event_certificates(event_id):
    """View all certificates for an event"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('public.index'))
    
    event = Event.query.get_or_404(event_id)
    certificates = Certificate.query.filter_by(event_id=event_id).order_by(desc(Certificate.generated_at)).all()
    
    return render_template('admin/certificates/event_certificates.html',
                         event=event,
                         certificates=certificates)


# ============================================
# Public Routes
# ============================================

@certificates_bp.route('/verify/<code>')
def verify_certificate(code):
    """Public certificate verification page"""
    certificate = Certificate.query.filter_by(verification_code=code.upper(), is_active=True).first()
    
    if not certificate:
        return render_template('public/certificates/verify.html', 
                             valid=False, 
                             message='Certificate not found or has been revoked.')
    
    # Check if expired
    if certificate.is_expired():
        return render_template('public/certificates/verify.html',
                             valid=False,
                             message='This certificate has expired.')
    
    # Mark as verified
    if not certificate.is_verified:
        certificate.mark_as_verified()
    
    # Get certificate data
    cert_data = {
        'verification_code': certificate.verification_code,
        'certificate_type': certificate.certificate_type,
        'team_name': certificate.team.name,
        'event_name': certificate.event.name,
        'event_date': certificate.event.event_date,
        'venue': certificate.event.venue,
        'rank': certificate.rank_position,
        'score': certificate.final_score,
        'generated_at': certificate.generated_at,
        'is_verified': certificate.is_verified
    }
    
    return render_template('public/certificates/verify.html',
                         valid=True,
                         certificate=cert_data)


@certificates_bp.route('/download/<cert_id>')
def download_certificate(cert_id):
    """Public certificate download"""
    certificate = Certificate.query.filter_by(verification_code=cert_id.upper(), is_active=True).first()
    
    if not certificate:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('public.index'))
    
    # Check if expired
    if certificate.is_expired():
        flash('This certificate has expired.', 'danger')
        return redirect(url_for('public.index'))
    
    # Increment download count
    certificate.increment_download_count()
    db.session.commit()
    
    filepath = os.path.join(current_app.static_folder, 'certificates', certificate.filename)
    
    if not os.path.exists(filepath):
        flash('Certificate file not found.', 'danger')
        return redirect(url_for('public.index'))
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"certificate_{certificate.verification_code}.pdf",
        mimetype='application/pdf'
    )


@certificates_bp.route('/view/<cert_id>')
def view_certificate(cert_id):
    """View certificate in browser (not download)"""
    certificate = Certificate.query.filter_by(verification_code=cert_id.upper(), is_active=True).first()
    
    if not certificate:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('public.index'))
    
    filepath = os.path.join(current_app.static_folder, 'certificates', certificate.filename)
    
    if not os.path.exists(filepath):
        flash('Certificate file not found.', 'danger')
        return redirect(url_for('public.index'))
    
    return send_file(filepath, mimetype='application/pdf')


# ============================================
# Team Routes
# ============================================

@certificates_bp.route('/team/my-certificates')
@login_required
def my_certificates():
    """View certificates for logged-in team"""
    if current_user.role != 'team':
        flash('Access denied.', 'danger')
        return redirect(url_for('public.index'))
    
    team = Team.query.filter_by(user_id=current_user.id).first()
    if not team:
        flash('No team profile found.', 'warning')
        return redirect(url_for('team.dashboard'))
    
    certificates = Certificate.query.filter_by(team_id=team.id).order_by(desc(Certificate.generated_at)).all()
    
    return render_template('team/certificates.html', certificates=certificates)


# ============================================
# API Routes
# ============================================

@certificates_bp.route('/api/event/<int:event_id>/certificates', methods=['GET'])
def api_event_certificates(event_id):
    """API endpoint to get certificates for an event"""
    certificates = Certificate.query.filter_by(event_id=event_id).all()
    return jsonify([cert.to_dict() for cert in certificates])


@certificates_bp.route('/api/team/<int:team_id>/certificates', methods=['GET'])
def api_team_certificates(team_id):
    """API endpoint to get certificates for a team"""
    certificates = Certificate.query.filter_by(team_id=team_id).all()
    return jsonify([cert.to_dict() for cert in certificates])


@certificates_bp.route('/api/verify/<code>', methods=['GET'])
def api_verify_certificate(code):
    """API endpoint to verify a certificate"""
    certificate = Certificate.query.filter_by(verification_code=code.upper()).first()
    
    if not certificate:
        return jsonify({'valid': False, 'message': 'Certificate not found'}), 404
    
    if not certificate.is_active:
        return jsonify({'valid': False, 'message': 'Certificate has been revoked'}), 400
    
    if certificate.is_expired():
        return jsonify({'valid': False, 'message': 'Certificate has expired'}), 400
    
    return jsonify({
        'valid': True,
        'certificate': certificate.to_dict()
    })


@certificates_bp.route('/api/generate-bulk', methods=['POST'])
@login_required
def api_generate_bulk():
    """API endpoint for bulk certificate generation"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    event_id = data.get('event_id')
    team_ids = data.get('team_ids', [])
    
    if not event_id:
        return jsonify({'error': 'Event ID required'}), 400
    
    event = Event.query.get_or_404(event_id)
    teams = Team.query.filter(Team.id.in_(team_ids)).all() if team_ids else Team.query.filter_by(event_id=event_id).all()
    
    # Create batch
    batch_code = f"API_BATCH_{event_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    batch = CertificateBatch(
        batch_code=batch_code,
        event_id=event_id,
        generated_by_id=current_user.id,
        total_teams=len(teams),
        status='processing'
    )
    db.session.add(batch)
    db.session.commit()
    
    # Trigger async generation
    generate_certificates_async.delay(batch.id)
    
    return jsonify({
        'batch_id': batch.id,
        'batch_code': batch_code,
        'message': 'Certificate generation started',
        'status_url': url_for('certificates.api_batch_status', batch_id=batch.id, _external=True)
    })


@certificates_bp.route('/api/batch/<int:batch_id>/status', methods=['GET'])
def api_batch_status(batch_id):
    """API endpoint to check batch generation status"""
    batch = CertificateBatch.query.get_or_404(batch_id)
    
    return jsonify({
        'batch_id': batch.id,
        'batch_code': batch.batch_code,
        'status': batch.status,
        'total_teams': batch.total_teams,
        'generated': batch.certificates_generated,
        'failed': batch.certificates_failed,
        'progress': batch.get_progress(),
        'started_at': batch.started_at.isoformat() if batch.started_at else None,
        'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
    })


# ============================================
# Helper Functions
# ============================================

def send_certificate_emails(batch_id):
    """Send certificate emails to teams (async task)"""
    from app.tasks.certificate_tasks import send_certificate_email
    from app.models import CertificateBatch
    
    batch = CertificateBatch.query.get(batch_id)
    if not batch:
        return
    
    certificates = Certificate.query.filter_by(event_id=batch.event_id).all()
    
    for cert in certificates:
        if cert.team.leader_email:
            send_certificate_email.delay(cert.id, cert.team.leader_email)


def generate_certificates_async(batch_id):
    """Async certificate generation task"""
    from app.tasks.certificate_tasks import generate_batch_certificates
    generate_batch_certificates.delay(batch_id)


# ============================================
# Template Routes
# ============================================

@certificates_bp.route('/admin/templates')
@login_required
def manage_templates():
    """Manage certificate templates"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('public.index'))
    
    templates = CertificateTemplate.query.all()
    return render_template('admin/certificates/templates.html', templates=templates)


@certificates_bp.route('/admin/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Create a new certificate template"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('public.index'))
    
    if request.method == 'POST':
        template = CertificateTemplate(
            name=request.form.get('name'),
            description=request.form.get('description'),
            template_type=request.form.get('template_type'),
            background_color=request.form.get('background_color', '#ffffff'),
            border_color=request.form.get('border_color', '#2b6eff'),
            title_color=request.form.get('title_color', '#ffaa33'),
            text_color=request.form.get('text_color', '#000000'),
            has_border=request.form.get('has_border') == 'on',
            has_seal=request.form.get('has_seal') == 'on',
            has_qr_code=request.form.get('has_qr_code') == 'on',
            is_default=request.form.get('is_default') == 'on'
        )
        
        db.session.add(template)
        db.session.commit()
        
        flash('Template created successfully.', 'success')
        return redirect(url_for('certificates.manage_templates'))
    
    return render_template('admin/certificates/template_form.html')