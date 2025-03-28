#!/usr/bin/env python3
"""
Notifications module for the Universal Media Converter
Handles email, webhook notifications for job events
"""

import os
import json
import logging
import smtplib
import threading
import requests
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from utils.database import get_setting, update_setting, add_notification, log_event

# Setup logging
logger = logging.getLogger(__name__)

# Thread safety for notification sending
notification_lock = threading.Lock()

# Constants
DEFAULT_EMAIL_TEMPLATE = """
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #1f2937; color: white; padding: 20px; text-align: center;">
        <h1>Universal Media Converter</h1>
        <h2>Job {status}</h2>
    </div>
    <div style="padding: 20px; background-color: #f9fafb;">
        <p><strong>Job ID:</strong> {job_id}</p>
        <p><strong>Media:</strong> {media_source}</p>
        <p><strong>Type:</strong> {media_type}</p>
        <p><strong>Status:</strong> {status}</p>
        <p><strong>Started:</strong> {start_time}</p>
        <p><strong>Completed:</strong> {end_time}</p>
        {error_info}
    </div>
    <div style="background-color: #1f2937; color: white; padding: 10px; text-align: center;">
        <p>Universal Media Converter - {timestamp}</p>
    </div>
</body>
</html>
"""

DEFAULT_WEBHOOK_PAYLOAD = {
    "job_id": "{job_id}",
    "status": "{status}",
    "media_source": "{media_source}",
    "media_type": "{media_type}",
    "output_format": "{output_format}",
    "start_time": "{start_time}",
    "end_time": "{end_time}",
    "output_file": "{output_file}",
    "error": "{error}",
    "hostname": "{hostname}",
    "event_time": "{timestamp}"
}

# Notification types
NOTIFICATION_TYPES = {
    'JOB_STARTED': 'Job Started',
    'JOB_COMPLETED': 'Job Completed',
    'JOB_FAILED': 'Job Failed',
    'JOB_CANCELLED': 'Job Cancelled',
    'SYSTEM_ERROR': 'System Error',
    'DISK_SPACE_LOW': 'Disk Space Low',
    'SYSTEM_STARTUP': 'System Started',
    'SYSTEM_SHUTDOWN': 'System Shutting Down'
}

def format_notification_template(template: str, job_data: Dict[str, Any]) -> str:
    """Format a notification template with job data"""
    # Create a copy of the data with defaults
    data = {
        'job_id': 'Unknown',
        'status': 'Unknown',
        'media_source': 'Unknown',
        'media_type': 'Unknown',
        'output_format': 'Unknown',
        'start_time': 'Unknown',
        'end_time': 'Unknown',
        'output_file': 'None',
        'error': 'None',
        'hostname': 'Unknown',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Update with actual job data
    data.update(job_data)
    
    # Format timestamps if they're epoch timestamps
    if isinstance(data.get('created_at'), (int, float)):
        data['start_time'] = datetime.fromtimestamp(data['created_at']).strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(data.get('end_time'), (int, float)):
        data['end_time'] = datetime.fromtimestamp(data['end_time']).strftime('%Y-%m-%d %H:%M:%S')
    
    # Add error info if present
    if data.get('error') and data['error'] != 'None':
        data['error_info'] = f'<p><strong>Error:</strong> {data["error"]}</p>'
    else:
        data['error_info'] = ''
    
    # Format template
    return template.format(**data)

def send_email_notification(subject: str, body: str, recipients: List[str]) -> bool:
    """Send an email notification"""
    with notification_lock:
        try:
            # Get email settings from database
            smtp_server = get_setting('smtp_server')
            smtp_port = int(get_setting('smtp_port', '587'))
            smtp_username = get_setting('smtp_username')
            smtp_password = get_setting('smtp_password')
            from_email = get_setting('notification_from_email')
            
            # Validate settings
            if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_email]):
                logger.warning("Email notification settings not configured")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = ', '.join(recipients)
            
            # Attach HTML content
            msg.attach(MIMEText(body, 'html'))
            
            # Connect to SMTP server
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False

