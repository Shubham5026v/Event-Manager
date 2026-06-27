"""
Certificate Generation Service
Handles PDF generation with dynamic content for winners and participants
"""

import os
import uuid
import qrcode
import io
from datetime import datetime
from flask import current_app, url_for
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4, portrait
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor, Color

class CertificateGenerator:
    """Certificate generator for events with support for winner and participation certificates"""
    
    def __init__(self, app=None):
        self.app = app
        self.cert_dir = None
        self.fonts_registered = False
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        
        # Setup certificate directory
        self.cert_dir = os.path.join(app.static_folder, 'certificates')
        os.makedirs(self.cert_dir, exist_ok=True)
        
        # Register custom fonts
        self._register_fonts()
    
    def _register_fonts(self):
        """Register custom fonts for certificates"""
        if self.fonts_registered:
            return
        
        try:
            # Register GreatVibes script font for names
            font_path = os.path.join(self.app.static_folder, 'fonts', 'GreatVibes-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('GreatVibes', font_path))
            
            # Register Montserrat for titles
            montserrat_path = os.path.join(self.app.static_folder, 'fonts', 'Montserrat-Bold.ttf')
            if os.path.exists(montserrat_path):
                pdfmetrics.registerFont(TTFont('Montserrat', montserrat_path))
            
            # Register Open Sans for body text
            opensans_path = os.path.join(self.app.static_folder, 'fonts', 'OpenSans-Regular.ttf')
            if os.path.exists(opensans_path):
                pdfmetrics.registerFont(TTFont('OpenSans', opensans_path))
                
            self.fonts_registered = True
        except Exception as e:
            current_app.logger.warning(f"Font registration failed: {e}")
            self.fonts_registered = False
    
    def generate_certificate(self, team, event, score=None, rank=None, custom_message=None):
        """
        Generate certificate for a team
        
        Args:
            team: Team object with name, leader, members
            event: Event object with name, date, venue
            score: Team's final score (optional)
            rank: Team's rank position (1st, 2nd, 3rd, or None)
            custom_message: Optional personalized message
            
        Returns:
            dict: {
                'filepath': str,
                'filename': str,
                'certificate_type': str,
                'verification_code': str,
                'download_url': str
            }
        """
        # Determine certificate type
        if rank and rank <= 3:
            cert_type = 'winner'
            medal = self._get_medal_symbol(rank)
        else:
            cert_type = 'participation'
            medal = None
        
        # Generate unique verification code
        verification_code = self._generate_verification_code(team.id, event.id)
        
        # Generate unique filename
        filename = f"cert_{event.id}_{team.id}_{verification_code[:8]}.pdf"
        filepath = os.path.join(self.cert_dir, filename)
        
        # Generate QR code for verification
        qr_path = self._generate_qr_code(verification_code, team.id, event.id)
        
        # Create PDF
        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        
        # Build certificate content
        story = []
        
        # Add background
        story.append(self._create_background())
        
        # Add border decoration
        story.append(self._create_border())
        
        # Add seal/stamp
        if cert_type == 'winner':
            story.append(self._create_seal(rank))
        
        # Add medal/ribbon decoration
        if medal:
            story.append(self._create_medal(medal))
        
        # Add main content
        story.extend(self._create_content(
            team=team,
            event=event,
            cert_type=cert_type,
            score=score,
            rank=rank,
            custom_message=custom_message
        ))
        
        # Add QR code
        if qr_path:
            story.append(self._create_qr_section(qr_path, verification_code))
        
        # Build PDF
        doc.build(story)
        
        # Generate download URL
        download_url = url_for('certificates.download', cert_id=verification_code, _external=True)
        
        return {
            'filepath': filepath,
            'filename': filename,
            'certificate_type': cert_type,
            'verification_code': verification_code,
            'download_url': download_url,
            'rank': rank
        }
    
    def _generate_verification_code(self, team_id, event_id):
        """Generate unique verification code for certificate"""
        import hashlib
        timestamp = datetime.utcnow().isoformat()
        raw = f"{team_id}-{event_id}-{timestamp}-{uuid.uuid4().hex}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    
    def _generate_qr_code(self, verification_code, team_id, event_id):
        """Generate QR code for certificate verification"""
        try:
            verification_url = url_for(
                'certificates.verify',
                code=verification_code,
                _external=True
            )
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=4,
                border=2
            )
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code as temporary file
            qr_filename = f"qr_{team_id}_{event_id}_{verification_code[:8]}.png"
            qr_path = os.path.join(self.cert_dir, qr_filename)
            qr_img.save(qr_path)
            
            return qr_path
        except Exception as e:
            current_app.logger.error(f"QR code generation failed: {e}")
            return None
    
    def _create_background(self):
        """Create certificate background"""
        drawing = Drawing(800, 565)
        
        # White background with subtle gradient effect
        rect = Rect(0, 0, 800, 565, fillColor=colors.white, strokeColor=None)
        drawing.add(rect)
        
        # Add subtle pattern
        for i in range(0, 800, 50):
            line = Line(i, 0, i, 565, strokeColor=colors.HexColor('#f0f0f0'), strokeWidth=0.5)
            drawing.add(line)
        
        for i in range(0, 565, 50):
            line = Line(0, i, 800, i, strokeColor=colors.HexColor('#f0f0f0'), strokeWidth=0.5)
            drawing.add(line)
        
        return drawing
    
    def _create_border(self):
        """Create decorative border"""
        drawing = Drawing(800, 565)
        
        # Outer border
        outer_rect = Rect(10, 10, 780, 545, 
                         fillColor=None, 
                         strokeColor=colors.HexColor('#2b6eff'),
                         strokeWidth=3)
        drawing.add(outer_rect)
        
        # Inner border
        inner_rect = Rect(15, 15, 770, 535,
                         fillColor=None,
                         strokeColor=colors.HexColor('#00ffff'),
                         strokeWidth=1.5)
        drawing.add(inner_rect)
        
        # Corner decorations
        corner_size = 30
        corners = [
            (20, 20), (760, 20), (20, 545), (760, 545)
        ]
        
        for x, y in corners:
            # Add corner accent
            corner = Rect(x, y, corner_size, corner_size,
                         fillColor=None,
                         strokeColor=colors.HexColor('#6b2eff'),
                         strokeWidth=2)
            drawing.add(corner)
        
        return drawing
    
    def _create_seal(self, rank):
        """Create official seal/stamp"""
        drawing = Drawing(800, 565)
        
        seal_size = 80
        seal_x = 700
        seal_y = 470
        
        # Circle background
        circle = Rect(seal_x, seal_y, seal_size, seal_size,
                     fillColor=colors.HexColor('#ffaa33', alpha=0.2),
                     strokeColor=colors.HexColor('#ffaa33'),
                     strokeWidth=2)
        drawing.add(circle)
        
        # Medal text
        medal_text = self._get_medal_text(rank)
        text = String(seal_x + 40, seal_y + 40, medal_text,
                     fontName='Helvetica-Bold',
                     fontSize=12,
                     fillColor=colors.HexColor('#ffaa33'))
        drawing.add(text)
        
        return drawing
    
    def _create_medal(self, medal_symbol):
        """Create medal decoration"""
        drawing = Drawing(800, 565)
        
        medal_x = 50
        medal_y = 500
        
        text = String(medal_x, medal_y, medal_symbol,
                     fontName='Helvetica-Bold',
                     fontSize=48,
                     fillColor=colors.HexColor('#ffaa33'))
        drawing.add(text)
        
        return drawing
    
    def _create_qr_section(self, qr_path, verification_code):
        """Create QR code section"""
        try:
            # Create a table for QR code and verification text
            qr_img = Image(qr_path, width=80, height=80)
            
            data = [
                [qr_img, Paragraph(f"<b>Verification Code</b><br/>{verification_code}", 
                                   ParagraphStyle('QRText', fontSize=8, alignment=TA_LEFT))]
            ]
            
            table = Table(data, colWidths=[100, 150])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            return table
        except Exception as e:
            current_app.logger.error(f"QR section creation failed: {e}")
            return Spacer(1, 1)
    
    def _create_content(self, team, event, cert_type, score=None, rank=None, custom_message=None):
        """Create certificate main content"""
        story = []
        
        # Add spacing
        story.append(Spacer(1, 40))
        
        # Certificate title
        if cert_type == 'winner':
            title_style = ParagraphStyle(
                'TitleStyle',
                fontName='Montserrat' if self.fonts_registered else 'Helvetica-Bold',
                fontSize=36,
                textColor=colors.HexColor('#ffaa33'),
                alignment=TA_CENTER,
                spaceAfter=20
            )
            title_text = f"CERTIFICATE OF ACHIEVEMENT"
        else:
            title_style = ParagraphStyle(
                'TitleStyle',
                fontName='Montserrat' if self.fonts_registered else 'Helvetica-Bold',
                fontSize=32,
                textColor=colors.HexColor('#2b6eff'),
                alignment=TA_CENTER,
                spaceAfter=20
            )
            title_text = "CERTIFICATE OF PARTICIPATION"
        
        story.append(Paragraph(title_text, title_style))
        
        # Award text
        award_style = ParagraphStyle(
            'AwardStyle',
            fontName='OpenSans' if self.fonts_registered else 'Helvetica',
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        if cert_type == 'winner':
            award_text = f"This certificate is proudly presented to"
        else:
            award_text = f"This certificate is awarded to"
        
        story.append(Paragraph(award_text, award_style))
        
        # Team name (using script font)
        name_style = ParagraphStyle(
            'NameStyle',
            fontName='GreatVibes' if self.fonts_registered else 'Helvetica-Oblique',
            fontSize=48,
            textColor=colors.HexColor('#6b2eff'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        story.append(Paragraph(team.name, name_style))
        
        # Achievement text
        if cert_type == 'winner':
            achievement_text = f"for outstanding performance in {event.name}"
            if rank == 1:
                achievement_text = f"for achieving <b>1st Place</b> with a score of {score:.1f} points in {event.name}"
            elif rank == 2:
                achievement_text = f"for achieving <b>2nd Place</b> with a score of {score:.1f} points in {event.name}"
            elif rank == 3:
                achievement_text = f"for achieving <b>3rd Place</b> with a score of {score:.1f} points in {event.name}"
        else:
            achievement_text = f"for participation and contribution to {event.name}"
        
        achievement_style = ParagraphStyle(
            'AchievementStyle',
            fontName='OpenSans' if self.fonts_registered else 'Helvetica',
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        story.append(Paragraph(achievement_text, achievement_style))
        
        # Custom message
        if custom_message:
            msg_style = ParagraphStyle(
                'MessageStyle',
                fontName='OpenSans' if self.fonts_registered else 'Helvetica-Oblique',
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#666666'),
                spaceAfter=20
            )
            story.append(Paragraph(custom_message, msg_style))
        
        # Event details
        details_style = ParagraphStyle(
            'DetailsStyle',
            fontName='OpenSans' if self.fonts_registered else 'Helvetica',
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#999999'),
            spaceAfter=10
        )
        
        event_date = event.event_date.strftime('%B %d, %Y') if event.event_date else 'TBD'
        details = f"Event: {event.name} | Date: {event_date} | Venue: {event.venue or 'TBD'}"
        story.append(Paragraph(details, details_style))
        
        # Team members (for participation certificates)
        if cert_type == 'participation' and team.members:
            story.append(Spacer(1, 10))
            members_text = "<b>Team Members:</b><br/>"
            members_text += ", ".join(team.members)
            members_style = ParagraphStyle(
                'MembersStyle',
                fontName='OpenSans' if self.fonts_registered else 'Helvetica',
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#666666')
            )
            story.append(Paragraph(members_text, members_style))
        
        # Signature section
        story.append(Spacer(1, 40))
        
        # Create signature table
        sig_data = [
            ["", ""],
            ["_________________________", "_________________________"],
            ["Event Coordinator", "Organizing Committee"]
        ]
        
        sig_table = Table(sig_data, colWidths=[300, 300])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, 1), 'OpenSans' if self.fonts_registered else 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, 1), 10),
            ('TOPPADDING', (0, 1), (-1, 1), 20),
        ]))
        
        story.append(sig_table)
        
        # Date of issue
        date_style = ParagraphStyle(
            'DateStyle',
            fontName='OpenSans' if self.fonts_registered else 'Helvetica',
            fontSize=9,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#999999')
        )
        issue_date = datetime.utcnow().strftime('%B %d, %Y')
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"Issued on: {issue_date}", date_style))
        
        return story
    
    def _get_medal_symbol(self, rank):
        """Get medal symbol based on rank"""
        medals = {
            1: "🥇",
            2: "🥈", 
            3: "🥉"
        }
        return medals.get(rank, "🏆")
    
    def _get_medal_text(self, rank):
        """Get medal text based on rank"""
        medals = {
            1: "1st PLACE",
            2: "2nd PLACE",
            3: "3rd PLACE"
        }
        return medals.get(rank, "WINNER")
    
    def generate_bulk_certificates(self, event, teams_with_scores):
        """
        Generate certificates for all teams in an event
        
        Args:
            event: Event object
            teams_with_scores: List of dicts with team, score, rank
            
        Returns:
            dict: {
                'total': int,
                'generated': int,
                'failed': int,
                'certificates': list
            }
        """
        results = {
            'total': len(teams_with_scores),
            'generated': 0,
            'failed': 0,
            'certificates': []
        }
        
        for team_data in teams_with_scores:
            try:
                certificate = self.generate_certificate(
                    team=team_data['team'],
                    event=event,
                    score=team_data.get('score'),
                    rank=team_data.get('rank')
                )
                results['certificates'].append(certificate)
                results['generated'] += 1
            except Exception as e:
                current_app.logger.error(f"Certificate generation failed for team {team_data['team'].id}: {e}")
                results['failed'] += 1
        
        return results
    
    def delete_certificate(self, certificate_file):
        """Delete certificate file"""
        try:
            filepath = os.path.join(self.cert_dir, certificate_file)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            current_app.logger.error(f"Certificate deletion failed: {e}")
        return False
    
    def get_certificate_info(self, verification_code):
        """Get certificate information by verification code"""
        # This would query the database in production
        # For now, return dummy data
        return {
            'verification_code': verification_code,
            'valid': True,
            'issued_date': datetime.utcnow(),
            'team_name': 'Demo Team',
            'event_name': 'Demo Event',
            'certificate_type': 'participation'
        }