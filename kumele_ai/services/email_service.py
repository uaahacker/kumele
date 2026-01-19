"""
Email Service - Handles support email sending via SMTP
"""
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_pass = settings.SMTP_PASS
        self.from_email = settings.SMTP_FROM_EMAIL
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an email"""
        try:
            # Create message
            if html_body:
                message = MIMEMultipart("alternative")
                message.attach(MIMEText(body, "plain"))
                message.attach(MIMEText(html_body, "html"))
            else:
                message = MIMEText(body, "plain")
            
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to_email
            
            if reply_to:
                message["Reply-To"] = reply_to
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=True
            ) as smtp:
                if self.smtp_user and self.smtp_pass:
                    await smtp.login(self.smtp_user, self.smtp_pass)
                
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
            return {
                "success": True,
                "message": "Email sent successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_support_reply(
        self,
        to_email: str,
        subject: str,
        reply_body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a support email reply"""
        # Add support signature
        full_body = f"""{reply_body}

---
Kumele Support Team
This is an automated response. For urgent matters, please reply to this email.
"""
        
        # Format subject for reply
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            body=full_body,
            reply_to=self.from_email
        )


# Singleton instance
email_service = EmailService()
