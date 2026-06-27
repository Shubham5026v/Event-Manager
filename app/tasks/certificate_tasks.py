"""
Certificate Tasks
Celery tasks for asynchronous certificate generation and email delivery
"""

import os
import logging
from datetime import datetime
from flask import current_app, render_template
from celery import current_app as celery_app
from celery.utils.log import get_task_logger
from sqlalchemy import func

from app import db, mail
from app.models import Certificate, CertificateBatch, Event, Team, Score, User
from app.services.certificate_generator import CertificateGenerator

# Initialize logger
logger = get_task_logger(__name__)

# Initialize certificate generator
cert_gen = CertificateGenerator()


@celery_app.task(bind=True, name='certificates.generate_batch')
def generate_batch_certificates(self, batch_id):
    """
    Generate certificates for all teams in a batch
    
    Args:
        batch_id: ID of the CertificateBatch record
    """
    logger.info(f"Starting certificate generation for batch {batch_id}")
    
    try:
        # Get batch record
        batch = CertificateBatch.query.get(batch_id)
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return {'status': 'failed', 'error': 'Batch not found'}
        
        # Update batch status to processing
        batch.status = 'processing'
        db.session.commit()
        
        # Get event and teams
        event = Event.query.get(batch.event_id)
        if not event:
            logger.error(f"Event {batch.event_id} not found")
            batch.status = 'failed'
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'failed', 'error': 'Event not found'}
        
        # Get all teams for this event
        teams = Team.query.filter_by(event_id=event.id).all()
        
        if not teams:
            logger.warning(f"No teams found for event {event.id}")
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'completed', 'generated': 0, 'failed': 0}
        
        # Calculate scores and ranks
        teams_data = []
        for team in teams:
            # Calculate total score
            total_score = db.session.query(func.sum(Score.score)).filter_by(
                team_id=team.id,
                event_id=event.id
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
        
        # Generate certificates
        generated = 0
        failed = 0
        certificate_ids = []
        
        for team_data in teams_data:
            try:
                rank = team_data['rank']
                score = team_data['score']
                
                # Determine certificate type
                if rank and rank <= 3:
                    cert_type = 'winner'
                else:
                    cert_type = 'participation'
                
                # Generate certificate
                cert_result = cert_gen.generate_certificate(
                    team=team_data['team'],
                    event=event,
                    score=score,
                    rank=rank if rank and rank <= 3 else None,
                    custom_message=batch.custom_message if hasattr(batch, 'custom_message') else None
                )
                
                # Save certificate record
                certificate = Certificate(
                    verification_code=cert_result['verification_code'],
                    certificate_type=cert_type,
                    team_id=team_data['team'].id,
                    event_id=event.id,
                    generated_by_id=batch.generated_by_id,
                    rank_position=rank if rank and rank <= 3 else None,
                    final_score=score,
                    filename=cert_result['filename'],
                    generated_at=datetime.utcnow()
                )
                
                db.session.add(certificate)
                certificate_ids.append(certificate.id)
                
                # Update team with final score and rank
                team_data['team'].final_score = score
                team_data['team'].final_rank = rank
                
                generated += 1
                
                # Update progress
                batch.certificates_generated = generated
                db.session.commit()
                
                logger.info(f"Generated certificate for team {team_data['team'].id} - {cert_type}")
                
            except Exception as e:
                logger.error(f"Failed to generate certificate for team {team_data['team'].id}: {e}")
                failed += 1
                batch.certificates_failed = failed
                db.session.commit()
                continue
        
        # Update batch record
        batch.certificates_generated = generated
        batch.certificates_failed = failed
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        
        # Update event certificate generation flag
        event.certificates_generated = True
        event.certificates_generated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Certificate generation completed for batch {batch_id}: Generated={generated}, Failed={failed}")
        
        # Send completion email to admin
        send_batch_completion_email.delay(batch_id)
        
        return {
            'status': 'completed',
            'batch_id': batch_id,
            'generated': generated,
            'failed': failed,
            'certificate_ids': certificate_ids
        }
        
    except Exception as e:
        logger.error(f"Certificate generation failed for batch {batch_id}: {e}")
        
        # Update batch as failed
        try:
            batch = CertificateBatch.query.get(batch_id)
            if batch:
                batch.status = 'failed'
                batch.completed_at = datetime.utcnow()
                db.session.commit()
        except:
            pass
        
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.send_certificate_email')
def send_certificate_email(self, certificate_id, recipient_email, cc_admin=True):
    """
    Send certificate email to team
    
    Args:
        certificate_id: ID of the Certificate record
        recipient_email: Email address to send to
        cc_admin: Whether to CC admin on the email
    """
    from flask_mail import Message
    
    logger.info(f"Sending certificate email to {recipient_email} for certificate {certificate_id}")
    
    try:
        # Get certificate data
        certificate = Certificate.query.get(certificate_id)
        if not certificate:
            logger.error(f"Certificate {certificate_id} not found")
            return {'status': 'failed', 'error': 'Certificate not found'}
        
        team = certificate.team
        event = certificate.event
        
        # Generate download URL
        download_url = certificate.get_download_url()
        verification_url = certificate.get_verification_url()
        
        # Prepare email context
        context = {
            'team_name': team.name,
            'event_name': event.name,
            'certificate_type': certificate.certificate_type,
            'rank': certificate.rank_position,
            'score': certificate.final_score,
            'download_url': download_url,
            'verification_url': verification_url,
            'verification_code': certificate.verification_code,
            'event_date': event.event_date,
            'venue': event.venue
        }
        
        # Render email template
        html_body = render_template('emails/certificate_email.html', **context)
        text_body = render_template('emails/certificate_email.txt', **context)
        
        # Create message
        msg = Message(
            subject=f"Your Certificate for {event.name} - EventX",
            recipients=[recipient_email],
            html=html_body,
            body=text_body
        )
        
        # CC admin if requested
        if cc_admin:
            admin_emails = User.query.filter_by(role='admin').with_entities(User.email).all()
            msg.cc = [email[0] for email in admin_emails if email[0]]
        
        # Send email
        mail.send(msg)
        
        # Update certificate record
        certificate.email_sent = True
        certificate.email_sent_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Certificate email sent to {recipient_email}")
        
        return {'status': 'success', 'recipient': recipient_email}
        
    except Exception as e:
        logger.error(f"Failed to send certificate email to {recipient_email}: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.send_batch_emails')
def send_batch_certificate_emails(self, batch_id):
    """
    Send certificate emails to all teams in a batch
    
    Args:
        batch_id: ID of the CertificateBatch record
    """
    logger.info(f"Sending batch emails for batch {batch_id}")
    
    try:
        batch = CertificateBatch.query.get(batch_id)
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return {'status': 'failed', 'error': 'Batch not found'}
        
        # Get all certificates for this event
        certificates = Certificate.query.filter_by(event_id=batch.event_id).all()
        
        if not certificates:
            logger.warning(f"No certificates found for event {batch.event_id}")
            return {'status': 'completed', 'sent': 0}
        
        sent = 0
        failed = 0
        
        for certificate in certificates:
            if certificate.team.leader_email:
                # Send email
                result = send_certificate_email.delay(
                    certificate.id,
                    certificate.team.leader_email,
                    cc_admin=False
                )
                sent += 1
            else:
                logger.warning(f"No email for team {certificate.team.id}")
                failed += 1
        
        logger.info(f"Batch email sending initiated: Sent={sent}, Failed={failed}")
        
        return {
            'status': 'initiated',
            'batch_id': batch_id,
            'sent': sent,
            'failed': failed
        }
        
    except Exception as e:
        logger.error(f"Batch email sending failed for batch {batch_id}: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.send_batch_completion_email')
def send_batch_completion_email(self, batch_id):
    """
    Send completion notification email to admin
    
    Args:
        batch_id: ID of the CertificateBatch record
    """
    from flask_mail import Message
    
    logger.info(f"Sending batch completion email for batch {batch_id}")
    
    try:
        batch = CertificateBatch.query.get(batch_id)
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return {'status': 'failed', 'error': 'Batch not found'}
        
        event = Event.query.get(batch.event_id)
        
        # Get admin emails
        admin_emails = User.query.filter_by(role='admin').with_entities(User.email).all()
        admin_emails = [email[0] for email in admin_emails if email[0]]
        
        if not admin_emails:
            logger.warning("No admin emails found")
            return {'status': 'completed', 'recipients': 0}
        
        # Prepare email context
        context = {
            'batch': batch,
            'event': event,
            'generated': batch.certificates_generated,
            'failed': batch.certificates_failed,
            'total': batch.total_teams,
            'admin_url': url_for('certificates.admin_index', _external=True)
        }
        
        # Render email template
        html_body = render_template('emails/batch_completion_email.html', **context)
        text_body = render_template('emails/batch_completion_email.txt', **context)
        
        # Create message
        msg = Message(
            subject=f"Certificate Generation Completed - {event.name}",
            recipients=admin_emails,
            html=html_body,
            body=text_body
        )
        
        # Send email
        mail.send(msg)
        
        logger.info(f"Batch completion email sent to {len(admin_emails)} admins")
        
        return {'status': 'success', 'recipients': len(admin_emails)}
        
    except Exception as e:
        logger.error(f"Failed to send batch completion email: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.generate_single')
def generate_single_certificate(self, team_id, event_id, custom_message=None):
    """
    Generate a single certificate for a team
    
    Args:
        team_id: ID of the Team
        event_id: ID of the Event
        custom_message: Optional custom message
    """
    logger.info(f"Generating single certificate for team {team_id}, event {event_id}")
    
    try:
        team = Team.query.get(team_id)
        event = Event.query.get(event_id)
        
        if not team or not event:
            return {'status': 'failed', 'error': 'Team or event not found'}
        
        # Calculate score
        total_score = db.session.query(func.sum(Score.score)).filter_by(
            team_id=team_id,
            event_id=event_id
        ).scalar() or 0
        
        # Calculate rank
        all_scores = db.session.query(
            Team.id,
            func.sum(Score.score).label('total')
        ).join(Score).filter(
            Score.event_id == event_id
        ).group_by(Team.id).order_by(func.sum(Score.score).desc()).all()
        
        rank = None
        for idx, score_row in enumerate(all_scores):
            if score_row[0] == team_id:
                rank = idx + 1
                break
        
        # Generate certificate
        cert_result = cert_gen.generate_certificate(
            team=team,
            event=event,
            score=total_score,
            rank=rank if rank and rank <= 3 else None,
            custom_message=custom_message
        )
        
        # Save certificate record
        certificate = Certificate(
            verification_code=cert_result['verification_code'],
            certificate_type=cert_result['certificate_type'],
            team_id=team_id,
            event_id=event_id,
            generated_by_id=None,
            rank_position=rank if rank and rank <= 3 else None,
            final_score=total_score,
            filename=cert_result['filename'],
            custom_message=custom_message,
            generated_at=datetime.utcnow()
        )
        
        db.session.add(certificate)
        db.session.commit()
        
        logger.info(f"Certificate generated for team {team_id}")
        
        return {
            'status': 'success',
            'certificate_id': certificate.id,
            'verification_code': certificate.verification_code
        }
        
    except Exception as e:
        logger.error(f"Single certificate generation failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.cleanup_old_certificates')
def cleanup_old_certificates(self, days=365):
    """
    Clean up old certificate files and records
    
    Args:
        days: Age in days to consider for cleanup
    """
    from datetime import timedelta
    
    logger.info(f"Starting cleanup of certificates older than {days} days")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old certificates
        old_certificates = Certificate.query.filter(
            Certificate.generated_at < cutoff_date,
            Certificate.download_count == 0  # Never downloaded
        ).all()
        
        deleted = 0
        deleted_files = 0
        
        for cert in old_certificates:
            try:
                # Delete PDF file
                filepath = os.path.join(current_app.static_folder, 'certificates', cert.filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_files += 1
                
                # Delete QR code file
                if cert.qr_code_filename:
                    qr_path = os.path.join(current_app.static_folder, 'certificates', cert.qr_code_filename)
                    if os.path.exists(qr_path):
                        os.remove(qr_path)
                
                # Delete record
                db.session.delete(cert)
                deleted += 1
                
            except Exception as e:
                logger.error(f"Failed to delete certificate {cert.id}: {e}")
                continue
        
        db.session.commit()
        
        logger.info(f"Cleanup completed: Deleted {deleted} records, {deleted_files} files")
        
        return {
            'status': 'completed',
            'deleted_records': deleted,
            'deleted_files': deleted_files
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.generate_missing_certificates')
def generate_missing_certificates(self, event_id):
    """
    Generate certificates for teams that don't have them
    
    Args:
        event_id: ID of the Event
    """
    logger.info(f"Generating missing certificates for event {event_id}")
    
    try:
        event = Event.query.get(event_id)
        if not event:
            return {'status': 'failed', 'error': 'Event not found'}
        
        # Get teams without certificates
        teams_with_certs = db.session.query(Certificate.team_id).filter_by(event_id=event_id).subquery()
        missing_teams = Team.query.filter(
            Team.event_id == event_id,
            Team.id.notin_(teams_with_certs)
        ).all()
        
        if not missing_teams:
            logger.info("No missing certificates found")
            return {'status': 'completed', 'generated': 0}
        
        # Generate certificates for missing teams
        generated = 0
        failed = 0
        
        for team in missing_teams:
            try:
                # Calculate score
                total_score = db.session.query(func.sum(Score.score)).filter_by(
                    team_id=team.id,
                    event_id=event_id
                ).scalar() or 0
                
                # Generate certificate
                cert_result = cert_gen.generate_certificate(
                    team=team,
                    event=event,
                    score=total_score,
                    rank=None,
                    custom_message="Thank you for participating!"
                )
                
                # Save certificate
                certificate = Certificate(
                    verification_code=cert_result['verification_code'],
                    certificate_type='participation',
                    team_id=team.id,
                    event_id=event_id,
                    generated_by_id=None,
                    final_score=total_score,
                    filename=cert_result['filename'],
                    generated_at=datetime.utcnow()
                )
                
                db.session.add(certificate)
                generated += 1
                
            except Exception as e:
                logger.error(f"Failed to generate certificate for team {team.id}: {e}")
                failed += 1
        
        db.session.commit()
        
        logger.info(f"Missing certificates generated: {generated} success, {failed} failed")
        
        return {
            'status': 'completed',
            'generated': generated,
            'failed': failed
        }
        
    except Exception as e:
        logger.error(f"Missing certificates generation failed: {e}")
        return {'status': 'failed', 'error': str(e)}


@celery_app.task(bind=True, name='certificates.update_certificate_stats')
def update_certificate_stats(self):
    """
    Update certificate statistics (run periodically)
    """
    logger.info("Updating certificate statistics")
    
    try:
        stats = {
            'total': Certificate.query.count(),
            'winner': Certificate.query.filter_by(certificate_type='winner').count(),
            'participation': Certificate.query.filter_by(certificate_type='participation').count(),
            'verified': Certificate.query.filter_by(is_verified=True).count(),
            'emailed': Certificate.query.filter_by(email_sent=True).count(),
            'total_downloads': db.session.query(func.sum(Certificate.download_count)).scalar() or 0
        }
        
        # Store stats in Redis or cache
        from app import redis_client
        if redis_client:
            redis_client.setex('certificate_stats', 3600, json.dumps(stats))
        
        logger.info(f"Certificate statistics updated: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to update certificate statistics: {e}")
        return {'status': 'failed', 'error': str(e)}


# ============================================
# Scheduled Tasks
# ============================================

@celery_app.task(bind=True, name='certificates.scheduled_cleanup')
def scheduled_cleanup(self):
    """
    Scheduled task to clean up old certificates
    Runs daily
    """
    logger.info("Running scheduled certificate cleanup")
    return cleanup_old_certificates.delay(days=365)


@celery_app.task(bind=True, name='certificates.scheduled_stats_update')
def scheduled_stats_update(self):
    """
    Scheduled task to update certificate statistics
    Runs hourly
    """
    logger.info("Running scheduled certificate statistics update")
    return update_certificate_stats.delay()


# ============================================
# Helper Functions
# ============================================

def get_task_status(task_id):
    """Get status of a Celery task"""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id, app=celery_app)
    
    if task.pending:
        return {'status': 'pending'}
    elif task.failed():
        return {'status': 'failed', 'error': str(task.info)}
    elif task.successful():
        return {'status': 'completed', 'result': task.result}
    else:
        return {'status': 'processing'}