def send_webhook_notification(webhook_url: str, payload: Dict[str, Any]) -> bool:
    """Send a webhook notification"""
    with notification_lock:
        try:
            # Get webhook settings
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Universal Media Converter'
            }
            
            # Get custom headers if configured
            custom_headers = get_setting('webhook_headers')
            if custom_headers:
                try:
                    custom_headers_dict = json.loads(custom_headers)
                    headers.update(custom_headers_dict)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in webhook_headers setting: {custom_headers}")
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code < 300:
                logger.info(f"Webhook notification sent to {webhook_url} - Status: {response.status_code}")
                return True
            else:
                logger.warning(f"Webhook notification failed - Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False

def notify(notification_type: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send notifications based on configured channels"""
    results = {
        'email': False,
        'webhook': False,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Check if notifications are enabled
        notifications_enabled = get_setting('notifications_enabled', 'false').lower() == 'true'
        if not notifications_enabled:
            logger.debug("Notifications are disabled")
            return results
        
        # Check if this notification type is enabled
        enabled_types = get_setting('notification_types', 'JOB_COMPLETED,JOB_FAILED').split(',')
        if notification_type not in enabled_types and 'ALL' not in enabled_types:
            logger.debug(f"Notification type {notification_type} is not enabled")
            return results
        
        # Prepare notification data
        notification_data = job_data.copy()
        notification_data['status'] = NOTIFICATION_TYPES.get(notification_type, notification_type)
        
        # Send email notifications if configured
        email_enabled = get_setting('email_notifications_enabled', 'false').lower() == 'true'
        if email_enabled:
            email_recipients = get_setting('email_recipients', '').split(',')
            email_template = get_setting('email_template', DEFAULT_EMAIL_TEMPLATE)
            
            if email_recipients:
                # Format email body
                email_body = format_notification_template(email_template, notification_data)
                
                # Send email
                subject = f"Media Converter: {NOTIFICATION_TYPES.get(notification_type, notification_type)}"
                results['email'] = send_email_notification(subject, email_body, email_recipients)
        
        # Send webhook notifications if configured
        webhook_enabled = get_setting('webhook_notifications_enabled', 'false').lower() == 'true'
        if webhook_enabled:
            webhook_url = get_setting('webhook_url')
            webhook_template = get_setting('webhook_payload_template', json.dumps(DEFAULT_WEBHOOK_PAYLOAD))
            
            if webhook_url:
                # Parse webhook template
                try:
                    webhook_payload = json.loads(webhook_template)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in webhook_payload_template setting: {webhook_template}")
                    webhook_payload = DEFAULT_WEBHOOK_PAYLOAD
                
                # Format webhook payload
                formatted_payload = {}
                for key, value in webhook_payload.items():
                    if isinstance(value, str):
                        formatted_payload[key] = format_notification_template(value, notification_data)
                    else:
                        formatted_payload[key] = value
                
                # Add notification type
                formatted_payload['notification_type'] = notification_type
                
                # Send webhook
                results['webhook'] = send_webhook_notification(webhook_url, formatted_payload)
        
        return results
        
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        return {
            'email': False,
            'webhook': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def setup_default_notifications() -> None:
    """Setup default notification settings if not already configured"""
    # Only set defaults if settings don't exist
    if get_setting('notifications_setup_completed') != 'true':
        # Default notification settings
        update_setting('notifications_enabled', 'false')
        update_setting('notification_types', 'JOB_COMPLETED,JOB_FAILED,DISK_SPACE_LOW')
        
        # Email settings
        update_setting('email_notifications_enabled', 'false')
        update_setting('smtp_server', 'smtp.example.com')
        update_setting('smtp_port', '587')
        update_setting('smtp_username', '')
        update_setting('smtp_password', '')
        update_setting('notification_from_email', 'mediaconverter@example.com')
        update_setting('email_recipients', '')
        update_setting('email_template', DEFAULT_EMAIL_TEMPLATE)
        
        # Webhook settings
        update_setting('webhook_notifications_enabled', 'false')
        update_setting('webhook_url', '')
        update_setting('webhook_headers', '{}')
        update_setting('webhook_payload_template', json.dumps(DEFAULT_WEBHOOK_PAYLOAD, indent=2))
        
        # Mark setup as completed
        update_setting('notifications_setup_completed', 'true')
        
        logger.info("Default notification settings configured")

# Initialize default settings when module is loaded
setup_default_notifications()

# Notification types
class NotificationType:
    JOB_STARTED = "JOB_STARTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    JOB_CANCELLED = "JOB_CANCELLED"
    DISK_SPACE_LOW = "DISK_SPACE_LOW"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"

# Message templates
NOTIFICATION_TEMPLATES = {
    NotificationType.JOB_STARTED: {
        "subject": "Job Started: {title}",
        "message": "Conversion job for '{title}' has started processing."
    },
    NotificationType.JOB_COMPLETED: {
        "subject": "Job Completed: {title}",
        "message": "Conversion job for '{title}' has completed successfully.\nOutput: {output_path}"
    },
    NotificationType.JOB_FAILED: {
        "subject": "Job Failed: {title}",
        "message": "Conversion job for '{title}' has failed.\nError: {error}"
    },
    NotificationType.JOB_CANCELLED: {
        "subject": "Job Cancelled: {title}",
        "message": "Conversion job for '{title}' was cancelled."
    },
    NotificationType.DISK_SPACE_LOW: {
        "subject": "Low Disk Space Warning",
        "message": "Media Converter is running low on disk space: {available_space}GB available ({percent_used}% used)."
    },
    NotificationType.SYSTEM_ERROR: {
        "subject": "System Error",
        "message": "A system error has occurred in the Media Converter: {error}"
    },
    NotificationType.SYSTEM_STARTUP: {
        "subject": "Media Converter Started",
        "message": "The Media Converter service has started."
    },
    NotificationType.SYSTEM_SHUTDOWN: {
        "subject": "Media Converter Shutting Down",
        "message": "The Media Converter service is shutting down."
    }
}

def format_notification(notification_type: str, data: Dict[str, Any]) -> Dict[str, str]:
    """Format a notification message and subject using templates"""
    template = NOTIFICATION_TEMPLATES.get(notification_type, {
        "subject": f"Notification: {notification_type}",
        "message": json.dumps(data, indent=2)
    })
    
    try:
        # Format template with data
        subject = template["subject"].format(**data)
        message = template["message"].format(**data)
        
        return {
            "subject": subject,
            "message": message
        }
    except KeyError as e:
        logger.error(f"Error formatting notification: missing key {e}")
        # Fallback to basic message
        return {
            "subject": f"Notification: {notification_type}",
            "message": json.dumps(data, indent=2)
        }
    except Exception as e:
        logger.error(f"Error formatting notification: {e}")
        return {
            "subject": f"Notification: {notification_type}",
            "message": f"Error formatting message: {str(e)}"
        }

def should_notify(notification_type: str) -> bool:
    """Check if notifications should be sent for this type"""
    try:
        # Check if notifications are enabled at all
        if get_setting("notifications_enabled", "true").lower() != "true":
            return False
        
        # Get enabled notification types
        notify_types_str = get_setting("notification_types", "JOB_COMPLETED,JOB_FAILED,SYSTEM_ERROR")
        notify_types = [t.strip() for t in notify_types_str.split(",")]
        
        # Special case: if "all" is in the list, notify for all types
        if "all" in notify_types or "ALL" in notify_types:
            return True
            
        return notification_type in notify_types
    except Exception as e:
        logger.error(f"Error checking notification settings: {e}")
        return False

def notify(
    notification_type: str, 
    data: Dict[str, Any],
    job_id: Optional[str] = None
) -> bool:
    """
    Send notifications through all configured channels
    Returns True if at least one notification was sent successfully
    """
    try:
        # Check if we should send notifications for this type
        if not should_notify(notification_type):
            logger.debug(f"Notifications disabled for type: {notification_type}")
            return False
        
        # Format the notification
        formatted = format_notification(notification_type, data)
        
        # Add to database (internal notification)
        add_notification(notification_type, formatted["message"], job_id)
        
        # Track if any external notifications were sent
        any_sent = False
        
        # Send email if enabled
        if get_setting("email_notifications_enabled", "false").lower() == "true":
            email_sent = send_email_notification(
                formatted["subject"],
                formatted["message"]
            )
            any_sent = any_sent or email_sent
        
        # Send webhook if enabled
        if get_setting("webhook_notifications_enabled", "false").lower() == "true":
            webhook_sent = send_webhook_notification(get_setting("webhook_url"), {
                "notification_type": notification_type,
                "timestamp": int(time.time()),
                "subject": formatted["subject"],
                "message": formatted["message"],
                "data": data
            })
            any_sent = any_sent or webhook_sent
        
        # Log the notification
        log_event("NOTIFICATION_SENT", {
            "type": notification_type,
            "job_id": job_id,
            "success": any_sent
        })
        
        return True
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

def notify_job_started(job_data: Dict[str, Any]) -> bool:
    """Convenience function to notify about job start"""
    return notify(
        NotificationType.JOB_STARTED,
        {
            "title": job_data.get("title", "Unknown Job"),
            "id": job_data.get("id"),
            "source": job_data.get("source", "Unknown Source")
        },
        job_data.get("id")
    )

def notify_job_completed(job_data: Dict[str, Any]) -> bool:
    """Convenience function to notify about job completion"""
    return notify(
        NotificationType.JOB_COMPLETED,
        {
            "title": job_data.get("title", "Unknown Job"),
            "id": job_data.get("id"),
            "output_path": job_data.get("output_path", "Unknown Output")
        },
        job_data.get("id")
    )

def notify_job_failed(job_data: Dict[str, Any], error: str) -> bool:
    """Convenience function to notify about job failure"""
    return notify(
        NotificationType.JOB_FAILED,
        {
            "title": job_data.get("title", "Unknown Job"),
            "id": job_data.get("id"),
            "error": error
        },
        job_data.get("id")
    )

def notify_job_cancelled(job_data: Dict[str, Any]) -> bool:
    """Convenience function to notify about job cancellation"""
    return notify(
        NotificationType.JOB_CANCELLED,
        {
            "title": job_data.get("title", "Unknown Job"),
            "id": job_data.get("id")
        },
        job_data.get("id")
    )

def notify_system_error(error: str) -> bool:
    """Convenience function to notify about system error"""
    return notify(
        NotificationType.SYSTEM_ERROR,
        {"error": error}
    )

def notify_disk_space_low(available_gb: float, percent_used: float) -> bool:
    """Convenience function to notify about low disk space"""
    return notify(
        NotificationType.DISK_SPACE_LOW,
        {
            "available_space": round(available_gb, 2),
            "percent_used": round(percent_used, 2)
        }
    )

def notify_system_startup() -> bool:
    """Convenience function to notify about system startup"""
    return notify(
        NotificationType.SYSTEM_STARTUP,
        {"timestamp": int(time.time())}
    )

def notify_system_shutdown() -> bool:
    """Convenience function to notify about system shutdown"""
    return notify(
        NotificationType.SYSTEM_SHUTDOWN,
        {"timestamp": int(time.time())}
    )

# Initialize by checking if we should send a startup notification
if get_setting("notifications_enabled", "true").lower() == "true":
    try:
        notify_system_startup()
    except Exception as e:
        logger.error(f"Error sending startup notification: {e}") 