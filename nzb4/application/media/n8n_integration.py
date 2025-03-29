#!/usr/bin/env python3
"""
N8N Integration module for media services.

This module provides integration with N8N for workflow automation 
and external API integrations.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
import logging
import hmac
import hashlib
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from nzb4.application.media.security import SecurityValidator
from nzb4.config.settings import config

# Set up logging
logger = logging.getLogger(__name__)

# Default N8N endpoint
DEFAULT_N8N_HOST = os.environ.get('N8N_HOST', 'localhost')
DEFAULT_N8N_PORT = os.environ.get('N8N_PORT', '5678')
DEFAULT_N8N_URL = f"http://{DEFAULT_N8N_HOST}:{DEFAULT_N8N_PORT}"

# N8N API credentials from env vars
N8N_API_KEY = os.environ.get('N8N_API_KEY', '')
N8N_WEBHOOK_SECRET = os.environ.get('N8N_WEBHOOK_SECRET', '')

# Encrypted API key storage if env not set
ENCRYPTED_API_KEYS = {}
if not N8N_API_KEY and not N8N_WEBHOOK_SECRET:
    # Create a default encrypted key if not available
    salt = os.environ.get('N8N_SALT', None)
    default_key = SecurityValidator.secure_random_string(32)
    ENCRYPTED_API_KEYS['n8n_api_key'] = SecurityValidator.encrypt_api_key(default_key, salt)
    
    # Log key generation for initial setup only
    logger.info(f"Generated default N8N API key: {default_key} - save this for your workflows")


class MediaN8nIntegration:
    """Integration with N8N for workflow automation"""
    
    def __init__(self, 
                n8n_url: Optional[str] = None, 
                api_key: Optional[str] = None,
                webhook_secret: Optional[str] = None):
        """
        Initialize N8N integration
        
        Args:
            n8n_url: URL for N8N server (defaults to environment variable)
            api_key: API key for N8N (defaults to environment variable)
            webhook_secret: Secret for webhook verification (defaults to environment variable)
        """
        self.n8n_url = n8n_url or DEFAULT_N8N_URL
        self.api_key = api_key or N8N_API_KEY
        self.webhook_secret = webhook_secret or N8N_WEBHOOK_SECRET
        
        # Validate URL
        is_valid, error = SecurityValidator.validate_url(self.n8n_url)
        if not is_valid:
            logger.warning(f"Invalid N8N URL: {error}")
    
    def trigger_workflow(self, 
                       workflow_id: str, 
                       payload: Dict[str, Any],
                       webhook_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger a workflow in N8N
        
        Args:
            workflow_id: ID of the workflow to trigger
            payload: Data to send to the workflow
            webhook_path: Custom webhook path (if not using ID directly)
            
        Returns:
            Dict: Response from N8N
        """
        try:
            # Construct webhook URL
            if webhook_path:
                webhook_url = f"{self.n8n_url}/webhook/{webhook_path}"
            else:
                webhook_url = f"{self.n8n_url}/webhook/{workflow_id}"
            
            # Add security timestamp to payload
            payload['_timestamp'] = int(time.time())
                        
            # Create request
            headers = {
                "Content-Type": "application/json"
            }
            
            # Add API key authentication if available
            if self.api_key:
                headers["X-N8N-API-KEY"] = self.api_key
            
            # Add signature if webhook secret is available
            if self.webhook_secret:
                data_str = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    self.webhook_secret.encode('utf-8'),
                    data_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers["X-N8N-Signature"] = signature
            
            # Convert payload to JSON
            data = json.dumps(payload).encode('utf-8')
            
            # Create request
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers=headers,
                method="POST"
            )
            
            # Send request
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                
                # Parse response if it's JSON
                try:
                    return json.loads(response_data)
                except json.JSONDecodeError:
                    return {"success": True, "raw_response": response_data}
        
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"HTTP error triggering workflow: {error_msg}")
            return {"success": False, "error": f"HTTP error: {e.code}", "message": error_msg}
        
        except Exception as e:
            logger.error(f"Error triggering workflow: {e}")
            return {"success": False, "error": str(e)}
    
    def verify_webhook_request(self, 
                             headers: Dict[str, str], 
                             raw_body: str) -> bool:
        """
        Verify a webhook request signature
        
        Args:
            headers: Request headers
            raw_body: Raw request body
            
        Returns:
            bool: True if signature is valid
        """
        try:
            if not self.webhook_secret:
                # If no webhook secret is configured, we can't verify
                logger.warning("No webhook secret configured, skipping signature verification")
                return True
            
            # Get signature from headers
            signature = headers.get('X-N8N-Signature')
            if not signature:
                logger.warning("No signature in webhook request")
                return False
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                raw_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook request: {e}")
            return False
    
    def validate_api_key(self, provided_key: str) -> bool:
        """
        Validate an API key
        
        Args:
            provided_key: API key to validate
            
        Returns:
            bool: True if API key is valid
        """
        # Compare with environment variable if set
        if N8N_API_KEY:
            return hmac.compare_digest(provided_key, N8N_API_KEY)
        
        # Check against encrypted storage
        if 'n8n_api_key' in ENCRYPTED_API_KEYS:
            return SecurityValidator.verify_api_key(
                provided_key, 
                ENCRYPTED_API_KEYS['n8n_api_key']
            )
        
        # No API key configured
        logger.warning("No API key configured for validation")
        return False
    
    def notify_job_status(self, 
                         job_id: str, 
                         status: str, 
                         details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send job status notification to N8N
        
        Args:
            job_id: ID of the job
            status: Status of the job
            details: Job details
            
        Returns:
            Dict: Response from N8N
        """
        try:
            # Create payload
            payload = {
                "event_type": "job_status",
                "job_id": job_id,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "details": details
            }
            
            # Trigger notification workflow
            return self.trigger_workflow(
                "job_status_notification",  # Standard workflow name
                payload
            )
        
        except Exception as e:
            logger.error(f"Error sending job status notification: {e}")
            return {"success": False, "error": str(e)}
    
    def notify_media_ready(self, 
                          job_id: str, 
                          media_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send media ready notification to N8N
        
        Args:
            job_id: ID of the job
            media_info: Information about the ready media
            
        Returns:
            Dict: Response from N8N
        """
        try:
            # Create payload
            payload = {
                "event_type": "media_ready",
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "media_info": media_info
            }
            
            # Trigger notification workflow
            return self.trigger_workflow(
                "media_ready_notification",  # Standard workflow name
                payload
            )
        
        except Exception as e:
            logger.error(f"Error sending media ready notification: {e}")
            return {"success": False, "error": str(e)}
    
    def notify_error(self, 
                    job_id: Optional[str], 
                    error_msg: str,
                    error_type: str,
                    details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send error notification to N8N
        
        Args:
            job_id: Optional ID of the job
            error_msg: Error message
            error_type: Type of error
            details: Optional details about the error
            
        Returns:
            Dict: Response from N8N
        """
        try:
            # Create payload
            payload = {
                "event_type": "error",
                "error_type": error_type,
                "error_message": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add job ID if available
            if job_id:
                payload["job_id"] = job_id
            
            # Add details if available
            if details:
                payload["details"] = details
            
            # Trigger notification workflow
            return self.trigger_workflow(
                "error_notification",  # Standard workflow name
                payload
            )
        
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return {"success": False, "error": str(e)}
    
    def fetch_workflow_templates(self) -> Dict[str, Any]:
        """
        Fetch available workflow templates from N8N
        
        Returns:
            Dict: Available templates
        """
        try:
            # Construct API URL
            api_url = f"{self.n8n_url}/api/v1/workflows/templates"
            
            # Create request
            headers = {}
            if self.api_key:
                headers["X-N8N-API-KEY"] = self.api_key
            
            # Send request
            req = urllib.request.Request(
                api_url,
                headers=headers,
                method="GET"
            )
            
            # Execute request
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        
        except Exception as e:
            logger.error(f"Error fetching workflow templates: {e}")
            return {"success": False, "error": str(e)}
    
    def create_media_detection_workflow(self, name: str) -> Dict[str, Any]:
        """
        Create a new media detection workflow in N8N
        
        Args:
            name: Name for the workflow
            
        Returns:
            Dict: Created workflow information
        """
        try:
            # Add timestamp to ensure unique name
            timestamp = datetime.now().strftime("%Y%m%d%H%M")
            workflow_name = f"{name}_{timestamp}"
            
            # Create workflow definition
            # This is a simplified template - in a real app, you'd have
            # complete workflow definitions stored as templates
            workflow_def = {
                "name": workflow_name,
                "active": False,
                "nodes": [
                    {
                        "name": "Start",
                        "type": "n8n-nodes-base.webhook",
                        "position": [250, 300],
                        "parameters": {
                            "path": workflow_name.lower().replace(" ", "_"),
                            "options": {
                                "responseMode": "lastNode"
                            }
                        }
                    },
                    {
                        "name": "Media Detection Function",
                        "type": "n8n-nodes-base.function",
                        "position": [490, 300],
                        "parameters": {
                            "functionCode": "// Media detection logic\n// In a real workflow, this would contain\n// actual detection code or API calls\nreturn {\n  json: {\n    detected: true,\n    media_type: 'movie',\n    confidence: 0.95,\n    metadata: {\n      title: 'Example Movie',\n      year: 2023\n    }\n  }\n};"
                        }
                    },
                    {
                        "name": "Response",
                        "type": "n8n-nodes-base.respondToWebhook",
                        "position": [730, 300],
                        "parameters": {}
                    }
                ],
                "connections": {
                    "Start": {
                        "main": [
                            [
                                {
                                    "node": "Media Detection Function",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    },
                    "Media Detection Function": {
                        "main": [
                            [
                                {
                                    "node": "Response",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
                }
            }
            
            # Construct API URL
            api_url = f"{self.n8n_url}/api/v1/workflows"
            
            # Create request
            headers = {
                "Content-Type": "application/json"
            }
            if self.api_key:
                headers["X-N8N-API-KEY"] = self.api_key
            
            # Convert workflow definition to JSON
            data = json.dumps(workflow_def).encode('utf-8')
            
            # Send request
            req = urllib.request.Request(
                api_url,
                data=data,
                headers=headers,
                method="POST"
            )
            
            # Execute request
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            return {"success": False, "error": str(e)}
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of N8N
        
        Returns:
            Dict: Health status
        """
        try:
            # Construct API URL - using public endpoint that doesn't require auth
            api_url = f"{self.n8n_url}/healthz"
            
            # Create request
            req = urllib.request.Request(
                api_url,
                method="GET"
            )
            
            # Execute request
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.getcode() == 200:
                    return {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "code": response.getcode(),
                        "timestamp": datetime.now().isoformat()
                    }
        
        except Exception as e:
            logger.error(f"Error checking N8N health: {e}")
            return {
                "status": "unreachable",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def rotate_api_key(self) -> Dict[str, Any]:
        """
        Generate a new API key and invalidate the old one
        
        Returns:
            Dict: New API key information
        """
        try:
            # Generate new secure key
            new_key = SecurityValidator.secure_random_string(32)
            
            # Get salt
            salt = os.environ.get('N8N_SALT', None)
            
            # Encrypt and store
            ENCRYPTED_API_KEYS['n8n_api_key'] = SecurityValidator.encrypt_api_key(new_key, salt)
            
            # In a production environment, you would also update the N8N server's API key
            # This is a simplified implementation
            
            return {
                "success": True,
                "api_key": new_key,
                "expires": None,  # No expiration in this implementation
                "generated": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error rotating API key: {e}")
            return {"success": False, "error": str(e)}


# Helper functions for common operations
def create_n8n_integration() -> MediaN8nIntegration:
    """Create a new N8N integration instance with default settings"""
    return MediaN8nIntegration(
        n8n_url=config.n8n.url if hasattr(config, 'n8n') and hasattr(config.n8n, 'url') else None,
        api_key=config.n8n.api_key if hasattr(config, 'n8n') and hasattr(config.n8n, 'api_key') else None,
        webhook_secret=config.n8n.webhook_secret if hasattr(config, 'n8n') and hasattr(config.n8n, 'webhook_secret') else None
    ) 