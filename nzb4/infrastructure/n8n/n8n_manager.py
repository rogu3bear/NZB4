#!/usr/bin/env python3
"""
N8n Manager - Handles installation, startup, and integration with n8n
"""

import os
import time
import json
import logging
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime

from nzb4.config.settings import config

logger = logging.getLogger(__name__)


class N8nManagerError(Exception):
    """Base exception for N8n Manager errors"""
    pass


class N8nConnectionError(N8nManagerError):
    """Error connecting to n8n instance"""
    pass


class N8nInstallationError(N8nManagerError):
    """Error during n8n installation"""
    pass


class N8nManager:
    """
    Manages n8n installation, startup, and integration
    """
    
    def __init__(self):
        """Initialize the n8n manager"""
        self.n8n_config = config.n8n
        self._container_name = "nzb4-n8n"
        self._n8n_api_url = f"http://localhost:{self.n8n_config.port}/api/v1"
        self._n8n_process = None
        self._is_running = False
    
    def is_installed(self) -> bool:
        """Check if n8n is installed"""
        if self.n8n_config.install_type == "docker":
            try:
                # Check if Docker image exists
                result = subprocess.run(
                    ["docker", "image", "ls", "n8nio/n8n", "--format", "{{.Repository}}"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return "n8nio/n8n" in result.stdout
            except Exception as e:
                logger.error(f"Error checking n8n Docker installation: {e}")
                return False
        elif self.n8n_config.install_type == "npm":
            try:
                # Check if n8n is installed via npm
                result = subprocess.run(
                    ["which", "n8n"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return bool(result.stdout.strip())
            except Exception as e:
                logger.error(f"Error checking n8n npm installation: {e}")
                return False
        else:
            logger.error(f"Unsupported installation type: {self.n8n_config.install_type}")
            return False
    
    def install(self) -> bool:
        """Install n8n"""
        if self.is_installed():
            logger.info("n8n is already installed")
            return True
        
        logger.info(f"Installing n8n using {self.n8n_config.install_type}...")
        
        try:
            if self.n8n_config.install_type == "docker":
                # Pull the n8n Docker image
                subprocess.run(
                    ["docker", "pull", "n8nio/n8n"],
                    check=True,
                    capture_output=True
                )
                logger.info("n8n Docker image pulled successfully")
                return True
            
            elif self.n8n_config.install_type == "npm":
                # Install n8n globally using npm
                subprocess.run(
                    ["npm", "install", "n8n", "-g"],
                    check=True,
                    capture_output=True
                )
                logger.info("n8n installed successfully using npm")
                return True
            
            else:
                raise N8nInstallationError(f"Unsupported installation type: {self.n8n_config.install_type}")
        
        except subprocess.CalledProcessError as e:
            error_message = f"Error installing n8n: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(error_message)
            raise N8nInstallationError(error_message) from e
        except Exception as e:
            error_message = f"Unexpected error installing n8n: {str(e)}"
            logger.error(error_message)
            raise N8nInstallationError(error_message) from e
    
    def is_running(self) -> bool:
        """Check if n8n is running"""
        if self.n8n_config.install_type == "docker":
            try:
                # Check if the container is running
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={self._container_name}", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return self._container_name in result.stdout
            except Exception as e:
                logger.error(f"Error checking if n8n Docker container is running: {e}")
                return False
        
        elif self.n8n_config.install_type == "npm":
            # Check if the process is running
            if self._n8n_process:
                return self._n8n_process.poll() is None
            
            # Check if there's an n8n process running
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "n8n start"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return bool(result.stdout.strip())
            except Exception as e:
                logger.error(f"Error checking if n8n process is running: {e}")
                return False
        
        else:
            logger.error(f"Unsupported installation type: {self.n8n_config.install_type}")
            return False
    
    def start(self) -> bool:
        """Start n8n"""
        if self.is_running():
            logger.info("n8n is already running")
            return True
        
        logger.info(f"Starting n8n using {self.n8n_config.install_type}...")
        
        try:
            if self.n8n_config.install_type == "docker":
                # Ensure data directory exists
                os.makedirs(self.n8n_config.data_dir, exist_ok=True)
                
                # Start the n8n Docker container
                subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", self._container_name,
                        "-p", f"{self.n8n_config.port}:{self.n8n_config.port}",
                        "-v", f"{self.n8n_config.data_dir}:/home/node/.n8n",
                        "--restart", "unless-stopped",
                        "n8nio/n8n"
                    ],
                    check=True,
                    capture_output=True
                )
                
                # Wait for n8n to start up
                self._wait_for_startup()
                logger.info("n8n Docker container started successfully")
                return True
            
            elif self.n8n_config.install_type == "npm":
                # Ensure data directory exists
                os.makedirs(self.n8n_config.data_dir, exist_ok=True)
                
                # Start n8n as a background process
                env = os.environ.copy()
                env["N8N_USER_FOLDER"] = self.n8n_config.data_dir
                
                self._n8n_process = subprocess.Popen(
                    ["n8n", "start"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for n8n to start up
                self._wait_for_startup()
                logger.info("n8n process started successfully")
                return True
            
            else:
                raise N8nManagerError(f"Unsupported installation type: {self.n8n_config.install_type}")
        
        except subprocess.CalledProcessError as e:
            error_message = f"Error starting n8n: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(error_message)
            return False
        except Exception as e:
            error_message = f"Unexpected error starting n8n: {str(e)}"
            logger.error(error_message)
            return False
    
    def stop(self) -> bool:
        """Stop n8n"""
        if not self.is_running():
            logger.info("n8n is not running")
            return True
        
        logger.info(f"Stopping n8n ({self.n8n_config.install_type})...")
        
        try:
            if self.n8n_config.install_type == "docker":
                # Stop and remove the n8n Docker container
                subprocess.run(
                    ["docker", "stop", self._container_name],
                    check=True,
                    capture_output=True
                )
                subprocess.run(
                    ["docker", "rm", self._container_name],
                    check=True,
                    capture_output=True
                )
                logger.info("n8n Docker container stopped successfully")
                return True
            
            elif self.n8n_config.install_type == "npm":
                # Stop the n8n process
                if self._n8n_process:
                    self._n8n_process.terminate()
                    try:
                        self._n8n_process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self._n8n_process.kill()
                    self._n8n_process = None
                else:
                    # Try to find and kill the process
                    subprocess.run(
                        ["pkill", "-f", "n8n start"],
                        check=False,
                        capture_output=True
                    )
                
                logger.info("n8n process stopped successfully")
                return True
            
            else:
                raise N8nManagerError(f"Unsupported installation type: {self.n8n_config.install_type}")
        
        except subprocess.CalledProcessError as e:
            error_message = f"Error stopping n8n: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(error_message)
            return False
        except Exception as e:
            error_message = f"Unexpected error stopping n8n: {str(e)}"
            logger.error(error_message)
            return False
    
    def restart(self) -> bool:
        """Restart n8n"""
        logger.info("Restarting n8n...")
        if self.is_running():
            if not self.stop():
                return False
        
        # Wait a bit before starting again
        time.sleep(2)
        return self.start()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status information about n8n"""
        status = {
            "installed": self.is_installed(),
            "running": self.is_running(),
            "config": {
                "port": self.n8n_config.port,
                "data_dir": self.n8n_config.data_dir,
                "install_type": self.n8n_config.install_type
            },
            "health": {
                "status": "unknown",
                "last_check": None,
                "error": None
            }
        }
        
        # Check health if running
        if status["running"]:
            health = self._check_health()
            status["health"] = health
        
        return status
    
    def get_workflows(self) -> List[Dict[str, Any]]:
        """Get all workflows from n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to get workflows: {response.status_code}")
            
            return response.json()
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get a specific workflow from n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows/{workflow_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to get workflow: {response.status_code}")
            
            return response.json()
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow in n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows"
            response = requests.post(url, json=workflow_data, timeout=10)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to create workflow: {response.status_code}")
            
            return response.json()
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing workflow in n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows/{workflow_id}"
            response = requests.put(url, json=workflow_data, timeout=10)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to update workflow: {response.status_code}")
            
            return response.json()
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows/{workflow_id}"
            response = requests.delete(url, timeout=10)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to delete workflow: {response.status_code}")
            
            return True
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def execute_workflow(self, workflow_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a workflow in n8n"""
        if not self.is_running():
            raise N8nConnectionError("n8n is not running")
        
        try:
            url = f"{self._n8n_api_url}/workflows/{workflow_id}/execute"
            response = requests.post(url, json=data or {}, timeout=30)
            
            if response.status_code != 200:
                raise N8nConnectionError(f"Failed to execute workflow: {response.status_code}")
            
            return response.json()
        except requests.RequestException as e:
            raise N8nConnectionError(f"Connection error: {str(e)}") from e
    
    def create_webhook_workflow(self, name: str, description: str) -> Dict[str, Any]:
        """
        Create a basic webhook workflow in n8n
        
        This creates a simple workflow with a webhook trigger node
        that can be used as a starting point.
        """
        workflow_data = {
            "name": name,
            "active": False,
            "nodes": [
                {
                    "parameters": {
                        "path": f"/webhook/{name.lower().replace(' ', '_')}",
                        "options": {}
                    },
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "position": [250, 300]
                }
            ],
            "connections": {},
            "tags": ["nzb4", "webhook"],
            "settings": {
                "saveManualExecutions": True,
                "callerPolicy": "workflowsFromSameOwner"
            }
        }
        
        if description:
            workflow_data["description"] = description
        
        return self.create_workflow(workflow_data)
    
    def check_webhook_url(self, workflow_id: str) -> Optional[str]:
        """Get the webhook URL for a workflow"""
        try:
            workflow = self.get_workflow(workflow_id)
            
            # Find the webhook node
            for node in workflow.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    path = node.get("parameters", {}).get("path", "")
                    if path:
                        return f"http://localhost:{self.n8n_config.port}{path}"
            
            return None
        except Exception as e:
            logger.error(f"Error getting webhook URL: {e}")
            return None
    
    def _wait_for_startup(self, max_wait_seconds: int = 60) -> None:
        """Wait for n8n to start up and be available"""
        logger.info("Waiting for n8n to start...")
        
        health_endpoint = f"http://localhost:{self.n8n_config.port}/healthz"
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(health_endpoint, timeout=2)
                if response.status_code == 200:
                    logger.info("n8n is now available")
                    return
            except requests.RequestException:
                pass
            
            # Check if process is still running
            if self.n8n_config.install_type == "npm" and self._n8n_process:
                if self._n8n_process.poll() is not None:
                    stdout, stderr = self._n8n_process.communicate()
                    error_message = f"n8n process terminated: {stderr}"
                    logger.error(error_message)
                    raise N8nManagerError(error_message)
            
            # Wait a bit before trying again
            time.sleep(2)
        
        raise N8nManagerError(f"n8n did not start within {max_wait_seconds} seconds")
    
    def _check_health(self) -> Dict[str, Any]:
        """Check the health of the n8n instance"""
        health = {
            "status": "unhealthy",
            "last_check": datetime.now().isoformat(),
            "error": None
        }
        
        try:
            health_endpoint = f"http://localhost:{self.n8n_config.port}/healthz"
            response = requests.get(health_endpoint, timeout=5)
            
            if response.status_code == 200:
                health["status"] = "healthy"
            else:
                health["status"] = "unhealthy"
                health["error"] = f"Health check returned status code {response.status_code}"
        except requests.RequestException as e:
            health["error"] = f"Connection error: {str(e)}"
        
        return health


# Global n8n manager instance
n8n_manager = N8nManager() 