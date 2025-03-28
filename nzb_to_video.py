#!/usr/bin/env python3
"""
NZB to Video Converter
Converts NZB files to MP4/MOV by downloading, unpacking, and processing content
"""

import os
import sys
import subprocess
import argparse
import logging
import shutil
import tempfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required tools are installed"""
    tools = ['sabnzbd', 'ffmpeg']
    missing = []
    
    for tool in tools:
        if shutil.which(tool) is None:
            missing.append(tool)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Install dependencies using:")
        if 'sabnzbd' in missing:
            logger.info("  - SABnzbd: https://sabnzbd.org/download")
        if 'ffmpeg' in missing:
            logger.info("  - FFmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu/Debian)")
        return False
    return True

def process_nzb(nzb_file, output_dir, video_format="mp4", download_dir="/downloads"):
    """Process the NZB file using SABnzbd to download and extract content"""
    if not os.path.exists(nzb_file):
        logger.error(f"NZB file not found: {nzb_file}")
        return None
    
    # Use specified download directory or create a temporary one
    temp_dir = None
    if not os.path.exists(download_dir):
        temp_dir = tempfile.mkdtemp()
        download_dir = temp_dir
        logger.info(f"Created temporary directory for downloads: {download_dir}")
    
    try:
        # Check if SABnzbd is already running
        try:
            subprocess.run(["pgrep", "-f", "sabnzbd"], check=True, stdout=subprocess.PIPE)
            logger.info("SABnzbd is already running")
            sabnzbd_running = True
        except subprocess.CalledProcessError:
            sabnzbd_running = False
        
        if not sabnzbd_running:
            # Start SABnzbd in background
            logger.info("Starting SABnzbd...")
            sabnzbd_process = subprocess.Popen([
                "sabnzbd", 
                "-d",
                "-b", "0",
                "-f", "/config/sabnzbd"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for SABnzbd to start
            time.sleep(5)
        
        # Add NZB to SABnzbd via API
        logger.info(f"Adding NZB file to SABnzbd: {nzb_file}")
        
        # Get API key from config or use default for Docker setup
        api_key = "apikey"
        config_path = "/config/sabnzbd/sabnzbd.ini"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                for line in f:
                    if line.startswith("api_key"):
                        api_key = line.split("=")[1].strip()
                        break
        
        # Add NZB file using API
        add_nzb_cmd = [
            "curl", "-s",
            f"http://localhost:8080/sabnzbd/api",
            "--form", f"apikey={api_key}",
            "--form", "mode=addlocalfile",
            "--form", f"name=@{nzb_file}",
            "--form", f"dir={download_dir}"
        ]
        
        subprocess.run(add_nzb_cmd, check=True)
        
        logger.info("NZB added to SABnzbd. Waiting for download to complete...")
        logger.info("You can monitor the progress at http://localhost:8080/sabnzbd/")
        
        # Check download status periodically
        while True:
            status_cmd = [
                "curl", "-s",
                f"http://localhost:8080/sabnzbd/api?apikey={api_key}&mode=queue&output=json"
            ]
            
            try:
                status_output = subprocess.check_output(status_cmd).decode('utf-8')
                
                # Very simple check - if no jobs in queue, assume complete
                if '"noofslots": 0' in status_output:
                    logger.info("Download appears to be complete")
                    break
                
                logger.info("Download in progress, waiting 30 seconds...")
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error checking status: {e}")
                logger.info("Assuming download is complete")
                break
        
        # Give it a moment for post-processing
        time.sleep(10)
        
        # Look for video files in the download directory
        video_files = find_video_files(download_dir)
        if not video_files:
            logger.error("No video files found in downloaded content")
            return None
        
        # Convert to desired format
        output_file = os.path.join(output_dir, f"{os.path.basename(nzb_file).split('.')[0]}.{video_format}")
        convert_video(video_files[0], output_file, video_format)
        
        return output_file
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error processing NZB file: {e}")
        return None
    finally:
        # Clean up temp directory if we created one
        if temp_dir:
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)

def find_video_files(directory):
    """Find all video files in the given directory"""
    video_extensions = ['.avi', '.mkv', '.mp4', '.mov', '.wmv', '.flv', '.webm']
    video_files = []
    
    logger.info(f"Searching for video files in: {directory}")
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(root, file))
    
    if video_files:
        logger.info(f"Found {len(video_files)} video files. Largest: {video_files[0]}")
    
    return sorted(video_files, key=os.path.getsize, reverse=True)

def convert_video(input_file, output_file, video_format="mp4"):
    """Convert video to the desired format using FFmpeg"""
    logger.info(f"Converting video to {video_format}: {input_file} -> {output_file}")
    
    # Determine codec based on format
    video_codec = "libx264"  # Default for both mp4 and mov
    
    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-c:v", video_codec,
        "-c:a", "aac",
        "-strict", "experimental",
        "-b:a", "192k",
        "-y",  # Overwrite output file if it exists
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"Video conversion complete: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error converting video: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Convert NZB files to video (MP4/MOV)")
    parser.add_argument("nzb_file", help="Path to the NZB file")
    parser.add_argument("-o", "--output-dir", default="/complete", help="Output directory (default: /complete)")
    parser.add_argument("-d", "--download-dir", default="/downloads", help="Download directory (default: /downloads)")
    parser.add_argument("-f", "--format", choices=["mp4", "mov"], default="mp4", help="Output video format (default: mp4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Process NZB file
    output_file = process_nzb(args.nzb_file, args.output_dir, args.format, args.download_dir)
    
    if output_file and os.path.exists(output_file):
        logger.info(f"Conversion successful. Output file: {output_file}")
    else:
        logger.error("Conversion failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 