#!/usr/bin/env python3
"""
Direct downloader module
Handles downloading media directly from URLs or YouTube
"""

import os
import subprocess
import logging
import tempfile
import shutil
import requests
import re
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

class DirectDownloader:
    """Direct downloader class for videos from URLs or YouTube"""
    
    def __init__(self, download_dir="/downloads"):
        """Initialize the direct downloader"""
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
    
    def download(self, url):
        """
        Download file from direct URL
        
        Args:
            url: Direct download URL
            
        Returns:
            list: Paths to downloaded files
        """
        try:
            # Parse URL to get filename
            parsed_url = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or '.' not in filename:
                filename = f"download_{hash(url)}.mp4"  # Default name
            
            # Create output path
            output_path = os.path.join(self.download_dir, filename)
            
            logger.info(f"Downloading from URL: {url}")
            logger.info(f"Output path: {output_path}")
            
            # Use aria2c for efficient downloading
            cmd = [
                "aria2c",
                "--file-allocation=none",  # Faster allocation
                "--check-certificate=false",  # Skip certificate validation
                "--continue=true",  # Resume download if possible
                "--max-tries=5",  # Retry up to 5 times
                "--retry-wait=10",  # Wait 10 seconds between retries
                "--http-accept-gzip=true",  # Accept gzip compression
                "--max-connection-per-server=10",  # Multiple connections
                "-d", os.path.dirname(output_path),  # Download directory
                "-o", os.path.basename(output_path),  # Output filename
                url
            ]
            
            result = subprocess.run(cmd, check=True)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Download complete: {output_path}")
                return [output_path]
            else:
                logger.error("Download failed")
                return []
                
        except Exception as e:
            logger.error(f"Error downloading from URL: {e}")
            
            # Try fallback with requests
            try:
                logger.info("Trying fallback download method...")
                
                # Parse URL to get filename
                parsed_url = urllib.parse.urlparse(url)
                filename = os.path.basename(parsed_url.path)
                
                if not filename or '.' not in filename:
                    filename = f"download_{hash(url)}.mp4"  # Default name
                
                # Create output path
                output_path = os.path.join(self.download_dir, filename)
                
                response = requests.get(url, stream=True, timeout=60, verify=False)
                
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    logger.info(f"Fallback download complete: {output_path}")
                    return [output_path]
                else:
                    logger.error(f"Fallback download failed with status code: {response.status_code}")
                    return []
                    
            except Exception as e2:
                logger.error(f"Error in fallback download: {e2}")
                return []
    
    def download_youtube(self, url):
        """
        Download video from YouTube or other supported platforms
        
        Args:
            url: YouTube video URL
            
        Returns:
            list: Paths to downloaded files
        """
        try:
            # Create temp directory for download
            temp_dir = tempfile.mkdtemp()
            
            logger.info(f"Downloading from YouTube: {url}")
            
            # Use yt-dlp for better compatibility and more sites
            cmd = [
                "yt-dlp",
                "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # Prefer MP4
                "--merge-output-format", "mp4",  # Always output MP4
                "--no-playlist",  # Skip playlists
                "--output", os.path.join(temp_dir, "%(title)s.%(ext)s"),  # Output filename template
                url
            ]
            
            result = subprocess.run(cmd, check=True)
            
            if result.returncode == 0:
                # Find the downloaded file
                files = []
                for root, _, filenames in os.walk(temp_dir):
                    for filename in filenames:
                        if filename.endswith(('.mp4', '.mkv', '.webm', '.avi')):
                            src_path = os.path.join(root, filename)
                            dst_path = os.path.join(self.download_dir, filename)
                            shutil.move(src_path, dst_path)
                            files.append(dst_path)
                
                if files:
                    logger.info(f"YouTube download complete: {files}")
                    return files
                else:
                    logger.error("No video files found after YouTube download")
                    return []
            else:
                logger.error("YouTube download failed")
                return []
                
        except Exception as e:
            logger.error(f"Error downloading from YouTube: {e}")
            return []
            
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    
    def download_m3u8(self, url):
        """
        Download HLS stream (m3u8)
        
        Args:
            url: M3U8 stream URL
            
        Returns:
            list: Paths to downloaded files
        """
        try:
            # Generate output filename
            output_filename = f"stream_{hash(url)}.mp4"
            output_path = os.path.join(self.download_dir, output_filename)
            
            logger.info(f"Downloading HLS stream: {url}")
            
            # Use FFmpeg to download and convert the stream
            cmd = [
                "ffmpeg",
                "-i", url,
                "-c", "copy",  # Copy without re-encoding
                "-bsf:a", "aac_adtstoasc",  # Fix for aac streams
                "-y",  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(cmd, check=True)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"HLS stream download complete: {output_path}")
                return [output_path]
            else:
                logger.error("HLS stream download failed")
                return []
                
        except Exception as e:
            logger.error(f"Error downloading HLS stream: {e}")
            return [] 