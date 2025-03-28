#!/usr/bin/env python3
"""
Video converter module
Handles conversion of video files to various formats
"""

import os
import subprocess
import logging
import json

logger = logging.getLogger(__name__)

class VideoConverter:
    """Video conversion class using FFmpeg"""
    
    def __init__(self):
        """Initialize the video converter"""
        self._check_ffmpeg()
        
    def _check_ffmpeg(self):
        """Check if FFmpeg is installed"""
        try:
            result = subprocess.run(["ffmpeg", "-version"], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, 
                                    check=False)
            if result.returncode != 0:
                logger.warning("FFmpeg not found or not working properly")
                return False
            return True
        except Exception as e:
            logger.warning(f"Error checking FFmpeg: {e}")
            return False
    
    def convert(self, input_file, output_file, video_format="mp4", quality="medium"):
        """
        Convert video to the desired format
        
        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            video_format: Output format (mp4 or mov)
            quality: Encoding quality (low, medium, high)
            
        Returns:
            bool: True if conversion was successful
        """
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return False
            
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        
        # Determine codec and quality settings based on format and quality
        video_codec = "libx264"  # Default for both mp4 and mov
        
        # Set quality presets
        if quality == "low":
            quality_preset = "faster"
            video_bitrate = "1000k"
            audio_bitrate = "128k"
        elif quality == "high":
            quality_preset = "slow"
            video_bitrate = "4000k"
            audio_bitrate = "320k"
        else:  # medium
            quality_preset = "medium"
            video_bitrate = "2000k"
            audio_bitrate = "192k"
            
        # Basic command with common settings
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-c:v", video_codec,
            "-preset", quality_preset,
            "-b:v", video_bitrate,
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-movflags", "+faststart",  # Optimize for web streaming
            "-y",  # Overwrite output file if it exists
            output_file
        ]
        
        try:
            logger.info(f"Converting video: {input_file} -> {output_file}")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            # Run the conversion process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor the conversion progress
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Extract progress information if available
                    if "time=" in output:
                        logger.debug(output.strip())
            
            # Check if conversion was successful
            if process.returncode == 0:
                logger.info(f"Video conversion complete: {output_file}")
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True
                else:
                    logger.error("Output file is empty or does not exist")
                    return False
            else:
                logger.error(f"FFmpeg returned error code: {process.returncode}")
                return False
                
        except Exception as e:
            logger.error(f"Error converting video: {e}")
            return False
    
    def extract_subtitles(self, input_file, output_dir):
        """Extract subtitles from video file if available"""
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Get subtitle streams
            cmd = [
                "ffprobe", 
                "-v", "quiet", 
                "-print_format", "json", 
                "-show_streams", 
                "-select_streams", "s", 
                input_file
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
            subtitle_info = json.loads(result.stdout)
            
            if 'streams' not in subtitle_info or not subtitle_info['streams']:
                logger.info("No subtitle streams found")
                return []
                
            extracted_files = []
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            
            for i, stream in enumerate(subtitle_info['streams']):
                lang = stream.get('tags', {}).get('language', f'und_{i}')
                out_file = os.path.join(output_dir, f"{base_name}.{lang}.srt")
                
                # Extract subtitle
                extract_cmd = [
                    "ffmpeg",
                    "-i", input_file,
                    "-map", f"0:s:{i}",
                    "-c:s", "srt",
                    "-y",
                    out_file
                ]
                
                subprocess.run(extract_cmd, check=True)
                extracted_files.append(out_file)
                
            return extracted_files
            
        except Exception as e:
            logger.error(f"Error extracting subtitles: {e}")
            return [] 