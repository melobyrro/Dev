"""
Email notification service for scheduler alerts
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


def send_scheduler_alert(subject: str, body: str):
    """
    Send email alert about scheduler issues

    Args:
        subject: Email subject line
        body: Email body text
    """
    try:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        alert_email = os.getenv("ALERT_EMAIL")

        if not all([smtp_host, smtp_user, smtp_pass, alert_email]):
            logger.warning("SMTP not configured, skipping email alert")
            return

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = alert_email
        msg['Subject'] = f"[CultoTranscript Scheduler] {subject}"
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"Alert email sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
