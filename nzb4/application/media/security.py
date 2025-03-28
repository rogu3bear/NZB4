#!/usr/bin/env python3
"""
Security module for media services.
Provides security-related utilities for input validation and protection.
"""

import os
import re
import logging
import urllib.parse
import hashlib
import psutil
import shutil
import magic  # python-magic for file type detection
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from nzb4.config.settings import config

# Set up logging
logger = logging.getLogger(__name__)

# Common video file extensions
ALLOWED_VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.m4v', '.3gp'
}

# Common audio file extensions
ALLOWED_AUDIO_EXTENSIONS = {
    '.mp3', '.aac', '.wav', '.flac', '.ogg', '.m4a', '.wma'
}

# Common document extensions
ALLOWED_DOCUMENT_EXTENSIONS = {
    '.pdf', '.epub', '.mobi', '.azw', '.azw3', '.txt', '.doc', '.docx'
}

# Allowed file types with MIME types
ALLOWED_MIME_TYPES = {
    # Video
    'video/mp4', 'video/x-matroska', 'video/x-msvideo', 'video/quicktime',
    'video/x-ms-wmv', 'video/x-flv', 'video/webm', 'video/mpeg', 
    
    # Audio
    'audio/mpeg', 'audio/aac', 'audio/wav', 'audio/flac', 'audio/ogg', 
    'audio/mp4', 'audio/x-ms-wma',
    
    # Documents
    'application/pdf', 'application/epub+zip', 'application/x-mobipocket-ebook',
    'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    
    # Archives (for NZB and torrent files)
    'application/x-nzb', 'application/x-bittorrent', 'application/zip', 'application/x-rar-compressed',
    'application/gzip', 'application/x-7z-compressed'
}

# Max file sizes by type (in bytes)
MAX_FILE_SIZES = {
    'video': 20 * 1024 * 1024 * 1024,  # 20GB
    'audio': 2 * 1024 * 1024 * 1024,   # 2GB
    'document': 500 * 1024 * 1024,     # 500MB
    'archive': 100 * 1024 * 1024,      # 100MB
    'nzb': 10 * 1024 * 1024,           # 10MB
    'torrent': 10 * 1024 * 1024        # 10MB
}

# Suspicious file patterns
SUSPICIOUS_PATTERNS = [
    r'\.exe$', r'\.bat$', r'\.cmd$', r'\.sh$', r'\.php$', r'\.phtml$',
    r'\.js$', r'\.cgi$', r'\.asp$', r'\.aspx$', r'\.jsp$'
]


