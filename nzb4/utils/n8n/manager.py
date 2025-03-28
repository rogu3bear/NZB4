#!/usr/bin/env python3
"""
n8n manager module to handle installation, configuration, and monitoring
"""

import os
import sys
import json
import logging
import subprocess
import time
import shutil
import platform
import requests
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from ..database import get_setting, update_setting, log_event
from ..docker_manager import is_docker_installed, is_docker_running, ensure_docker_running

# Setup logging
logger = logging.getLogger(__name__)

# Constants
N8N_PORT = 5678
N8N_DOCKER_IMAGE = "n8nio/n8n:latest"
DEFAULT_N8N_DATA_DIR = os.path.expanduser("~/n8n-data")
N8N_CONTAINER_NAME = "nzb4-n8n"

class N8nManager:
    """
    Manages n8n workflow automation tool installation and configuration
    """
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize n8n manager
        
        Args:
            data_dir: Directory to store n8n data. Default is ~/n8n-data
        """
        self.data_dir = data_dir or get_setting("n8n_data_dir", DEFAULT_N8N_DATA_DIR)
        self.port = int(get_setting("n8n_port", str(N8N_PORT)))
        self.container_name = N8N_CONTAINER_NAME
        self.health_check_thread = None
        self.is_running_check = False
    
    def is_installed(self) -> bool:
        """Check if n8n is installed"""
        if self._is_docker_install():
            # Check if the Docker image exists
            try:
                result = subprocess.run(
                    ["docker", "images", "-q", N8N_DOCKER_IMAGE],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                return bool(result.stdout.strip())
            except Exception as e:
                logger.error(f"Error checking n8n Docker image: {e}")
                return False
        else:
            # Check for npm installation
            try:
                result = subprocess.run(
                    ["n8n", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                return False
    
    def is_running(self) -> bool:
        """Check if n8n is running"""
        if self._is_docker_install():
            # Check if container is running
            try:
                result = subprocess.run(
                    ["docker", "ps", "-q", "-f", f"name={self.container_name}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                return bool(result.stdout.strip())
            except Exception as e:
                logger.error(f"Error checking n8n Docker container: {e}")
                return False
        else:
            # Try to connect to n8n API
            try:
                response = requests.get(f"http://localhost:{self.port}/healthz", timeout=2)
                return response.status_code == 200
            except Exception:
                return False
    
    def _is_docker_install(self) -> bool:
        """Check if this is a Docker-based install"""
        return get_setting("n8n_install_type", "docker").lower() == "docker"
    
    def install(self, use_docker: bool = True) -> bool:
        """
        Install n8n
        
        Args:
            use_docker: Whether to use Docker for installation
            
        Returns:
            bool: Whether installation was successful
        """
        if self.is_installed():
            logger.info("n8n is already installed")
            return True
        
        # Update install type setting
        update_setting("n8n_install_type", "docker" if use_docker else "npm")
        
        if use_docker:
            return self._install_docker()
        else:
            return self._install_npm()
    
    def _install_docker(self) -> bool:
        """Install n8n using Docker"""
        # Ensure Docker is running
        if not ensure_docker_running():
            logger.error("Docker is not running and could not be started")
            return False
        
        try:
            # Create data directory
            os.makedirs(self.data_dir, exist_ok=True)
            
            # Pull n8n image
            logger.info(f"Pulling n8n Docker image: {N8N_DOCKER_IMAGE}")
            subprocess.run(
                ["docker", "pull", N8N_DOCKER_IMAGE],
                check=True
            )
            
            # Create n8n startup script
            self._create_docker_startup_script()
            
            logger.info("n8n installed successfully via Docker")
            return True
        except Exception as e:
            logger.error(f"Error installing n8n with Docker: {e}")
            return False
    
    def _install_npm(self) -> bool:
        """Install n8n using npm"""
        try:
            # Check if npm is installed
            npm_result = subprocess.run(
                ["npm", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            
            if npm_result.returncode != 0:
                logger.error("npm is not installed. Please install Node.js and npm first.")
                return False
            
            # Install n8n globally
            logger.info("Installing n8n via npm...")
            subprocess.run(
                ["npm", "install", "n8n", "-g"],
                check=True
            )
            
            # Create data directory
            os.makedirs(self.data_dir, exist_ok=True)
            
            # Create n8n startup script for npm
            self._create_npm_startup_script()
            
            logger.info("n8n installed successfully via npm")
            return True
        except Exception as e:
            logger.error(f"Error installing n8n with npm: {e}")
            return False
    
    def _create_docker_startup_script(self) -> None:
        """Create a shell script to start n8n with Docker"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "start_n8n_docker.sh")
        
        script_content = f"""#!/bin/bash
# Start n8n in Docker container without username/password auth
docker run -d \\
  --name {self.container_name} \\
  --restart unless-stopped \\
  -p {self.port}:{self.port} \\
  -v {self.data_dir}:/home/node/.n8n \\
  -e N8N_ENCRYPTION_KEY=$(openssl rand -hex 24) \\
  -e N8N_BASIC_AUTH_ACTIVE=false \\
  -e NODE_ENV=production \\
  {N8N_DOCKER_IMAGE}

# Print status message
echo "n8n started at http://localhost:{self.port}"
"""
        
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
    
    def _create_npm_startup_script(self) -> None:
        """Create a shell script to start n8n with npm"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "start_n8n_npm.sh")
        
        script_content = f"""#!/bin/bash
