#!/usr/bin/env python3
"""
Torrent downloader module
Handles downloading from torrents using Transmission
"""

import os
import time
import subprocess
import logging
import json
import requests
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class TorrentDownloader:
    """Torrent downloader class using Transmission"""
    
    def __init__(self, download_dir="/downloads", port=9091):
        """Initialize the torrent downloader"""
        self.download_dir = download_dir
        self.port = port
        self.session_id = None
        self._ensure_transmission_running()
    
    def _ensure_transmission_running(self):
        """Make sure Transmission daemon is running"""
        try:
            # Check if Transmission is running
            result = subprocess.run(["pgrep", "-f", "transmission-daemon"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   check=False)
            
            if result.returncode != 0:
                # Start transmission-daemon
                logger.info("Starting Transmission daemon...")
                subprocess.run(["transmission-daemon", "-g", "/config/transmission"], check=True)
                time.sleep(3)  # Wait for daemon to start
                
                # Set download directory
                self._set_download_directory()
            
            # Test connection to API
            self._get_session_id()
            logger.info("Transmission daemon is running")
            return True
            
        except Exception as e:
            logger.warning(f"Error ensuring Transmission is running: {e}")
            return False
    
    def _set_download_directory(self):
        """Set Transmission download directory"""
        settings_file = "/config/transmission/settings.json"
        
        if os.path.exists(settings_file):
            try:
                # Stop transmission
                subprocess.run(["killall", "transmission-daemon"], check=False)
                time.sleep(1)
                
                # Read settings
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                
                # Update download directory
                settings['download-dir'] = self.download_dir
                
                # Write back
                with open(settings_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                
                # Restart transmission
                subprocess.run(["transmission-daemon", "-g", "/config/transmission"], check=True)
                time.sleep(3)
                
                logger.info(f"Set Transmission download directory to {self.download_dir}")
            except Exception as e:
                logger.warning(f"Error setting download directory: {e}")
    
    def _get_session_id(self):
        """Get Transmission session ID for API calls"""
        try:
            response = requests.get(f"http://localhost:{self.port}/transmission/rpc",
                                   headers={'X-Transmission-Session-Id': '0'})
            
            if response.status_code == 409:
                self.session_id = response.headers.get('X-Transmission-Session-Id')
                return self.session_id
            else:
                logger.warning(f"Unexpected response from Transmission API: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Error getting Transmission session ID: {e}")
            return None
    
    def _add_torrent(self, torrent_source):
        """
        Add a torrent to Transmission
        
        Args:
            torrent_source: Path to .torrent file or magnet link
            
        Returns:
            int: Torrent ID if successful, None otherwise
        """
        if not self.session_id:
            self._get_session_id()
            
        if not self.session_id:
            logger.error("Failed to get Transmission session ID")
            return None
            
        headers = {
            'X-Transmission-Session-Id': self.session_id,
            'Content-Type': 'application/json'
        }
        
        # Determine if source is a file path or magnet link
        payload = {
            "method": "torrent-add",
            "arguments": {}
        }
        
        if os.path.exists(torrent_source):
            # Read torrent file and encode as base64
            with open(torrent_source, 'rb') as f:
                import base64
                torrent_data = base64.b64encode(f.read()).decode('utf-8')
                payload["arguments"]["metainfo"] = torrent_data
        elif torrent_source.startswith('magnet:'):
            # Use magnet link directly
            payload["arguments"]["filename"] = torrent_source
        else:
            logger.error(f"Invalid torrent source: {torrent_source}")
            return None
            
        try:
            response = requests.post(f"http://localhost:{self.port}/transmission/rpc", 
                                    headers=headers, 
                                    json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and result['result'] == 'success':
                    if 'arguments' in result and 'torrent-added' in result['arguments']:
                        torrent_id = result['arguments']['torrent-added']['id']
                        logger.info(f"Torrent added with ID: {torrent_id}")
                        return torrent_id
                    elif 'arguments' in result and 'torrent-duplicate' in result['arguments']:
                        torrent_id = result['arguments']['torrent-duplicate']['id']
                        logger.info(f"Torrent already exists with ID: {torrent_id}")
                        return torrent_id
            
            logger.error(f"Failed to add torrent: {response.json()}")
            return None
            
        except Exception as e:
            logger.error(f"Error adding torrent: {e}")
            return None
    
    def _wait_for_torrent(self, torrent_id, max_wait_time=3600):
        """
        Wait for torrent to complete downloading
        
        Args:
            torrent_id: ID of the torrent
            max_wait_time: Maximum wait time in seconds
            
        Returns:
            bool: True if download completed successfully
        """
        if not self.session_id:
            self._get_session_id()
            
        if not self.session_id:
            logger.error("Failed to get Transmission session ID")
            return False
            
        headers = {
            'X-Transmission-Session-Id': self.session_id,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "method": "torrent-get",
            "arguments": {
                "ids": [torrent_id],
                "fields": ["id", "name", "status", "percentDone", "downloadDir", "error", "errorString"]
            }
        }
        
        start_time = time.time()
        wait_interval = 10  # Seconds between status checks
        
        while (time.time() - start_time) < max_wait_time:
            try:
                response = requests.post(f"http://localhost:{self.port}/transmission/rpc", 
                                        headers=headers, 
                                        json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'result' in result and result['result'] == 'success':
                        if 'arguments' in result and 'torrents' in result['arguments']:
                            torrents = result['arguments']['torrents']
                            if torrents:
                                torrent = torrents[0]
                                percent_done = torrent.get('percentDone', 0) * 100
                                status = torrent.get('status', 0)
                                name = torrent.get('name', 'Unknown')
                                
                                status_text = "Unknown"
                                if status == 0:
                                    status_text = "Stopped"
                                elif status == 1:
                                    status_text = "Check waiting"
                                elif status == 2:
                                    status_text = "Checking"
                                elif status == 3:
                                    status_text = "Download waiting"
                                elif status == 4:
                                    status_text = "Downloading"
                                elif status == 5:
                                    status_text = "Seed waiting"
                                elif status == 6:
                                    status_text = "Seeding"
                                
                                logger.info(f"Torrent: {name} - Status: {status_text} - Progress: {percent_done:.2f}%")
                                
                                # Check for errors
                                error = torrent.get('error', 0)
                                if error != 0:
                                    error_string = torrent.get('errorString', 'Unknown error')
                                    logger.error(f"Torrent error: {error_string}")
                                
                                # Check if download is complete
                                if percent_done >= 100:
                                    logger.info(f"Torrent download complete: {name}")
                                    return True
                    
                time.sleep(wait_interval)
                
            except Exception as e:
                logger.warning(f"Error checking torrent status: {e}")
                time.sleep(wait_interval)
        
        logger.warning(f"Maximum wait time reached for torrent ID {torrent_id}")
        return False
    
    def _get_torrent_files(self, torrent_id):
        """Get the files associated with a torrent"""
        if not self.session_id:
            self._get_session_id()
            
        if not self.session_id:
            logger.error("Failed to get Transmission session ID")
            return []
            
        headers = {
            'X-Transmission-Session-Id': self.session_id,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "method": "torrent-get",
            "arguments": {
                "ids": [torrent_id],
                "fields": ["id", "name", "downloadDir", "files"]
            }
        }
        
        try:
            response = requests.post(f"http://localhost:{self.port}/transmission/rpc", 
                                    headers=headers, 
                                    json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and result['result'] == 'success':
                    if 'arguments' in result and 'torrents' in result['arguments']:
                        torrents = result['arguments']['torrents']
                        if torrents:
                            torrent = torrents[0]
                            download_dir = torrent.get('downloadDir', self.download_dir)
                            files = torrent.get('files', [])
                            
                            file_paths = []
                            for file in files:
                                file_path = os.path.join(download_dir, file.get('name', ''))
                                if os.path.exists(file_path):
                                    file_paths.append(file_path)
                            
                            return file_paths
            
            logger.error("Failed to get torrent files")
            return []
            
        except Exception as e:
            logger.error(f"Error getting torrent files: {e}")
            return []
    
    def download(self, torrent_source):
        """
        Download content from a torrent
        
        Args:
            torrent_source: Path to .torrent file or magnet link
            
        Returns:
            list: Paths to downloaded files
        """
        try:
            # Make sure Transmission is running
            if not self._ensure_transmission_running():
                logger.error("Failed to start Transmission")
                return []
                
            # Add torrent to Transmission
            torrent_id = self._add_torrent(torrent_source)
            if torrent_id is None:
                logger.error("Failed to add torrent")
                return []
                
            # Wait for torrent to complete
            if not self._wait_for_torrent(torrent_id):
                logger.warning("Torrent download did not complete successfully")
                # Continue anyway in case some files were downloaded
            
            # Get files from torrent
            files = self._get_torrent_files(torrent_id)
            
            if not files:
                logger.error("No files found in torrent")
            else:
                logger.info(f"Downloaded {len(files)} files from torrent")
                
            return files
            
        except Exception as e:
            logger.error(f"Error in torrent download: {e}")
            return [] 