class SecurityValidator:
    """Validator for security-related checks"""
    
    @staticmethod
    def validate_filepath(filepath: str, base_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate that a filepath is safe and doesn't attempt path traversal
        
        Args:
            filepath: The filepath to validate
            base_dir: Optional base directory that the path must be within
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Normalize path
            norm_path = os.path.normpath(filepath)
            
            # Check for suspicious patterns
            path_basename = os.path.basename(norm_path)
            for pattern in SUSPICIOUS_PATTERNS:
                if re.search(pattern, path_basename, re.IGNORECASE):
                    return False, f"Filepath contains suspicious pattern: {pattern}"
            
            # If base directory specified, ensure the path is within it
            if base_dir:
                base_path = os.path.abspath(base_dir)
                abs_path = os.path.abspath(norm_path)
                
                if not abs_path.startswith(base_path):
                    return False, "Filepath attempts directory traversal outside of permitted directory"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"Error validating filepath: {e}")
            return False, f"Error validating filepath: {e}"
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """
        Validate that a URL is safe and properly formatted
        
        Args:
            url: The URL to validate
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Parse URL
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ('http', 'https', 'ftp'):
                return False, f"Unsupported URL scheme: {parsed.scheme}"
            
            # Check for IP addresses instead of hostnames (optional)
            ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
            if re.match(ip_pattern, parsed.netloc):
                # Additional checks for private IP ranges could be added here
                pass
            
            # Check for common signs of injection
            if ';' in url or '&&' in url or '|' in url:
                return False, "URL contains potential command injection characters"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"Error validating URL: {e}")
            return False, f"Error validating URL: {e}"
    
    @staticmethod
    def validate_file_type(filepath: str, allowed_types: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Validate file type using magic numbers (MIME type)
        
        Args:
            filepath: Path to the file
            allowed_types: Optional list of allowed MIME types (defaults to ALLOWED_MIME_TYPES)
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"File doesn't exist: {filepath}"
            
            # Get file MIME type
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(filepath)
            
            # Use default allowed types if none provided
            if allowed_types is None:
                allowed_types = ALLOWED_MIME_TYPES
            
            # Check if file type is allowed
            if file_type not in allowed_types:
                return False, f"File type {file_type} is not allowed"
            
            # Check file size based on type category
            size = os.path.getsize(filepath)
            
            # Determine type category
            category = None
            if file_type.startswith('video/'):
                category = 'video'
            elif file_type.startswith('audio/'):
                category = 'audio'
            elif file_type in ('application/pdf', 'text/plain', 'application/msword'):
                category = 'document'
            elif file_type in ('application/x-nzb'):
                category = 'nzb'
            elif file_type in ('application/x-bittorrent'):
                category = 'torrent'
            elif file_type in ('application/zip', 'application/x-rar-compressed'):
                category = 'archive'
            
            # Check size limit if category is determined
            if category and size > MAX_FILE_SIZES.get(category, 0):
                max_size_mb = MAX_FILE_SIZES[category] / (1024 * 1024)
                return False, f"File exceeds maximum size for {category} ({max_size_mb:.2f} MB)"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"Error validating file type: {e}")
            return False, f"Error validating file type: {e}"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal and command injection
        
        Args:
            filename: The filename to sanitize
            
        Returns:
            str: Sanitized filename
        """
        # Remove path separators and null bytes
        sanitized = re.sub(r'[/\\:\*\?"<>\|\x00]', '', filename)
        
        # Limit length
        if len(sanitized) > 200:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:200-len(ext)] + ext
            
        return sanitized
    
    @staticmethod
    def create_safe_directory(base_dir: str, subdir: str) -> str:
        """
        Create a safe directory with proper permissions
        
        Args:
            base_dir: Base directory
            subdir: Subdirectory to create
            
        Returns:
            str: Path to created directory
        """
        # Sanitize subdirectory name
        safe_subdir = SecurityValidator.sanitize_filename(subdir)
        
        # Create full path ensuring no directory traversal
        full_path = os.path.join(base_dir, safe_subdir)
        
        # Validate path is within base directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(base_dir)):
            raise ValueError(f"Invalid directory path would escape base directory: {full_path}")
        
        # Create directory with proper permissions
        os.makedirs(full_path, mode=0o750, exist_ok=True)
        
        return full_path
    
    @staticmethod
    def calculate_file_hash(filepath: str, algorithm: str = 'sha256') -> str:
        """
        Calculate the hash of a file
        
        Args:
            filepath: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            str: File hash
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        h = hashlib.new(algorithm)
        
        with open(filepath, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                h.update(chunk)
                chunk = f.read(8192)
        
        return h.hexdigest()


class ResourceMonitor:
    """Monitors system resources and enforces limits"""
    
    @staticmethod
    def check_disk_space(directory: str = None, min_free_mb: int = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if there's enough disk space available
        
        Args:
            directory: Directory to check (defaults to download_dir from config)
            min_free_mb: Minimum free space required in MB (defaults from config)
            
        Returns:
            Tuple[bool, Dict]: (has_enough_space, space_info)
        """
        if directory is None:
            directory = config.media.download_dir
        
        if min_free_mb is None:
            min_free_mb = config.media.min_disk_space_mb
        
        try:
            disk_stats = shutil.disk_usage(directory)
            
            free_mb = disk_stats.free / (1024 * 1024)  # Convert to MB
            
            space_info = {
                "total_mb": disk_stats.total / (1024 * 1024),
                "used_mb": disk_stats.used / (1024 * 1024),
                "free_mb": free_mb,
                "percent_used": (disk_stats.used / disk_stats.total) * 100
            }
            
            has_enough_space = free_mb >= min_free_mb
            
            return has_enough_space, space_info
        
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    def check_system_resources() -> Dict[str, Any]:
        """
        Check overall system resources
        
        Returns:
            Dict: Resource usage information
        """
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.5)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get disk I/O
            disk_io = psutil.disk_io_counters()
            
            # Get network I/O
            net_io = psutil.net_io_counters()
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_read_mb": disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                "disk_write_mb": disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                "net_sent_mb": net_io.bytes_sent / (1024 * 1024) if net_io else 0,
                "net_recv_mb": net_io.bytes_recv / (1024 * 1024) if net_io else 0,
                "is_overloaded": cpu_percent > 90 or memory_percent > 90
            }
        
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_process_usage(pid: Optional[int] = None) -> Dict[str, Any]:
        """
        Get resource usage for a specific process
        
        Args:
            pid: Process ID (defaults to current process)
            
        Returns:
            Dict: Process resource usage information
        """
        try:
            if pid is None:
                process = psutil.Process()
            else:
                process = psutil.Process(pid)
            
            # Get process info
            process_info = {
                "pid": process.pid,
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(interval=0.5),
                "memory_percent": process.memory_percent(),
                "memory_mb": process.memory_info().rss / (1024 * 1024),
                "threads": process.num_threads(),
                "created": process.create_time()
            }
            
            return process_info
        
        except Exception as e:
            logger.error(f"Error getting process usage: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def should_throttle() -> bool:
        """
        Determine if the system should throttle operations due to resource constraints
        
        Returns:
            bool: True if system should throttle operations
        """
        try:
            resources = ResourceMonitor.check_system_resources()
            
            # Check if system is overloaded
            if resources.get("is_overloaded", False):
                return True
            
            # Check disk space
            has_space, _ = ResourceMonitor.check_disk_space()
            if not has_space:
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking if should throttle: {e}")
            return True  # Throttle if we can't determine 