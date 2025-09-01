"""Email service for automatic delivery of summaries and digests."""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict
from datetime import datetime, date
from pathlib import Path
import json
import os

from config import Config
from database import db

# Set up logging
logger = logging.getLogger(__name__)

class EmailService:
    """Handles automated email delivery for radio synopsis."""
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')
        self.email_from = os.getenv('EMAIL_FROM', self.smtp_user)
        self.email_to = os.getenv('EMAIL_TO', '').split(',')
        self.email_enabled = os.getenv('ENABLE_EMAIL', 'false').lower() == 'true'
        
        # Clean email list
        self.email_to = [email.strip() for email in self.email_to if email.strip()]
        
        if self.email_enabled and not self._validate_config():
            logger.warning("Email configuration incomplete. Email delivery disabled.")
            self.email_enabled = False
    
    def _validate_config(self) -> bool:
        """Validate email configuration."""
        required_fields = [self.smtp_host, self.smtp_user, self.smtp_pass, self.email_from]
        
        if not all(required_fields):
            logger.error("Missing required email configuration")
            return False
        
        if not self.email_to:
            logger.error("No recipient email addresses configured")
            return False
        
        return True
    
    def _create_smtp_connection(self):
        """Create and configure SMTP connection."""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.smtp_user, self.smtp_pass)
        return server
    
    def _send_email(self, subject: str, body_text: str, body_html: str = None, 
                   attachments: List[Path] = None) -> bool:
        """Send email with optional HTML body and attachments."""
        if not self.email_enabled:
            logger.info(f"Email disabled. Would send: {subject}")
            return True
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = subject
            
            # Add text body
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            
            # Add HTML body if provided
            if body_html:
                msg.attach(MIMEText(body_html, 'html', 'utf-8'))
            
            # Add attachments if provided
            if attachments:
                for attachment_path in attachments:
                    if attachment_path.exists():
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {attachment_path.name}'
                            )
                            msg.attach(part)
            
            # Send email
            with self._create_smtp_connection() as server:
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email '{subject}': {e}")
            return False
    
    def send_block_summary(self, block_id: int) -> bool:
        """Send block summary email to stakeholders."""
        try:
            # Get block and summary data
            block = db.get_block(block_id)
            if not block:
                logger.error(f"Block {block_id} not found")
                return False
            
            summary = db.get_summary(block_id)
            if not summary:
                logger.error(f"Summary for block {block_id} not found")
                return False
            
            # Get block configuration
            block_config = Config.BLOCKS.get(block['block_code'], {})
            block_name = block_config.get('name', f"Block {block['block_code']}")
            
            # Format date
            show_date = block['show_date'].strftime('%B %d, %Y') if block.get('show_date') else 'Unknown Date'
            
            # Create subject
            subject = f"[Brass Tacks] Block {block['block_code']} Summary – {show_date}"
            
            # Create email body
            body_text = self._create_block_summary_text(block, summary, block_name, show_date)
            body_html = self._create_block_summary_html(block, summary, block_name, show_date)
            
            # Send email
            return self._send_email(subject, body_text, body_html)
            
        except Exception as e:
            logger.error(f"Error sending block summary email: {e}")
            return False
    
    def _create_block_summary_text(self, block: Dict, summary: Dict, 
                                  block_name: str, show_date: str) -> str:
        """Create plain text email body for block summary."""
        
        text = f"""DOWN TO BRASS TACKS - BLOCK SUMMARY
{'=' * 50}

Date: {show_date}
Block: {block['block_code']} - {block_name}
Time: {block.get('start_time', 'N/A')} - {block.get('end_time', 'N/A')}
Callers: {summary.get('caller_count', 0)}

EXECUTIVE SUMMARY
{'-' * 20}
{summary.get('summary_text', 'No summary available')[:500]}
"""
        
        # Add key points
        key_points = summary.get('key_points', [])
        if key_points:
            text += f"\n\nKEY POINTS\n{'-' * 12}\n"
            for i, point in enumerate(key_points[:5], 1):
                text += f"{i}. {point}\n"
        
        # Add notable quotes
        quotes = summary.get('quotes', [])
        if quotes:
            text += f"\n\nNOTABLE QUOTES\n{'-' * 15}\n"
            for quote in quotes[:3]:
                speaker = quote.get('speaker', 'Unknown')
                text += f"• \"{quote.get('text', '')}\"\n  - {speaker}\n\n"
        
        # Add entities
        entities = summary.get('entities', [])
        if entities:
            text += f"\nKEY ENTITIES MENTIONED\n{'-' * 22}\n"
            text += ", ".join(entities[:10]) + "\n"
        
        # Footer
        text += f"""
{'=' * 50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}
System: Radio Synopsis Automated Briefing
Contact: Technical Support for questions

📊 For deeper analytics and detailed insights:
View caller segments, timeline analysis & dashboard at:
https://echobot-docker-app.azurewebsites.net/
"""
        
        return text
    
    def _create_block_summary_html(self, block: Dict, summary: Dict, 
                                  block_name: str, show_date: str) -> str:
        """Create HTML email body for block summary."""
        
        # Color scheme matching the dashboard
        primary_red = "#c41e3a"
        gold_accent = "#ffc107"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, {primary_red}, #dc3545); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .header p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .summary-box {{ background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid {gold_accent}; }}
        .key-points {{ margin: 20px 0; }}
        .key-points ul {{ list-style: none; padding: 0; }}
        .key-points li {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 3px solid {primary_red}; }}
        .quotes {{ margin: 20px 0; }}
        .quote {{ background: #fff; padding: 15px; margin: 10px 0; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 3px solid {gold_accent}; }}
        .quote-text {{ font-style: italic; font-size: 16px; margin-bottom: 8px; }}
        .quote-speaker {{ font-weight: 600; color: {primary_red}; }}
        .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 24px; font-weight: 600; color: {primary_red}; }}
        .stat-label {{ font-size: 14px; color: #6c757d; }}
        .entities {{ background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 20px 0; }}
        .entity-tag {{ display: inline-block; background: {gold_accent}; color: #212529; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin: 2px; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📻 Down to Brass Tacks - Block Summary</h1>
            <p>{show_date} • Block {block['block_code']} - {block_name}</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{summary.get('caller_count', 0)}</div>
                    <div class="stat-label">Callers</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{block.get('duration', 'N/A')}</div>
                    <div class="stat-label">Duration</div>
                </div>
            </div>
            
            <div class="summary-box">
                <h3 style="margin-top: 0; color: {primary_red};">📋 Executive Summary</h3>
                <p style="line-height: 1.6; margin-bottom: 0;">{summary.get('summary_text', 'No summary available')[:500]}...</p>
            </div>
"""
        
        # Add key points
        key_points = summary.get('key_points', [])
        if key_points:
            html += f"""
            <div class="key-points">
                <h3 style="color: {primary_red};">🔑 Key Points</h3>
                <ul>
"""
            for point in key_points[:5]:
                html += f"                    <li>{point}</li>\n"
            html += "                </ul>\n            </div>\n"
        
        # Add quotes
        quotes = summary.get('quotes', [])
        if quotes:
            html += f"""
            <div class="quotes">
                <h3 style="color: {primary_red};">💬 Notable Quotes</h3>
"""
            for quote in quotes[:3]:
                speaker = quote.get('speaker', 'Unknown Speaker')
                html += f"""
                <div class="quote">
                    <div class="quote-text">"{quote.get('text', '')}"</div>
                    <div class="quote-speaker">— {speaker}</div>
                </div>
"""
            html += "            </div>\n"
        
        # Add entities
        entities = summary.get('entities', [])
        if entities:
            html += f"""
            <div class="entities">
                <h3 style="margin-top: 0; color: {primary_red};">🏢 Key Entities Mentioned</h3>
"""
            for entity in entities[:15]:
                html += f'                <span class="entity-tag">{entity}</span>\n'
            html += "            </div>\n"
        
        # Footer
        html += f"""
        </div>
        
        <div class="footer">
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}</p>
            <p>Radio Synopsis Automated Briefing System</p>
            <p>📧 Contact technical support for questions</p>
            <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
            <p style="font-size: 16px; color: {primary_red}; font-weight: 600;">
                📊 For deeper analytics and detailed insights:
            </p>
            <p>
                <a href="https://echobot-docker-app.azurewebsites.net/" 
                   style="color: {primary_red}; text-decoration: none; font-weight: 600;">
                    View caller segments, timeline analysis & full dashboard →
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def send_daily_digest(self, show_date: date) -> bool:
        """Send daily digest email to stakeholders."""
        try:
            # Get daily digest
            digest = db.get_daily_digest(show_date)
            if not digest:
                logger.error(f"Daily digest for {show_date} not found")
                return False
            
            # Get blocks summary
            blocks = db.get_blocks_by_date(show_date)
            completed_blocks = [b for b in blocks if b['status'] == 'completed']
            
            # Format date
            formatted_date = show_date.strftime('%B %d, %Y')
            
            # Create subject
            subject = f"[Brass Tacks] Daily Digest – {formatted_date}"
            
            # Create email body
            body_text = self._create_daily_digest_text(digest, show_date, completed_blocks)
            body_html = self._create_daily_digest_html(digest, show_date, completed_blocks)
            
            # Send email
            return self._send_email(subject, body_text, body_html)
            
        except Exception as e:
            logger.error(f"Error sending daily digest email: {e}")
            return False
    
    def _create_daily_digest_text(self, digest: Dict, show_date: date, 
                                 completed_blocks: List[Dict]) -> str:
        """Create plain text daily digest email."""
        
        formatted_date = show_date.strftime('%B %d, %Y')
        
        text = f"""DOWN TO BRASS TACKS - DAILY DIGEST
{'=' * 50}

Date: {formatted_date}
Blocks Processed: {len(completed_blocks)}/4
Total Callers: {digest.get('total_callers', 0)}

DAILY SUMMARY
{'-' * 15}
{digest.get('digest_text', 'No digest available')}

{'=' * 50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}
System: Radio Synopsis Automated Briefing
Contact: Technical Support for questions

📊 For deeper analytics and detailed insights:
View full archive, caller segments & dashboard at:
https://echobot-docker-app.azurewebsites.net/
"""
        
        return text
    
    def _create_daily_digest_html(self, digest: Dict, show_date: date, 
                                 completed_blocks: List[Dict]) -> str:
        """Create HTML daily digest email."""
        
        primary_red = "#c41e3a"
        gold_accent = "#ffc107"
        formatted_date = show_date.strftime('%B %d, %Y')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, {primary_red}, #dc3545); color: white; padding: 40px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
        .header p {{ margin: 15px 0 0 0; font-size: 18px; opacity: 0.9; }}
        .content {{ padding: 40px; }}
        .digest-content {{ background: #f8f9fa; padding: 30px; border-radius: 8px; margin: 20px 0; border-left: 6px solid {gold_accent}; }}
        .digest-content pre {{ white-space: pre-wrap; font-family: 'Segoe UI', sans-serif; line-height: 1.6; margin: 0; }}
        .stats {{ display: flex; justify-content: space-around; margin: 30px 0; }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 32px; font-weight: 600; color: {primary_red}; }}
        .stat-label {{ font-size: 16px; color: #6c757d; margin-top: 5px; }}
        .footer {{ background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📰 Down to Brass Tacks - Daily Digest</h1>
            <p>{formatted_date}</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(completed_blocks)}</div>
                    <div class="stat-label">Blocks Processed</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{digest.get('total_callers', 0)}</div>
                    <div class="stat-label">Total Callers</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{round(len(completed_blocks)/4*100)}%</div>
                    <div class="stat-label">Completion Rate</div>
                </div>
            </div>
            
            <div class="digest-content">
                <h3 style="margin-top: 0; color: {primary_red};">📋 Executive Daily Briefing</h3>
                <pre>{digest.get('digest_text', 'No digest available')}</pre>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}</p>
            <p>Radio Synopsis Automated Briefing System</p>
            <p>📧 Contact technical support for questions</p>
            <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
            <p style="font-size: 16px; color: {primary_red}; font-weight: 600;">
                📊 For deeper analytics and detailed insights:
            </p>
            <p>
                <a href="https://echobot-docker-app.azurewebsites.net/" 
                   style="color: {primary_red}; text-decoration: none; font-weight: 600;">
                    View full archive, caller segments & dashboard →
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def send_test_email(self) -> bool:
        """Send a test email to verify configuration."""
        subject = "[Brass Tacks] Test Email - System Configuration"
        body_text = f"""This is a test email from the Radio Synopsis system.

Configuration Test Results:
- SMTP Host: {self.smtp_host}
- SMTP Port: {self.smtp_port}
- From Address: {self.email_from}
- Recipients: {', '.join(self.email_to)}
- Email Enabled: {self.email_enabled}

If you receive this email, the email service is configured correctly.

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}
"""
        
        return self._send_email(subject, body_text)
    
    def get_status(self) -> Dict:
        """Get email service status."""
        return {
            'enabled': self.email_enabled,
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'from_address': self.email_from,
            'recipients': self.email_to,
            'recipient_count': len(self.email_to),
            'configuration_valid': self._validate_config()
        }

# Global email service instance
email_service = EmailService()

if __name__ == "__main__":
    # Test the email service
    logging.basicConfig(level=logging.INFO)
    
    print("Email Service Status:")
    status = email_service.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    if status['enabled']:
        print("\nSending test email...")
        success = email_service.send_test_email()
        print(f"Test email result: {'Success' if success else 'Failed'}")
    else:
        print("\nEmail service is disabled. Configure environment variables to enable.")
