"""
Email background tasks.
"""
from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="worker.tasks.email_tasks.send_email")
def send_email(self, to_email: str, subject: str, body: str, html_body: str = None):
    """
    Send an email asynchronously.
    """
    logger.info(f"Sending email to {to_email}")
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.config import settings
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        
        # Attach plain text
        part1 = MIMEText(body, "plain")
        msg.attach(part1)
        
        # Attach HTML if provided
        if html_body:
            part2 = MIMEText(html_body, "html")
            msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        
        logger.info(f"Email sent to {to_email}")
        return {"success": True, "to": to_email}
        
    except Exception as e:
        logger.error(f"Email send error: {e}")
        self.retry(exc=e, countdown=300, max_retries=3)


@celery_app.task(name="worker.tasks.email_tasks.process_incoming_email")
def process_incoming_email(email_data: dict):
    """
    Process incoming support email.
    """
    logger.info(f"Processing incoming email from {email_data.get('from_email')}")
    
    try:
        import asyncio
        from app.database import async_session_maker
        from app.services.support_service import SupportService
        
        async def run_process():
            async with async_session_maker() as db:
                result = await SupportService.process_incoming_email(
                    db=db,
                    from_email=email_data["from_email"],
                    subject=email_data["subject"],
                    body=email_data["body"],
                    user_id=email_data.get("user_id"),
                    thread_id=email_data.get("thread_id")
                )
                await db.commit()
                return result
        
        result = asyncio.run(run_process())
        logger.info(f"Processed email: {result.get('email_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Email process error: {e}")
        raise


@celery_app.task(name="worker.tasks.email_tasks.send_support_reply")
def send_support_reply(email_id: str, reply_body: str, agent_id: str):
    """
    Send support reply and update database.
    """
    logger.info(f"Sending support reply for {email_id}")
    
    try:
        import asyncio
        from app.database import async_session_maker
        from app.services.support_service import SupportService
        
        async def run_reply():
            async with async_session_maker() as db:
                # Get original email
                details = await SupportService.get_email_details(db, email_id)
                
                if "error" in details:
                    return {"error": details["error"]}
                
                # Send reply
                result = await SupportService.reply_to_email(
                    db=db,
                    email_id=email_id,
                    reply_body=reply_body,
                    agent_id=agent_id
                )
                
                # Actually send email
                if result.get("success"):
                    send_email.delay(
                        to_email=details["from_email"],
                        subject=f"Re: {details['subject']}",
                        body=reply_body
                    )
                
                await db.commit()
                return result
        
        result = asyncio.run(run_reply())
        logger.info(f"Reply sent for {email_id}")
        return result
        
    except Exception as e:
        logger.error(f"Reply error: {e}")
        raise


@celery_app.task(name="worker.tasks.email_tasks.send_notification")
def send_notification(user_id: str, notification_type: str, data: dict):
    """
    Send notification to user.
    """
    logger.info(f"Sending {notification_type} notification to {user_id}")
    
    try:
        import asyncio
        from sqlalchemy import select
        from app.database import async_session_maker
        from app.models.database_models import User
        import uuid
        
        async def get_user_email():
            async with async_session_maker() as db:
                query = select(User.email).where(User.id == uuid.UUID(user_id))
                result = await db.execute(query)
                return result.scalar_one_or_none()
        
        email = asyncio.run(get_user_email())
        
        if not email:
            return {"error": "User not found"}
        
        # Generate notification content based on type
        templates = {
            "event_reminder": {
                "subject": f"Reminder: {data.get('event_name', 'Your event')} is coming up!",
                "body": f"Don't forget about {data.get('event_name')} on {data.get('event_date')}."
            },
            "rating_request": {
                "subject": "How was your experience?",
                "body": f"Please rate your experience at {data.get('event_name')}."
            },
            "new_recommendation": {
                "subject": "New events you might like!",
                "body": "We found some new events based on your interests."
            }
        }
        
        template = templates.get(notification_type, {
            "subject": "Notification from Kumele",
            "body": str(data)
        })
        
        # Send email
        send_email.delay(
            to_email=email,
            subject=template["subject"],
            body=template["body"]
        )
        
        return {"success": True, "type": notification_type}
        
    except Exception as e:
        logger.error(f"Notification error: {e}")
        raise
