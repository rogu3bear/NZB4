"""
Validation Utilities

This module provides functions for validating and sanitizing input data,
particularly for media sources, file paths, and API parameters.
It implements best practices for input validation and security from 
Shopify, MDN, and Python security guidelines.
"""

import os
import re
import logging
import urllib.parse
from typing import Dict, Any, Tuple, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# Safe filename character pattern
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

# Media file extensions that are recognized
MEDIA_EXTENSIONS = {
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'],
    'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'],
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
    'container': ['.nzb', '.torrent']
}

def validate_request_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the request data for the conversion API.
    
    Args:
        data: The JSON payload containing request parameters
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not data:
        return False, "Empty request data"
    
    # Check required fields
    if 'source_path' not in data:
        return False, "Missing required field: source_path"
    
    # Validate source_path
    source_path = data.get('source_path')
    if not source_path:
        return False, "source_path cannot be empty"
    
    # Validate target_format if present
    if 'target_format' in data:
        target_format = data.get('target_format')
        if not target_format:
            return False, "target_format cannot be empty if specified"
        
        # Check if target_format is allowed
        allowed_formats = ['mp4', 'mov']
        if target_format not in allowed_formats:
            return False, f"Invalid target_format. Allowed values: {', '.join(allowed_formats)}"
    
    return True, "Valid request data"

def validate_media_source(source: str) -> Tuple[bool, str]:
    """
    Validate a media source (file path or URL).
    
    Args:
        source: The media source to validate
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not source:
        return False, "Media source cannot be empty"
    
    # URL validation
    if source.startswith(('http://', 'https://', 'ftp://')):
        try:
            result = urllib.parse.urlparse(source)
            if not all([result.scheme, result.netloc]):
                return False, "Invalid URL format"
                
            # Validate URL scheme
            if result.scheme not in ['http', 'https', 'ftp']:
                return False, f"Unsupported URL scheme: {result.scheme}"
                
            # Additional URL validations could be performed here
            # (domain whitelist, safety checks, etc.)
            return True, "Valid URL"
        except Exception as e:
            logger.warning(f"URL validation error: {str(e)}")
            return False, "Invalid URL format"
    
    # File path validation
    if os.path.exists(source):
        # Check if it's a regular file
        if not os.path.isfile(source):
            return False, "Source exists but is not a regular file"
            
        # Check if the file is readable
        if not os.access(source, os.R_OK):
            return False, "Source file is not readable"
            
        # Check file extension
        file_ext = os.path.splitext(source)[1].lower()
        allowed_extensions = []
        for ext_list in MEDIA_EXTENSIONS.values():
            allowed_extensions.extend(ext_list)
            
        if file_ext not in allowed_extensions:
            return False, f"Unsupported file type: {file_ext}"
            
        return True, "Valid file path"
    
    # Search term validation (if it's neither a URL nor existing file)
    if ' ' in source and len(source) > 3:
        # This could be a search term
        return True, "Valid search term"
    
    return False, "Source not found or invalid"

def sanitize_path(path_str: str) -> str:
    """
    Sanitize a file path to prevent path traversal attacks and other security issues.
    
    Args:
        path_str: The path string to sanitize
        
    Returns:
        A sanitized path string
    """
    if not path_str:
        return ""
    
    # Convert to Path object for safe handling
    path = Path(path_str)
    
    # Get just the filename to avoid directory traversal
    filename = path.name
    
    # Replace potentially dangerous characters
    safe_filename = re.sub(r'[^\w\-\.]', '_', filename)
    
    return safe_filename

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to ensure it's safe for use in the file system.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        A sanitized filename
    """
    if not filename:
        return ""
    
    # Remove any directory path
    basename = os.path.basename(filename)
    
    # Remove extension to clean the name
    name_parts = os.path.splitext(basename)
    name = name_parts[0]
    extension = name_parts[1] if len(name_parts) > 1 else ""
    
    # Replace unsafe characters
    safe_name = re.sub(r'[^\w\-\.]', '_', name)
    
    # Recombine with extension
    if extension:
        safe_name = f"{safe_name}{extension}"
    
    return safe_name

def is_path_traversal(path_str: str) -> bool:
    """
    Check if a path contains directory traversal sequences.
    
    Args:
        path_str: The path string to check
        
    Returns:
        True if path traversal detected, False otherwise
    """
    normalized = os.path.normpath(path_str)
    return '..' in normalized.split(os.path.sep)

def validate_output_directory(directory: str) -> Tuple[bool, str]:
    """
    Validate an output directory for writing.
    
    Args:
        directory: The directory path to validate
        
    Returns:
        Tuple of (is_valid, message)
    """
    # Check if directory exists
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            return False, f"Cannot create output directory: {str(e)}"
    
    # Check if it's a directory
    if not os.path.isdir(directory):
        return False, "Path exists but is not a directory"
    
    # Check if it's writable
    if not os.access(directory, os.W_OK):
        return False, "Directory is not writable"
    
    return True, "Valid output directory" 