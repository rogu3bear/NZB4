#!/usr/bin/env python3
"""
Usenet downloader module
Handles downloading from Usenet using SABnzbd with free server support
"""

import os
import time
import subprocess
import logging
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

class UsenetDownloader:
    """Usenet downloader class using SABnzbd"""
    
    def __init__(self, download_dir="/downloads", config_dir="/config/sabnzbd", port=8080):
        """Initialize the Usenet downloader"""
        self.download_dir = download_dir
        self.config_dir = config_dir
        self.port = port
        self.api_key = self._get_api_key()
        self._setup_free_servers()
        
    def _get_api_key(self):
        """Get SABnzbd API key from config file"""
        api_key = "apikey"  # Default value
        config_path = os.path.join(self.config_dir, "sabnzbd.ini")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        if line.startswith("api_key"):
                            api_key = line.split("=")[1].strip()
                            break
            except Exception as e:
                logger.warning(f"Error reading config file: {e}")
                
        return api_key
    
    def _setup_free_servers(self):
        """Set up free Usenet servers in SABnzbd"""
        free_servers = [
            {
                "name": "Free-Usenet-Server",
                "host": "news.free-usenet.org",
                "port": 443,
                "username": "",
                "password": "",
                "ssl": 1,
                "connections": 4
            },
            {
                "name": "XS-Usenet-Free",
                "host": "reader.xsusenet.com",
                "port": 443,
                "username": "",
                "password": "",
                "ssl": 1,
                "connections": 3
            },
            {
                "name": "Free-Usenet-News",
                "host": "free.usenetserver.com",
                "port": 563,
                "username": "",
                "password": "",
                "ssl": 1,
                "connections": 5
            }
        ]
        
        # Try to add free servers to SABnzbd
        for server in free_servers:
            try:
                # Check if SABnzbd is running
                r = requests.get(f"http://localhost:{self.port}/sabnzbd/api", params={
                    "mode": "get_config",
                    "section": "servers",
                    "output": "json",
                    "apikey": self.api_key
                }, timeout=5)
                
                if r.status_code != 200:
                    logger.warning("SABnzbd API not available, skip adding free servers")
                    break
                    
                # Add server if not already added
                response = r.json()
                existing_servers = [s.get('name') for s in response.get('config', {}).get('servers', [])]
                
                if server['name'] not in existing_servers:
                    logger.info(f"Adding free Usenet server: {server['name']}")
                    
                    params = {
                        "mode": "config",
                        "name": "addserver",
                        "apikey": self.api_key,
                        "output": "json",
                        "host": server['host'],
                        "port": server['port'],
                        "username": server['username'],
                        "password": server['password'],
                        "ssl": server['ssl'],
                        "connections": server['connections']
                    }
                    
                    r = requests.get(f"http://localhost:{self.port}/sabnzbd/api", params=params, timeout=5)
                    
                    if r.status_code == 200:
                        logger.info(f"Added free server: {server['name']}")
                    else:
                        logger.warning(f"Failed to add server: {server['name']}")
                        
            except Exception as e:
                logger.warning(f"Error setting up free server {server['name']}: {e}")
    
    def download(self, nzb_file):
        """
        Download from Usenet using SABnzbd
        
        Args:
            nzb_file: Path to NZB file
            
        Returns:
            list: Paths to downloaded files
        """
        if not os.path.exists(nzb_file):
            logger.error(f"NZB file not found: {nzb_file}")
            return []
            
        try:
            # Check if SABnzbd is running
            try:
                subprocess.run(["pgrep", "-f", "sabnzbd"], check=True, stdout=subprocess.PIPE)
                logger.info("SABnzbd is already running")
            except subprocess.CalledProcessError:
                # Start SABnzbd if not running
                logger.info("Starting SABnzbd...")
                sabnzbd_process = subprocess.Popen([
                    "sabnzbd", 
                    "-d",
                    "-b", "0",
                    "-f", self.config_dir
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Wait for SABnzbd to start
                time.sleep(5)
            
            # Try to get content name from NZB file
            try:
                tree = ET.parse(nzb_file)
                root = tree.getroot()
                subject_element = root.find(".//meta[@type='subject']")
                if subject_element is not None:
                    content_name = subject_element.text.split('\"')[1] if '\"' in subject_element.text else subject_element.text
                else:
                    content_name = os.path.basename(nzb_file).replace('.nzb', '')
            except Exception:
                content_name = os.path.basename(nzb_file).replace('.nzb', '')
            
            # Create a unique folder for this download
            folder_name = content_name.replace(' ', '_').replace('.', '_')
            download_folder = os.path.join(self.download_dir, folder_name)
            os.makedirs(download_folder, exist_ok=True)
            
            # Add NZB to SABnzbd
            logger.info(f"Adding NZB file to SABnzbd: {nzb_file}")
            
            add_nzb_cmd = [
                "curl", "-s",
                f"http://localhost:{self.port}/sabnzbd/api",
                "--form", f"apikey={self.api_key}",
                "--form", "mode=addlocalfile",
                "--form", f"name=@{nzb_file}",
                "--form", f"dir={download_folder}"
            ]
            
            result = subprocess.run(add_nzb_cmd, stdout=subprocess.PIPE, check=True)
            response = result.stdout.decode('utf-8')
            
            if "error" in response.lower() or "failed" in response.lower():
                logger.error(f"Error adding NZB to SABnzbd: {response}")
                return []
            
            logger.info("NZB added to SABnzbd. Waiting for download to complete...")
            logger.info(f"You can monitor the progress at http://localhost:{self.port}/sabnzbd/")
            
            # Check download status periodically
            max_wait_time = 60 * 60  # 1 hour max wait time
            wait_interval = 10  # 10 seconds between checks
            total_wait_time = 0
            
            while total_wait_time < max_wait_time:
                status_cmd = [
                    "curl", "-s",
                    f"http://localhost:{self.port}/sabnzbd/api?apikey={self.api_key}&mode=queue&output=json"
                ]
                
                try:
                    status_output = subprocess.check_output(status_cmd).decode('utf-8')
                    status_json = json.loads(status_output)
                    
                    # Check if queue is empty (download complete)
                    if status_json.get('queue', {}).get('slots', []) == []:
                        logger.info("Download appears to be complete")
                        # Wait a bit for post-processing
                        time.sleep(5)
                        break
                    
                    # Check jobs in queue
                    jobs = status_json.get('queue', {}).get('slots', [])
                    if jobs:
                        job = jobs[0]  # Look at first job
                        percentage = job.get('percentage', '0')
                        status = job.get('status', '')
                        logger.info(f"Download progress: {percentage}% - {status}")
                        
                        # Check for errors
                        if "failed" in status.lower() or "error" in status.lower():
                            logger.error(f"Download error: {status}")
                            break
                    
                    # Wait before next check
                    time.sleep(wait_interval)
                    total_wait_time += wait_interval
                    
                except Exception as e:
                    logger.warning(f"Error checking status: {e}")
                    time.sleep(wait_interval)
                    total_wait_time += wait_interval
            
            # Find all files in the download folder
            all_files = []
            for root, _, files in os.walk(download_folder):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            logger.info(f"Found {len(all_files)} files in download folder")
            return all_files
            
        except Exception as e:
            logger.error(f"Error in Usenet download: {e}")
            return [] 