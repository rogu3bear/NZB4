#!/usr/bin/env python3
"""
Docker management utilities
Handles checking, starting and installing Docker on macOS
"""

import os
import subprocess
import time
import logging
import platform
import shutil

logger = logging.getLogger(__name__)

def is_macos():
    """Check if running on macOS"""
    return platform.system() == 'Darwin'

def is_docker_installed():
    """Check if Docker is installed"""
    return shutil.which('docker') is not None

def is_docker_running():
    """Check if Docker daemon is running"""
    try:
        result = subprocess.run(['docker', 'info'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               timeout=5)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def start_docker():
    """Attempt to start Docker daemon"""
    if not is_macos():
        logger.warning("start_docker() is only supported on macOS")
        return False
        
    if not is_docker_installed():
        logger.warning("Docker is not installed, cannot start")
        return False
        
    # Check if Docker Desktop is installed
    docker_app_path = '/Applications/Docker.app'
    docker_cli_path = os.path.expanduser('~/.docker/bin/docker')
    
    if os.path.exists(docker_app_path):
        # Start Docker Desktop
        try:
            logger.info("Starting Docker Desktop...")
            subprocess.run(['open', '-a', 'Docker'], check=True)
            
            # Wait for Docker to start (could take some time)
            for _ in range(60):  # Wait up to 60 seconds
                time.sleep(1)
                if is_docker_running():
                    logger.info("Docker Desktop started successfully")
                    return True
            
            logger.error("Docker Desktop didn't start within the timeout period")
            return False
        except subprocess.SubprocessError as e:
            logger.error(f"Error starting Docker Desktop: {e}")
            return False
    elif os.path.exists(docker_cli_path):
        # For Docker CLI installed via Homebrew
        try:
            logger.info("Starting Docker daemon...")
            # The specific command may vary based on how Docker was installed
            subprocess.run(['docker', 'context', 'use', 'default'], check=True)
            
            # Wait for Docker to start
            for _ in range(30):
                time.sleep(1)
                if is_docker_running():
                    logger.info("Docker daemon started successfully")
                    return True
            
            logger.error("Docker daemon didn't start within the timeout period")
            return False
        except subprocess.SubprocessError as e:
            logger.error(f"Error starting Docker daemon: {e}")
            return False
    else:
        logger.error("Could not find Docker installation to start")
        return False

def install_docker():
    """Install Docker on macOS using Homebrew"""
    if not is_macos():
        logger.warning("install_docker() is only supported on macOS")
        return False
    
    # Check if Homebrew is installed
    if shutil.which('brew') is None:
        logger.error("Homebrew is not installed. Please install Homebrew first: https://brew.sh")
        return False
    
    try:
        # Update Homebrew
        logger.info("Updating Homebrew...")
        subprocess.run(['brew', 'update'], check=True)
        
        # Install Docker CLI
        logger.info("Installing Docker CLI...")
        subprocess.run(['brew', 'install', 'docker'], check=True)
        
        # Install Docker Compose
        logger.info("Installing Docker Compose...")
        subprocess.run(['brew', 'install', 'docker-compose'], check=True)
        
        # Install colima (lightweight Docker Desktop alternative for macOS)
        logger.info("Installing Colima (Docker backend)...")
        subprocess.run(['brew', 'install', 'colima'], check=True)
        
        # Start Colima
        logger.info("Starting Colima...")
        subprocess.run(['colima', 'start'], check=True)
        
        # Verify installation
        if is_docker_installed() and is_docker_running():
            logger.info("Docker installed and running successfully")
            return True
        else:
            logger.error("Docker installation completed but Docker is not running")
            return False
            
    except subprocess.SubprocessError as e:
        logger.error(f"Error during Docker installation: {e}")
        return False

def ensure_docker_running():
    """Ensure Docker is installed and running, with user prompts for installation if needed"""
    if not is_docker_installed():
        print("Docker is not installed.")
        response = input("Would you like to install Docker now? (y/n): ")
        if response.lower() in ('y', 'yes'):
            if install_docker():
                print("Docker installed successfully.")
                return True
            else:
                print("Docker installation failed. Please install Docker manually.")
                return False
        else:
            print("Docker is required to run this application.")
            return False
    
    if not is_docker_running():
        print("Docker is installed but not running.")
        response = input("Would you like to start Docker now? (y/n): ")
        if response.lower() in ('y', 'yes'):
            if start_docker():
                print("Docker started successfully.")
                return True
            else:
                print("Failed to start Docker. Please start Docker manually.")
                return False
        else:
            print("Docker must be running to use this application.")
            return False
    
    return True

def get_docker_status():
    """Get current Docker status information"""
    status = {
        "installed": is_docker_installed(),
        "running": False,
        "version": None,
        "containers": {
            "running": 0,
            "total": 0
        }
    }
    
    if status["installed"]:
        status["running"] = is_docker_running()
        
        if status["running"]:
            try:
                # Get Docker version
                version_result = subprocess.run(['docker', 'version', '--format', '{{.Server.Version}}'],
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if version_result.returncode == 0:
                    status["version"] = version_result.stdout.strip()
                
                # Get container counts
                containers_result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Status}}'],
                                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if containers_result.returncode == 0:
                    all_containers = containers_result.stdout.strip().split('\n')
                    status["containers"]["total"] = len(all_containers) if all_containers[0] else 0
                    status["containers"]["running"] = len([c for c in all_containers if c.startswith('Up')]) if all_containers[0] else 0
            except subprocess.SubprocessError:
                pass
    
    return status

if __name__ == "__main__":
    # Simple test when run directly
    logging.basicConfig(level=logging.INFO)
    print(f"Running on macOS: {is_macos()}")
    print(f"Docker installed: {is_docker_installed()}")
    print(f"Docker running: {is_docker_running()}")
    print(f"Docker status: {get_docker_status()}") 