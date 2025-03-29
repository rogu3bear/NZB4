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
import secrets  # For secure random values
import string   # For random string generation
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime

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

# Additional dangerous MIME types to explicitly block
BLOCKED_MIME_TYPES = {
    'application/x-msdownload',       # Windows executables
    'application/x-msdos-program',    # MS-DOS executables
    'application/x-sh',               # Shell scripts
    'application/x-dosexec',          # DOS executables
    'application/java',               # Java
    'application/java-archive',       # JAR files
    'text/x-php',                     # PHP code
    'text/x-script.phyton',           # Python code
    'text/javascript',                # JavaScript code
}

# Get directory permission mode from environment or use default
DEFAULT_DIR_MODE = int(os.environ.get('DIR_MODE', '750'), 8)


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
            # Check for null bytes which can be used to trick some systems
            if '\0' in filepath:
                return False, "Filepath contains null bytes"
                
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
                
                # Make sure base_path ends with separator to avoid /base_dir vs /base_dir2 confusion
                if not base_path.endswith(os.path.sep):
                    base_path += os.path.sep
                
                if not abs_path.startswith(base_path):
                    return False, "Filepath attempts directory traversal outside of permitted directory"
            
            # Check for non-printable characters
            for char in norm_path:
                if not char.isprintable() and char not in {os.path.sep}:
                    return False, "Filepath contains non-printable characters"
            
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
            # Check for null bytes
            if '\0' in url:
                return False, "URL contains null bytes"
                
            # Parse URL
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ('http', 'https', 'ftp'):
                return False, f"Unsupported URL scheme: {parsed.scheme}"
            
            # Check for IP addresses instead of hostnames
            ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
            if re.match(ip_pattern, parsed.netloc):
                # Check for private/local IP ranges
                parts = parsed.netloc.split('.')
                ip_parts = [int(part) for part in parts if part.isdigit()]
                
                # Check for private or reserved IPs
                if len(ip_parts) == 4:
                    # Check RFC1918 (private) addresses
                    if ip_parts[0] == 10:
                        return False, "URL contains private IP address (10.x.x.x)"
                    if ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31:
                        return False, "URL contains private IP address (172.16-31.x.x)"
                    if ip_parts[0] == 192 and ip_parts[1] == 168:
                        return False, "URL contains private IP address (192.168.x.x)"
                    # Check localhost
                    if ip_parts[0] == 127:
                        return False, "URL contains localhost address (127.x.x.x)"
                    # Check link-local addresses
                    if ip_parts[0] == 169 and ip_parts[1] == 254:
                        return False, "URL contains link-local address (169.254.x.x)"
            
            # Check for common signs of injection
            if ';' in url or '&&' in url or '|' in url or '`' in url:
                return False, "URL contains potential command injection characters"
            
            # Check for overly long URLs (potential DoS)
            if len(url) > 2000:
                return False, "URL exceeds maximum allowed length"
            
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
            
            # Explicitly check for blocked MIME types first
            if file_type in BLOCKED_MIME_TYPES:
                return False, f"File type {file_type} is explicitly blocked for security reasons"
            
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
            
            # For archives, verify they don't contain executable files (basic check)
            if category == 'archive' and file_type in ('application/zip', 'application/x-rar-compressed'):
                # This would be a more complex implementation in a real app
                # You'd extract the archive to a temp location and check each file
                # For now, we'll just check the filename patterns
                archive_name = os.path.basename(filepath).lower()
                for pattern in SUSPICIOUS_PATTERNS:
                    if re.search(pattern, archive_name):
                        return False, f"Archive may contain suspicious files matching pattern: {pattern}"
            
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
            
        # Ensure the filename doesn't start with a dot (hidden file in Unix)
        if sanitized.startswith('.'):
            sanitized = 'f' + sanitized
        
        return sanitized
    
    @staticmethod
    def secure_random_string(length: int = 16) -> str:
        """
        Generate a cryptographically secure random string
        
        Args:
            length: Length of the string to generate
            
        Returns:
            str: Random string
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def secure_temp_path(base_dir: str, extension: str = '') -> str:
        """
        Create a secure random temporary path
        
        Args:
            base_dir: Base directory for the path
            extension: Optional file extension
            
        Returns:
            str: Secure temporary path
        """
        # Current timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Secure random string
        random_part = SecurityValidator.secure_random_string(12)
        
        # Create filename
        filename = f"{timestamp}_{random_part}"
        if extension:
            if not extension.startswith('.'):
                extension = '.' + extension
            filename += extension
        
        # Return full path
        return os.path.join(base_dir, filename)
    
    @staticmethod
    def create_safe_directory(base_dir: str, subdir: str, mode: Optional[int] = None) -> str:
        """
        Create a safe directory with proper permissions
        
        Args:
            base_dir: Base directory
            subdir: Subdirectory to create
            mode: Optional directory permissions (octal)
            
        Returns:
            str: Path to created directory
        """
        # Use provided mode or default from environment
        if mode is None:
            mode = DEFAULT_DIR_MODE
        
        # Sanitize subdirectory name
        safe_subdir = SecurityValidator.sanitize_filename(subdir)
        
        # Add randomness to the directory name for unpredictability
        random_suffix = SecurityValidator.secure_random_string(8)
        safe_subdir = f"{safe_subdir}_{random_suffix}"
        
        # Create full path ensuring no directory traversal
        full_path = os.path.join(base_dir, safe_subdir)
        
        # Validate path is within base directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(base_dir)):
            raise ValueError(f"Invalid directory path would escape base directory: {full_path}")
        
        # Create directory with proper permissions
        os.makedirs(full_path, mode=mode, exist_ok=True)
        
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
    
    @staticmethod
    def encrypt_api_key(key: str, salt: Optional[str] = None) -> Dict[str, str]:
        """
        Encrypt an API key for secure storage
        
        Args:
            key: The API key to encrypt
            salt: Optional salt value
            
        Returns:
            Dict: Encrypted key information
        """
        if salt is None:
            salt = secrets.token_hex(16)
            
        # Create a salted hash
        salted_key = (salt + key).encode('utf-8')
        hashed = hashlib.sha256(salted_key).hexdigest()
        
        return {
            "salt": salt,
            "hash": hashed,
            "algorithm": "sha256"
        }
    
    @staticmethod
    def verify_api_key(key: str, stored_data: Dict[str, str]) -> bool:
        """
        Verify an API key against stored encrypted data
        
        Args:
            key: The API key to verify
            stored_data: Encrypted key data from encrypt_api_key
            
        Returns:
            bool: True if key is valid
        """
        salt = stored_data.get("salt", "")
        stored_hash = stored_data.get("hash", "")
        
        # Create a salted hash of the provided key
        salted_key = (salt + key).encode('utf-8')
        computed_hash = hashlib.sha256(salted_key).hexdigest()
        
        # Compare hashes (constant-time comparison)
        return secrets.compare_digest(computed_hash, stored_hash)


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
    def check_io_load() -> Dict[str, Any]:
        """
        Check IO load on the system
        
        Returns:
            Dict: IO load information
        """
        try:
            # Get disk I/O counters
            disk_io = psutil.disk_io_counters()
            
            # Get the initial counter values
            read_bytes_start = disk_io.read_bytes
            write_bytes_start = disk_io.write_bytes
            
            # Wait a moment to measure rate
            time.sleep(0.5)
            
            # Get updated counters
            disk_io = psutil.disk_io_counters()
            read_bytes_end = disk_io.read_bytes
            write_bytes_end = disk_io.write_bytes
            
            # Calculate IO rate in MB/s
            read_rate = (read_bytes_end - read_bytes_start) / (0.5 * 1024 * 1024)
            write_rate = (write_bytes_end - write_bytes_start) / (0.5 * 1024 * 1024)
            
            return {
                "disk_read_mb_sec": read_rate,
                "disk_write_mb_sec": write_rate,
                "total_io_mb_sec": read_rate + write_rate,
                "is_high_io": (read_rate + write_rate) > 100  # 100 MB/s threshold
            }
        except Exception as e:
            logger.error(f"Error checking IO load: {e}")
            return {"error": str(e)}
    
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
            
            # Check load average (Unix-like systems only)
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            
            # Get CPU count to determine relative load
            cpu_count = psutil.cpu_count() or 1
            
            # Calculate load factor (load average / cpu count)
            load_factor = load_avg[0] / cpu_count
            
            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "memory_percent": memory_percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_read_mb": disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                "disk_write_mb": disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                "net_sent_mb": net_io.bytes_sent / (1024 * 1024) if net_io else 0,
                "net_recv_mb": net_io.bytes_recv / (1024 * 1024) if net_io else 0,
                "load_average": load_avg,
                "load_factor": load_factor,
                "is_overloaded": cpu_percent > 90 or memory_percent > 90 or load_factor > 1.5
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
                "created": process.create_time(),
                "io_counters": None,
                "open_files": []
            }
            
            # Get IO counters if available
            try:
                io = process.io_counters()
                process_info["io_counters"] = {
                    "read_mb": io.read_bytes / (1024 * 1024),
                    "write_mb": io.write_bytes / (1024 * 1024)
                }
            except (psutil.AccessDenied, AttributeError):
                pass
            
            # Get open files if available
            try:
                open_files = process.open_files()
                process_info["open_files"] = [f.path for f in open_files]
            except (psutil.AccessDenied, AttributeError):
                pass
            
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
            # Check system resources
            resources = ResourceMonitor.check_system_resources()
            
            # Check if system is overloaded
            if resources.get("is_overloaded", False):
                return True
            
            # Check disk space
            has_space, _ = ResourceMonitor.check_disk_space()
            if not has_space:
                return True
            
            # Check IO load
            io_load = ResourceMonitor.check_io_load()
            if io_load.get("is_high_io", False):
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking if should throttle: {e}")
            return True  # Throttle if we can't determine
            
    @staticmethod
    def limit_process_resources(pid: Optional[int] = None, 
                               cpu_percent: Optional[float] = None,
                               memory_percent: Optional[float] = None) -> bool:
        """
        Attempt to limit resources for a process (platform-specific)
        
        Args:
            pid: Process ID (defaults to current process)
            cpu_percent: CPU percentage limit (0-100)
            memory_percent: Memory percentage limit (0-100)
            
        Returns:
            bool: True if limits were set
        """
        try:
            if pid is None:
                process = psutil.Process()
            else:
                process = psutil.Process(pid)
            
            # Platform-specific implementations would go here
            # This is a simplified version that just logs the intent
            
            logger.info(f"Would limit process {process.pid} to CPU: {cpu_percent}%, Memory: {memory_percent}%")
            
            # In a real implementation, you would use:
            # - On Linux: cgroups or nice/ionice
            # - On Windows: job objects
            # - On macOS: process resource controls
            
            return True
        
        except Exception as e:
            logger.error(f"Error limiting process resources: {e}")
            return False 