#!/usr/bin/env python3
""" 
app.py - Flask application for media conversion.

This implementation features enhanced error handling, input validation, logging,
and follows best practices inspired by Shopify docs, MDN security guidelines,
and incorporates type annotations.
"""

from flask import Flask, request, jsonify, Response, send_from_directory
import logging
import os
import time
from typing import Any, Dict, Tuple, Optional, Union
import traceback
from werkzeug.exceptions import HTTPException
from functools import wraps
import secrets
import re

# Import media conversion functionality
from media_converter import process_media, organize_output_path
from nzb4.utils.validation import validate_media_source, sanitize_path

# Configure application
app = Flask(__name__)
app.config['DEBUG'] = False  # Ensure debug mode is off in production
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Limit uploads to 50MB
app.config['OUTPUT_DIR'] = os.environ.get('OUTPUT_DIR', '/complete')
app.config['DOWNLOAD_DIR'] = os.environ.get('DOWNLOAD_DIR', '/downloads')
app.config['ALLOWED_FORMATS'] = ['mp4', 'mov']

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(process)d - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Request ID middleware for traceability
def request_id_middleware():
    """Generate a unique request ID for each request to improve traceability."""
    request.request_id = secrets.token_hex(8)
    logger.info(f"Request started: {request.method} {request.path} [ID: {request.request_id}]")

app.before_request(request_id_middleware)

# Rate limiting (simple implementation)
request_history = {}

def rate_limit(max_requests: int = 10, window: int = 60):
    """
    Simple rate limiting decorator.
    
    Args:
        max_requests: Maximum number of requests allowed in the time window
        window: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr
            current_time = time.time()
            
            # Clean up old entries
            if ip in request_history:
                request_history[ip] = [t for t in request_history[ip] if current_time - t < window]
            else:
                request_history[ip] = []
                
            # Check if rate limit exceeded
            if len(request_history[ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {ip} [ID: {request.request_id}]")
                return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
                
            # Add current request
            request_history[ip].append(current_time)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/convert', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def convert_route() -> Tuple[Response, int]:
    """
    POST /convert endpoint expects JSON payload with 'source_path' and 'target_format'.
    Returns conversion result or error message.
    """
    try:
        start_time = time.time()
        data: Dict[str, Any] = request.get_json()
        
        if not data:
            logger.warning(f"Invalid JSON payload [ID: {request.request_id}]")
            return jsonify({"error": "Invalid JSON payload"}), 400
        
        # Extract and validate input parameters
        source_path = data.get('source_path')
        target_format = data.get('target_format', 'mp4')
        
        if not source_path:
            logger.warning(f"Missing required parameter: source_path [ID: {request.request_id}]")
            return jsonify({"error": "Missing required parameter: source_path"}), 400
            
        if target_format not in app.config['ALLOWED_FORMATS']:
            logger.warning(f"Invalid target format: {target_format} [ID: {request.request_id}]")
            return jsonify({
                "error": f"Invalid target format. Allowed formats: {', '.join(app.config['ALLOWED_FORMATS'])}"
            }), 400
        
        # Validate and sanitize source path
        is_valid, message = validate_media_source(source_path)
        if not is_valid:
            logger.warning(f"Validation failed: {message} [ID: {request.request_id}]")
            return jsonify({"error": message}), 400

        # Process the media conversion
        logger.info(f"Starting conversion of {source_path} to {target_format} [ID: {request.request_id}]")
        output_path = process_media(
            source_path,
            app.config['OUTPUT_DIR'],
            target_format,
            app.config['DOWNLOAD_DIR'],
            organize=True
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Conversion completed in {elapsed_time:.2f}s [ID: {request.request_id}]")
        
        # Return success response with file information
        return jsonify({
            "message": "Conversion successful",
            "output": output_path,
            "format": target_format,
            "processing_time": f"{elapsed_time:.2f}s"
        }), 200
        
    except Exception as e:
        # Log the full exception with traceback but return a sanitized message
        logger.error(
            f"Conversion failed: {str(e)} [ID: {request.request_id}]", 
            exc_info=True
        )
        return jsonify({
            "error": "An error occurred during conversion",
            "request_id": request.request_id
        }), 500

@app.route('/status', methods=['GET'])
def status_route() -> Tuple[Response, int]:
    """
    GET /status endpoint returns the current status of the conversion service.
    Used for health checking and monitoring.
    """
    return jsonify({
        "status": "operational",
        "version": "1.0.0",
        "output_dir": app.config['OUTPUT_DIR'],
        "download_dir": app.config['DOWNLOAD_DIR']
    }), 200

@app.errorhandler(Exception)
def handle_exception(e: Exception) -> Tuple[Response, int]:
    """Global exception handler for all unhandled exceptions."""
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
        
    # Log unexpected errors but don't expose internal details
    logger.error(f"Unhandled exception: {str(e)} [ID: {request.request_id}]", exc_info=True)
    
    return jsonify({
        "error": "An unexpected error occurred",
        "request_id": request.request_id
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting media conversion service on {host}:{port}")
    app.run(host=host, port=port) 