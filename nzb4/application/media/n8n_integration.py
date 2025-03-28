#!/usr/bin/env python3
"""
N8N integration for media service.
This module provides integration between the media service and N8N workflows.
"""

import os
import logging
import json
import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import time

from nzb4.domain.media.entities import Media, ConversionJob, ConversionStatus
from nzb4.domain.media.repositories import MediaRepository, ConversionJobRepository
from nzb4.domain.media.services import MediaService
from nzb4.infrastructure.n8n.n8n_manager import N8nManager
from nzb4.config.settings import config

# Set up logging
logger = logging.getLogger(__name__)


class MediaN8nIntegration:
    """
    Integration between media service and N8N automation platform.
    Provides webhooks and callbacks for workflow automation.
    """
    
    def __init__(
        self,
        media_service: MediaService,
        media_repo: MediaRepository,
        job_repo: ConversionJobRepository,
        n8n_manager: N8nManager
    ):
        self.media_service = media_service
        self.media_repo = media_repo
        self.job_repo = job_repo
        self.n8n_manager = n8n_manager
        
        # Ensure N8N is running if enabled
        if config.n8n.enabled:
            self._ensure_n8n_running()
    
    def _ensure_n8n_running(self) -> bool:
        """
        Ensure N8N is running and available
        
        Returns:
            bool: True if running, False otherwise
        """
        try:
            if not self.n8n_manager.is_running():
                logger.info("Starting N8N service...")
                return self.n8n_manager.start()
            return True
        except Exception as e:
            logger.error(f"Error ensuring N8N is running: {e}")
            return False
    
    def register_webhook_workflows(self) -> Dict[str, Any]:
        """
        Register default webhook workflows in N8N
        
        Returns:
            Dict: Result information
        """
        try:
            if not self._ensure_n8n_running():
                return {"error": "N8N service is not running"}
            
            results = {
                "created": [],
                "errors": []
            }
            
            # Create job status webhook workflow
            job_status_workflow = self._create_job_status_workflow()
            if "error" not in job_status_workflow:
                results["created"].append({
                    "name": "Media Job Status Notification",
                    "id": job_status_workflow.get("id"),
                    "webhook_url": job_status_workflow.get("webhook_url")
                })
            else:
                results["errors"].append({
                    "workflow": "Media Job Status Notification",
                    "error": job_status_workflow.get("error")
                })
            
            # Create media detection workflow
            media_detection_workflow = self._create_media_detection_workflow()
            if "error" not in media_detection_workflow:
                results["created"].append({
                    "name": "Media Content Detection",
                    "id": media_detection_workflow.get("id"),
                    "webhook_url": media_detection_workflow.get("webhook_url")
                })
            else:
                results["errors"].append({
                    "workflow": "Media Content Detection",
                    "error": media_detection_workflow.get("error")
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error registering webhook workflows: {e}")
            return {"error": str(e)}
    
    def _create_job_status_workflow(self) -> Dict[str, Any]:
        """
        Create a job status notification workflow in N8N
        
        Returns:
            Dict: Workflow information
        """
        try:
            # Define the workflow structure for job status notifications
            workflow_data = {
                "name": "Media Job Status Notification",
                "active": True,
                "nodes": [
                    {
                        "parameters": {
                            "httpMethod": "POST",
                            "path": "job-status",
                            "options": {}
                        },
                        "name": "Webhook",
                        "type": "n8n-nodes-base.webhook",
                        "position": [100, 300]
                    },
                    {
                        "parameters": {
                            "conditions": {
                                "string": [
                                    {
                                        "value1": "={{ $json.status }}",
                                        "operation": "equal",
                                        "value2": "COMPLETED"
                                    }
                                ]
                            }
                        },
                        "name": "IF",
                        "type": "n8n-nodes-base.if",
                        "position": [340, 300]
                    },
                    {
                        "parameters": {
                            "toEmail": "={{ $json.notification_email }}",
                            "subject": "Media Job Completed",
                            "text": "=Your media conversion job has completed successfully.\n\nJob ID: {{ $json.job_id }}\nStatus: {{ $json.status }}\nMedia: {{ $json.media.title || $json.media.source }}\nOutput Path: {{ $json.media.output_path }}"
                        },
                        "name": "Send Email",
                        "type": "n8n-nodes-base.emailSend",
                        "position": [540, 240]
                    },
                    {
                        "parameters": {
                            "url": "={{ $json.webhook_url }}",
                            "options": {},
                            "method": "POST",
                            "bodyParametersUi": {
                                "parameter": [
                                    {
                                        "name": "job_id",
                                        "value": "={{ $json.job_id }}"
                                    },
                                    {
                                        "name": "status",
                                        "value": "={{ $json.status }}"
                                    },
                                    {
                                        "name": "completed_at",
                                        "value": "={{ $json.completed_at }}"
                                    }
                                ]
                            }
                        },
                        "name": "HTTP Request",
                        "type": "n8n-nodes-base.httpRequest",
                        "position": [540, 400]
                    }
                ],
                "connections": {
                    "Webhook": {
                        "main": [
                            [
                                {
                                    "node": "IF",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    },
                    "IF": {
                        "main": [
                            [
                                {
                                    "node": "Send Email",
                                    "type": "main",
                                    "index": 0
                                }
                            ],
                            [
                                {
                                    "node": "HTTP Request",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
                }
            }
            
            # Create the workflow in N8N
            result = self.n8n_manager.create_workflow(workflow_data)
            
            # Get the webhook URL for this workflow
            if "id" in result:
                webhook_url = self.n8n_manager.check_webhook_url(result["id"])
                if webhook_url:
                    result["webhook_url"] = webhook_url
            
            return result
        
        except Exception as e:
            logger.error(f"Error creating job status workflow: {e}")
            return {"error": str(e)}
    
    def _create_media_detection_workflow(self) -> Dict[str, Any]:
        """
        Create a media content detection workflow in N8N
        
        Returns:
            Dict: Workflow information
        """
        try:
            # Define the workflow structure for media detection
            workflow_data = {
                "name": "Media Content Detection",
                "active": True,
                "nodes": [
                    {
                        "parameters": {
                            "httpMethod": "POST",
                            "path": "detect-media",
                            "options": {}
                        },
                        "name": "Webhook",
                        "type": "n8n-nodes-base.webhook",
                        "position": [100, 300]
                    },
                    {
                        "parameters": {
                            "url": "https://www.omdbapi.com",
                            "options": {},
                            "queryParametersUi": {
                                "parameter": [
                                    {
                                        "name": "apikey",
                                        "value": "={{ $env.OMDB_API_KEY }}"
                                    },
                                    {
                                        "name": "t",
                                        "value": "={{ $json.title }}"
                                    },
                                    {
                                        "name": "y",
                                        "value": "={{ $json.year }}"
                                    }
                                ]
                            }
                        },
                        "name": "Lookup Media",
                        "type": "n8n-nodes-base.httpRequest",
                        "position": [340, 300]
                    },
                    {
                        "parameters": {
                            "conditions": {
                                "string": [
                                    {
                                        "value1": "={{ $json.Response }}",
                                        "operation": "equal",
                                        "value2": "True"
                                    }
                                ]
                            }
                        },
                        "name": "IF",
                        "type": "n8n-nodes-base.if",
                        "position": [540, 300]
                    },
                    {
                        "parameters": {
                            "url": "={{ $json.callback_url }}",
                            "options": {},
                            "method": "POST",
                            "bodyParametersUi": {
                                "parameter": [
                                    {
                                        "name": "media_id",
                                        "value": "={{ $node.Webhook.json.media_id }}"
                                    },
                                    {
                                        "name": "metadata",
                                        "value": "={{ $json }}"
                                    },
                                    {
                                        "name": "success",
                                        "value": "true"
                                    }
                                ]
                            }
                        },
                        "name": "Success Callback",
                        "type": "n8n-nodes-base.httpRequest",
                        "position": [740, 240]
                    },
                    {
                        "parameters": {
                            "url": "={{ $node.Webhook.json.callback_url }}",
                            "options": {},
                            "method": "POST",
                            "bodyParametersUi": {
                                "parameter": [
                                    {
                                        "name": "media_id",
                                        "value": "={{ $node.Webhook.json.media_id }}"
                                    },
                                    {
                                        "name": "error",
                                        "value": "Media not found"
                                    },
                                    {
                                        "name": "success",
                                        "value": "false"
                                    }
                                ]
                            }
                        },
                        "name": "Error Callback",
                        "type": "n8n-nodes-base.httpRequest",
                        "position": [740, 400]
                    }
                ],
                "connections": {
                    "Webhook": {
                        "main": [
                            [
                                {
                                    "node": "Lookup Media",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    },
                    "Lookup Media": {
                        "main": [
                            [
                                {
                                    "node": "IF",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    },
                    "IF": {
                        "main": [
                            [
                                {
                                    "node": "Success Callback",
                                    "type": "main",
                                    "index": 0
                                }
                            ],
                            [
                                {
                                    "node": "Error Callback",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
                }
            }
            
            # Create the workflow in N8N
            result = self.n8n_manager.create_workflow(workflow_data)
            
            # Get the webhook URL for this workflow
            if "id" in result:
                webhook_url = self.n8n_manager.check_webhook_url(result["id"])
                if webhook_url:
                    result["webhook_url"] = webhook_url
            
            return result
        
        except Exception as e:
            logger.error(f"Error creating media detection workflow: {e}")
            return {"error": str(e)}
    
    def notify_job_status_change(self, job_id: str) -> bool:
        """
        Notify N8N workflow of job status change
        
        Args:
            job_id: ID of the job
            
        Returns:
            bool: True if notification sent, False otherwise
        """
        try:
            # Get job data
            job = self.job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"Job not found: {job_id}")
                return False
            
            # Get media data
            media = self.media_repo.get_by_id(job.media_id)
            if not media:
                logger.error(f"Media not found for job: {job_id}")
                return False
            
            # Check if N8N is running
            if not self._ensure_n8n_running():
                logger.error("N8N service is not running")
                return False
            
            # Get workflows
            workflows = self.n8n_manager.get_workflows()
            
            # Find job status workflow
            job_status_workflow = None
            for workflow in workflows:
                if workflow.get("name") == "Media Job Status Notification":
                    job_status_workflow = workflow
                    break
            
            if not job_status_workflow:
                logger.warning("Job status workflow not found in N8N")
                return False
            
            # Get webhook URL
            webhook_url = self.n8n_manager.check_webhook_url(job_status_workflow["id"])
            if not webhook_url:
                logger.error("Could not get webhook URL for job status workflow")
                return False
            
            # Prepare notification data
            notification_data = {
                "job_id": job.id,
                "media_id": media.id,
                "status": job.status.name,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message,
                "media": {
                    "source": media.source,
                    "type": media.media_type.name,
                    "title": media.metadata.title if media.metadata and media.metadata.title else None,
                    "output_path": media.output_path
                },
                "webhook_url": None,  # Optional webhook for further notifications
                "notification_email": None  # Optional email for notifications
            }
            
            # Send notification to N8N webhook
            response = requests.post(
                webhook_url,
                json=notification_data,
                timeout=10
            )
            
            if response.status_code < 200 or response.status_code >= 300:
                logger.error(f"Error notifying job status: HTTP {response.status_code}")
                return False
            
            logger.info(f"Job status notification sent for job {job_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error notifying job status change: {e}")
            return False
    
    def request_media_detection(self, media_id: str, title: str, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Request media detection from N8N workflow
        
        Args:
            media_id: ID of the media
            title: Media title
            year: Media year
            
        Returns:
            Dict: Result information
        """
        try:
            # Get media data
            media = self.media_repo.get_by_id(media_id)
            if not media:
                logger.error(f"Media not found: {media_id}")
                return {"error": "Media not found"}
            
            # Check if N8N is running
            if not self._ensure_n8n_running():
                logger.error("N8N service is not running")
                return {"error": "N8N service is not running"}
            
            # Get workflows
            workflows = self.n8n_manager.get_workflows()
            
            # Find media detection workflow
            detection_workflow = None
            for workflow in workflows:
                if workflow.get("name") == "Media Content Detection":
                    detection_workflow = workflow
                    break
            
            if not detection_workflow:
                logger.warning("Media detection workflow not found in N8N")
                return {"error": "Media detection workflow not found"}
            
            # Get webhook URL
            webhook_url = self.n8n_manager.check_webhook_url(detection_workflow["id"])
            if not webhook_url:
                logger.error("Could not get webhook URL for media detection workflow")
                return {"error": "Could not get webhook URL"}
            
            # Create a callback URL (would be implemented in a real app)
            callback_url = f"http://{config.network.host}:{config.network.port}/api/media/{media_id}/detection-callback"
            
            # Prepare detection request data
            request_data = {
                "media_id": media.id,
                "title": title,
                "year": year,
                "callback_url": callback_url
            }
            
            # Send request to N8N webhook
            response = requests.post(
                webhook_url,
                json=request_data,
                timeout=10
            )
            
            if response.status_code < 200 or response.status_code >= 300:
                logger.error(f"Error requesting media detection: HTTP {response.status_code}")
                return {"error": f"HTTP error: {response.status_code}"}
            
            logger.info(f"Media detection requested for media {media_id}")
            return {
                "success": True,
                "message": "Media detection requested",
                "media_id": media_id
            }
        
        except Exception as e:
            logger.error(f"Error requesting media detection: {e}")
            return {"error": str(e)}
    
    def process_detection_callback(self, media_id: str, data: Dict[str, Any]) -> bool:
        """
        Process media detection callback from N8N
        
        Args:
            media_id: ID of the media
            data: Callback data
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            # Get media data
            media = self.media_repo.get_by_id(media_id)
            if not media:
                logger.error(f"Media not found: {media_id}")
                return False
            
            # Check if detection was successful
            if not data.get("success", False):
                logger.warning(f"Media detection failed for {media_id}: {data.get('error', 'Unknown error')}")
                return False
            
            # Extract metadata
            metadata = data.get("metadata", {})
            if not metadata:
                logger.warning(f"No metadata received for media {media_id}")
                return False
            
            # Update media metadata
            media.metadata.title = metadata.get("Title")
            media.metadata.description = metadata.get("Plot")
            media.metadata.year = int(metadata.get("Year", 0)) if metadata.get("Year", "").isdigit() else None
            media.metadata.genre = metadata.get("Genre")
            
            # Handle specific media types
            if "Type" in metadata:
                if metadata["Type"].lower() == "movie":
                    media.media_type = MediaType.MOVIE
                elif metadata["Type"].lower() in ("series", "episode"):
                    media.media_type = MediaType.TV_SHOW
                    # Extract season and episode if possible
                    if "Season" in metadata and metadata["Season"].isdigit():
                        media.metadata.season = int(metadata["Season"])
                    if "Episode" in metadata and metadata["Episode"].isdigit():
                        media.metadata.episode = int(metadata["Episode"])
            
            # Save updated media
            self.media_repo.save(media)
            
            logger.info(f"Updated metadata for media {media_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing detection callback: {e}")
            return False 