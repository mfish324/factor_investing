"""
Email alerting for unattended trading runs.

Sends via SMTP using SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/ALERT_EMAIL_TO
from config.py. If those aren't configured, send_alert() logs a warning and
no-ops so the rest of the codebase (including tests/CI) works without SMTP set up.
"""

import logging
import smtplib
from email.message import EmailMessage

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO

logger = logging.getLogger(__name__)


def send_alert(subject: str, body: str) -> bool:
    """
    Send an email alert. Returns True if sent, False if skipped/failed.
    """
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL_TO):
        logger.warning(f"Alert not sent (SMTP not configured): {subject}")
        return False

    msg = EmailMessage()
    msg['Subject'] = f"[factor_investing] {subject}"
    msg['From'] = SMTP_USER
    msg['To'] = ALERT_EMAIL_TO
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Alert sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        return False