# Start n8n without username/password auth
export N8N_ENCRYPTION_KEY=$(openssl rand -hex 24)
export N8N_BASIC_AUTH_ACTIVE=false
export N8N_USER_FOLDER="{self.data_dir}"
export N8N_PORT={self.port}

# Start n8n
n8n start &

# Print status message
echo "n8n started at http://localhost:{self.port}"
"""
        
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
    
    def start(self) -> bool:
        """Start n8n"""
        if self.is_running():
            logger.info("n8n is already running")
            return True
        
        try:
            if self._is_docker_install():
                # Check if container exists but is stopped
                result = subprocess.run(
                    ["docker", "ps", "-a", "-q", "-f", f"name={self.container_name}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.stdout.strip():
                    # Container exists, start it
                    logger.info(f"Starting existing n8n container: {self.container_name}")
                    subprocess.run(
                        ["docker", "start", self.container_name],
                        check=True
                    )
                else:
                    # Run the start script
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    script_path = os.path.join(script_dir, "start_n8n_docker.sh")
                    
                    if not os.path.exists(script_path):
                        self._create_docker_startup_script()
                    
                    logger.info("Starting n8n with Docker")
                    subprocess.run(script_path, shell=True, check=True)
            else:
                # Run the start script for npm
                script_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(script_dir, "start_n8n_npm.sh")
                
                if not os.path.exists(script_path):
                    self._create_npm_startup_script()
                
                logger.info("Starting n8n with npm")
                subprocess.run(script_path, shell=True, check=True)
            
            # Wait for n8n to start
            for _ in range(10):
                time.sleep(2)
                if self.is_running():
                    logger.info(f"n8n started successfully at http://localhost:{self.port}")
                    return True
            
            logger.warning("n8n did not start within the timeout period")
            return False
        except Exception as e:
            logger.error(f"Error starting n8n: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop n8n"""
        if not self.is_running():
            logger.info("n8n is not running")
            return True
        
        try:
            if self._is_docker_install():
                # Stop Docker container
                logger.info(f"Stopping n8n Docker container: {self.container_name}")
                subprocess.run(
                    ["docker", "stop", self.container_name],
                    check=True
                )
            else:
                # Find and kill n8n process
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "n8n.exe"],
                        check=False
                    )
                else:
                    subprocess.run(
                        ["pkill", "-f", "n8n"],
                        check=False
                    )
            
            # Check if it stopped
            for _ in range(5):
                time.sleep(1)
                if not self.is_running():
                    logger.info("n8n stopped successfully")
                    return True
            
            logger.warning("n8n did not stop within the timeout period")
            return False
        except Exception as e:
            logger.error(f"Error stopping n8n: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get n8n status information"""
        status = {
            "installed": self.is_installed(),
            "running": False,
            "version": None,
            "install_type": "docker" if self._is_docker_install() else "npm",
            "data_dir": self.data_dir,
            "port": self.port,
            "url": f"http://localhost:{self.port}",
            "container_name": self.container_name if self._is_docker_install() else None
        }
        
        # Check if running and get additional info
        if self.is_installed():
            status["running"] = self.is_running()
            
            # Try to get version
            try:
                if self._is_docker_install():
                    result = subprocess.run(
                        ["docker", "exec", self.container_name, "n8n", "--version"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        status["version"] = result.stdout.strip()
                else:
                    result = subprocess.run(
                        ["n8n", "--version"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        status["version"] = result.stdout.strip()
            except Exception:
                pass
        
        return status
    
    def uninstall(self) -> bool:
        """Uninstall n8n"""
        try:
            # First stop if running
            if self.is_running():
                self.stop()
            
            if self._is_docker_install():
                # Remove container
                subprocess.run(
                    ["docker", "rm", "-f", self.container_name],
                    check=False
                )
                
                # Remove image
                subprocess.run(
                    ["docker", "rmi", N8N_DOCKER_IMAGE],
                    check=False
                )
            else:
                # Uninstall npm package
                subprocess.run(
                    ["npm", "uninstall", "n8n", "-g"],
                    check=False
                )
            
            # Option to remove data directory
            # We'll leave this commented out as it's dangerous
            # if os.path.exists(self.data_dir):
            #     shutil.rmtree(self.data_dir)
            
            logger.info("n8n uninstalled successfully")
            return True
        except Exception as e:
            logger.error(f"Error uninstalling n8n: {e}")
            return False
    
    def start_health_monitoring(self) -> None:
        """Start background thread to monitor n8n health"""
        if self.health_check_thread and self.health_check_thread.is_alive():
            return
        
        logger.info("Starting n8n health monitoring")
        self.is_running_check = True
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_check_thread.start()
    
    def stop_health_monitoring(self) -> None:
        """Stop health monitoring thread"""
        logger.info("Stopping n8n health monitoring")
        self.is_running_check = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
    
    def _health_check_loop(self) -> None:
        """Background monitoring loop for n8n"""
        check_interval = int(get_setting("n8n_health_check_interval", "300"))  # 5 min default
        
        while self.is_running_check:
            try:
                if self.is_installed() and not self.is_running():
                    logger.warning("n8n is installed but not running, attempting to restart")
                    self.start()
            except Exception as e:
                logger.error(f"Error in n8n health check: {e}")
            
            # Sleep for the check interval
            for _ in range(check_interval):
                if not self.is_running_check:
                    break
                time.sleep(1)

# Convenience functions
def is_n8n_installed() -> bool:
    """Check if n8n is installed"""
    manager = N8nManager()
    return manager.is_installed()

def is_n8n_running() -> bool:
    """Check if n8n is running"""
    manager = N8nManager()
    return manager.is_running()

def setup_n8n(data_dir: Optional[str] = None, port: int = N8N_PORT) -> bool:
    """
    Setup n8n for the first time
    
    Args:
        data_dir: Directory to store n8n data
        port: Port to run n8n on
        
    Returns:
        bool: Whether setup was successful
    """
    data_dir = data_dir or DEFAULT_N8N_DATA_DIR
    
    # Save settings
    update_setting("n8n_data_dir", data_dir)
    update_setting("n8n_port", str(port))
    update_setting("n8n_install_type", "docker")
    
    # Create directories
    os.makedirs(data_dir, exist_ok=True)
    
    # Install and start n8n
    manager = N8nManager(data_dir)
    if manager.install() and manager.start():
        manager.start_health_monitoring()
        logger.info(f"n8n setup completed successfully: http://localhost:{port}")
        return True
    else:
        logger.error("n8n setup failed")
        return False 