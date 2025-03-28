#!/usr/bin/env python3
"""
Web Interface for Universal Media Converter
"""

import os
import sys
import time
import json
import threading
import subprocess
import logging
import uuid
import re
import shutil
import psutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, abort
from werkzeug.utils import secure_filename
import platform
import traceback

# Import our utilities
from nzb4.utils.database import (
    init_db, save_job, get_job, get_all_jobs, get_active_jobs, 
    get_job_stats, cleanup_old_jobs, run_db_maintenance,
    get_setting, update_setting, get_all_settings
)
from nzb4.utils.notifications import notify, NOTIFICATION_TYPES
from nzb4.utils.docker_manager import is_docker_installed, is_docker_running, start_docker, install_docker, get_docker_status, ensure_docker_running
from nzb4.utils.n8n import N8nManager, is_n8n_installed, is_n8n_running, setup_n8n
from nzb4.utils.n8n.templates import SETUP_TEMPLATE, PROCESSING_TEMPLATE

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
COMPLETE_DIR = os.path.join(DATA_DIR, "complete")

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = os.path.join(UPLOADS_DIR, 'nzb')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'nzb', 'torrent'}
app.config['MIN_DISK_SPACE_MB'] = 500  # Minimum disk space required (MB)
app.jinja_env.add_extension('jinja2.ext.do')

# Thread safety for in-memory tracking
active_processes = {}  # Track running processes
active_processes_lock = threading.Lock()

# Job tracking dictionary: job_id -> {'status': 'pending'|'completed'|'failed', 'output': str}
jobs = {}

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def sanitize_input(input_str):
    """Sanitize user input to prevent command injection"""
    if not input_str:
        return ""
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[;&|`$><]', '', input_str)
    return sanitized.strip()

# Helper function to check for macOS platform
def is_macos():
    return platform.system() == 'Darwin'

def get_disk_space(path=DOWNLOADS_DIR):
    """Check available disk space"""
    try:
        stats = shutil.disk_usage(path)
        return stats.free // (1024 * 1024)  # Convert to MB
    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        return 0

def run_converter_job(job_id, media_source, media_type, output_format, keep_original):
    """Run media converter as a background process"""
    try:
        # Get job and update status
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found - cannot start")
            return
            
        job['status'] = 'running'
        save_job(job)
        
        # Send notification for job start
        notify('JOB_STARTED', job)
        
        # Check disk space
        min_disk_space = int(get_setting('min_disk_space_mb', str(app.config['MIN_DISK_SPACE_MB'])))
        free_mb = get_disk_space()
        if free_mb < min_disk_space:
            logger.error(f"Insufficient disk space ({free_mb}MB) to start job")
            job['status'] = 'failed'
            job['error'] = f"Insufficient disk space. Required: {min_disk_space}MB, Available: {free_mb}MB"
            job['end_time'] = time.time()
            save_job(job)
            
            # Send notification for failure
            notify('JOB_FAILED', job)
            return
        
        # Sanitize inputs
        sanitized_source = media_source
        if not os.path.exists(media_source):
            # If it's not a file path, sanitize it (search term or URL)
            sanitized_source = sanitize_input(media_source)
        
        # Get quality settings
        video_quality = get_setting('video_quality', 'high')
        quality_flags = []
        if video_quality == 'low':
            quality_flags = ["-q:v", "28", "-s", "854x480"]
        elif video_quality == 'medium':
            quality_flags = ["-q:v", "23", "-s", "1280x720"]
        elif video_quality == 'high':
            quality_flags = ["-q:v", "18", "-s", "1920x1080"]
        # original quality = no flags
        
        # Determine output directory based on media type
        if media_type == 'movie':
            output_dir = get_setting('movies_output_dir', os.path.join(COMPLETE_DIR, 'movies'))
        elif media_type == 'tv':
            output_dir = get_setting('tv_output_dir', os.path.join(COMPLETE_DIR, 'tv'))
        elif media_type == 'music':
            output_dir = get_setting('music_output_dir', os.path.join(COMPLETE_DIR, 'music'))
        else:
            output_dir = os.path.join(COMPLETE_DIR, 'other')
            
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # For testing: simulate a conversion job
        # In a real environment, we would call the actual converter script
        # but for testing, we'll just create a dummy output file and update status
        
        # Determine output file path
        filename = os.path.basename(sanitized_source)
        if not filename or len(filename) < 3:
            filename = f"output_{int(time.time())}.{output_format}"
        else:
            # Replace extension
            filename = f"{os.path.splitext(filename)[0]}.{output_format}"
        
        output_file = os.path.join(output_dir, filename)
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Log command (for real conversion, we would execute this)
        cmd = ["echo", f"Simulating conversion of {sanitized_source} to {output_file}"]
        
        # For testing: create a dummy output file
        with open(output_file, 'w') as f:
            f.write(f"Test conversion from {sanitized_source} with format {output_format}\n")
            f.write(f"Media type: {media_type}\n")
            f.write(f"Keep original: {keep_original}\n")
            f.write(f"Video quality: {video_quality}\n")
            f.write(f"Conversion time: {datetime.now().isoformat()}\n")
        
        # Run the command
        cmd_str = " ".join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
        job['cmd'] = cmd_str
        save_job(job)
        
        logger.info(f"Starting job {job_id}: {cmd_str}")
        
        # Update job with simulated output and progress
        outputs = [
            "Starting conversion process...",
            f"Source: {sanitized_source}",
            f"Output format: {output_format}",
            f"Media type: {media_type}",
            "Analyzing media source...",
            "Download progress: 20%",
            "Download progress: 40%",
            "Download progress: 60%",
            "Download progress: 80%",
            "Download progress: 100%",
            "Download complete",
            "Starting conversion...",
            "Converting: 25%",
            "Converting: 50%",
            "Converting: 75%",
            "Converting: 100%",
            "Processing complete",
            "Finalizing output file...",
            f"Output file: {output_file}",
            "Conversion successful"
        ]
        
        # Simulate progress over time
        job['output'] = []
        for line in outputs:
            # Update job with new output line
            job['output'].append(line)
            save_job(job)
            
            # Check if job was cancelled
            job = get_job(job_id)
            if job['status'] == 'cancelled':
                break
                
            # Sleep to simulate processing time
            time.sleep(0.5)
            
        # Complete the job
        if job['status'] != 'cancelled':
            job['status'] = 'completed'
            job['output_file'] = output_file
            job['end_time'] = time.time()
            job['return_code'] = 0
            save_job(job)
            
            # Send notification
            notify('JOB_COMPLETED', job)
        
        logger.info(f"Job {job_id} finished with status: {job['status']}")
        
        # Remove from active processes
        with active_processes_lock:
            if job_id in active_processes:
                del active_processes[job_id]
            
    except Exception as e:
        logger.exception(f"Error running converter job: {e}")
        
        # Get job for error update
        job = get_job(job_id)
        if job:
            job['status'] = 'failed'
            job['error'] = str(e)
            job['end_time'] = time.time()
            save_job(job)
            
            # Send failure notification
            notify('JOB_FAILED', job)
        
        # Cleanup in case of exception
        with active_processes_lock:
            if job_id in active_processes:
                try:
                    process = active_processes[job_id]
                    if process.poll() is None:
                        process.terminate()
                    del active_processes[job_id]
                except:
                    pass

def monitor_process_resources(job_id, pid):
    """Monitor resource usage of a process and terminate if excessive"""
    try:
        # Get resource limits from settings
        max_cpu_percent = int(get_setting('max_cpu_percent', '90'))
        max_memory_mb = int(get_setting('max_memory_mb', '1024'))  # 1GB default
        check_interval = int(get_setting('resource_check_interval', '10'))  # seconds
        
        while True:
            time.sleep(check_interval)
            
            # Get job for status check
            job = get_job(job_id)
            if not job or job['status'] not in ['running', 'pending']:
                return  # Job complete or cancelled
            
            try:
                process = psutil.Process(pid)
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                # Log resource usage
                logger.debug(f"Job {job_id} - CPU: {cpu_percent}%, Memory: {memory_mb}MB")
                
                # Update job with resource usage info
                job['cpu_percent'] = cpu_percent
                job['memory_mb'] = memory_mb
                save_job(job)
                
                # Check for excessive resource usage
                if cpu_percent > max_cpu_percent or memory_mb > max_memory_mb:
                    logger.warning(f"Job {job_id} exceeded resource limits - CPU: {cpu_percent}%, Memory: {memory_mb}MB")
                    
                    # Update job status
                    job['status'] = 'failed'
                    job['error'] = f"Process terminated - exceeded resource limits (CPU: {cpu_percent}%, Memory: {memory_mb}MB)"
                    job['end_time'] = time.time()
                    save_job(job)
                    
                    # Send notification
                    notify('JOB_FAILED', job)
                    
                    # Terminate the process
                    if process.is_running():
                        process.terminate()
                        with active_processes_lock:
                            if job_id in active_processes:
                                del active_processes[job_id]
                    return
            except psutil.NoSuchProcess:
                return  # Process no longer exists
            except Exception as e:
                logger.error(f"Error monitoring process {pid}: {e}")
                return
    except Exception as e:
        logger.error(f"Error in monitor thread: {e}")

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html', platform=platform.system())

@app.route('/api/convert', methods=['POST'])
def convert():
    """Start conversion job"""
    try:
        # Get form data
        media_source = request.form.get('media_source', '').strip()
        logger.debug(f"[DEBUG] Received media_source from form: '{media_source}'")
        media_type = request.form.get('media_type', get_setting('default_media_type', 'movie'))
        if media_type not in ['movie', 'tv', 'music', 'other']:
            return jsonify({'success': False, 'error': 'Invalid media type'}), 400
            
        output_format = request.form.get('output_format', get_setting('default_output_format', 'mp4'))
        if output_format not in ['mp4', 'mov', 'mkv', 'webm', 'avi']:
            return jsonify({'success': False, 'error': 'Invalid output format'}), 400
            
        keep_original = request.form.get('keep_original') == 'true' or get_setting('keep_original_default', 'false') == 'true'
        
        # Check disk space before proceeding
        min_disk_space = int(get_setting('min_disk_space_mb', str(app.config['MIN_DISK_SPACE_MB'])))
        free_mb = get_disk_space()
        if free_mb < min_disk_space:
            return jsonify({
                'success': False, 
                'error': f"Insufficient disk space. Required: {min_disk_space}MB, Available: {free_mb}MB"
            }), 400
        
        # Check active job count limit
        concurrent_limit = int(get_setting('concurrent_conversions', '2'))
        active_job_count = len(active_processes)
        if active_job_count >= concurrent_limit:
            return jsonify({
                'success': False,
                'error': f"Maximum concurrent conversion limit reached ({concurrent_limit}). Please try again later."
            }), 429  # Too Many Requests
        
        # Check if file was uploaded
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                if not allowed_file(file.filename):
                    return jsonify({'success': False, 'error': 'Invalid file type. Only .nzb and .torrent files are allowed'}), 400
                    
                # Determine file type and secure the filename
                _, ext = os.path.splitext(file.filename)
                upload_dir = os.path.join(UPLOADS_DIR, 'nzb' if ext.lower() == '.nzb' else 'torrents')
                
                # Create upload directory if it doesn't exist
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save file with a secure name
                filename = secure_filename(str(uuid.uuid4()) + ext)
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                
                # Use the file path as media source
                media_source = file_path
                logger.debug(f"[DEBUG] File uploaded, new media_source: '{media_source}'")
                
                # Check if file exists after saving
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    return jsonify({'success': False, 'error': 'Failed to save uploaded file'}), 500
        
        # If media_source is empty, try reading from JSON payload
        if not media_source:
            data = request.get_json(silent=True) or {}
            if 'media_source' in data:
                media_source = str(data['media_source']).strip()
                logger.debug(f"[DEBUG] Received media_source from JSON: {media_source}")

        # Log final media_source value before validation
        logger.debug(f"[DEBUG] Final media_source value: {media_source} (type: {type(media_source)})")
        logger.debug(f"[DEBUG] Final media_source repr: {repr(media_source)}")

        # Validate input
        if not media_source:
            logger.error("[DEBUG] media_source is empty after processing inputs!")
            return jsonify({'success': False, 'error': 'No media source provided'}), 400
            
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job
        job = {
            'id': job_id,
            'media_source': media_source,
            'media_type': media_type,
            'output_format': output_format,
            'keep_original': keep_original,
            'status': 'pending',
            'created_at': time.time(),
            'updated_at': time.time(),
            'output': [],
            'return_code': None,
            'output_file': None,
            'error': None,
            'hostname': request.remote_addr,
            'user_agent': request.user_agent.string if request.user_agent else 'Unknown'
        }
        
        # Log job details for debugging
        logger.debug(f"[DEBUG] Creating job with payload: {job}")

        # Save job to database
        if not save_job(job):
            return jsonify({'success': False, 'error': 'Failed to save job to database'}), 500
        
        # Mark job as active
        with active_processes_lock:
            active_processes[job_id] = True
        
        # Start job thread
        thread = threading.Thread(
            target=run_converter_job,
            args=(job_id, media_source, media_type, output_format, keep_original)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
        
    except Exception as e:
        logger.exception(f"Error starting conversion: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/job/<job_id>')
def get_job_api(job_id):
    """Get job status and output"""
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    return jsonify({'success': True, 'job': job})

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running job"""
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
        
    if job['status'] not in ['pending', 'running']:
        return jsonify({'success': False, 'error': 'Job cannot be cancelled in its current state'}), 400
    
    # Mark as cancelled
    job['status'] = 'cancelled'
    job['end_time'] = time.time()
    save_job(job)
    
    # Send notification
    notify('JOB_CANCELLED', job)
    
    # Remove from active processes
    with active_processes_lock:
        if job_id in active_processes:
            del active_processes[job_id]
    
    return jsonify({'success': True})

@app.route('/api/job/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Retry a failed job"""
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
        
    if job['status'] not in ['failed', 'cancelled']:
        return jsonify({'success': False, 'error': 'Only failed or cancelled jobs can be retried'}), 400
    
    # Create a new job with the same parameters
    new_job_id = str(uuid.uuid4())
    
    new_job = {
        'id': new_job_id,
        'media_source': job['media_source'],
        'media_type': job['media_type'],
        'output_format': job['output_format'],
        'keep_original': job['keep_original'],
        'status': 'pending',
        'created_at': time.time(),
        'updated_at': time.time(),
        'output': [],
        'return_code': None,
        'output_file': None,
        'error': None,
        'retried_from': job_id,
        'hostname': request.remote_addr,
        'user_agent': request.user_agent.string if request.user_agent else 'Unknown'
    }
    
    # Save new job
    if not save_job(new_job):
        return jsonify({'success': False, 'error': 'Failed to save new job to database'}), 500
    
    # Mark job as active
    with active_processes_lock:
        active_processes[new_job_id] = True
    
    # Start new job thread
    thread = threading.Thread(
        target=run_converter_job,
        args=(
            new_job_id, 
            new_job['media_source'], 
            new_job['media_type'], 
            new_job['output_format'], 
            new_job['keep_original']
        )
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': new_job_id})

@app.route('/api/jobs')
def get_jobs_api():
    """Get all jobs"""
    # Get limit parameter from query string
    try:
        limit = int(request.args.get('limit', get_setting('jobs_per_page', '20')))
        # Cap limit at a reasonable value
        limit = min(limit, 500)
    except ValueError:
        limit = int(get_setting('jobs_per_page', '20'))
        
    jobs = get_all_jobs(limit)
    return jsonify({'success': True, 'jobs': jobs})

@app.route('/api/status')
def get_status_api():
    """Get system status information"""
    try:
        # Get output directories
        movies_dir = get_setting('movies_output_dir', os.path.join(COMPLETE_DIR, 'movies'))
        tv_dir = get_setting('tv_output_dir', os.path.join(COMPLETE_DIR, 'tv'))
        music_dir = get_setting('music_output_dir', os.path.join(COMPLETE_DIR, 'music'))
        
        # Check disk space for each directory
        disk_spaces = {
            'downloads': get_disk_space(DOWNLOADS_DIR),
            'movies': get_disk_space(movies_dir),
            'tv': get_disk_space(tv_dir),
            'music': get_disk_space(music_dir)
        }
        
        # Get total disk space for the main data directory
        disk_total = shutil.disk_usage(DATA_DIR).total // (1024 * 1024)
        
        # Get job stats from database
        job_stats = get_job_stats()
        
        # Get system stats
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_used_percent = memory.percent
        
        # Get current settings
        settings_summary = {
            'max_concurrent': get_setting('concurrent_conversions', '2'),
            'default_format': get_setting('default_output_format', 'mp4'),
            'video_quality': get_setting('video_quality', 'high'),
            'min_disk_space_mb': get_setting('min_disk_space_mb', str(app.config['MIN_DISK_SPACE_MB']))
        }
        
        status = {
            'disk': {
                'free_mb': disk_spaces['downloads'],
                'total_mb': disk_total,
                'used_percent': ((disk_total - disk_spaces['downloads']) / disk_total) * 100 if disk_total > 0 else 0,
                'directories': disk_spaces
            },
            'jobs': job_stats,
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_used_percent,
                'time': datetime.now().isoformat()
            },
            'settings': settings_summary
        }
        
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.exception(f"Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/maintenance', methods=['POST'])
def run_maintenance():
    """Run maintenance tasks"""
    try:
        # Check if we should clean temporary files
        auto_cleanup = get_setting('auto_cleanup_temp', 'false').lower() == 'true'
        
        # Run database maintenance
        db_result = run_db_maintenance()
        
        # Initialize result with database maintenance results
        result = db_result
        
        # Clean temporary files if enabled
        if auto_cleanup:
            # Clean temporary download directories
            temp_dirs = [os.path.join(DOWNLOADS_DIR, 'temp'), os.path.join(DOWNLOADS_DIR, 'incomplete')]
            files_cleaned = 0
            
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                                files_cleaned += 1
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                                files_cleaned += 1
                        except Exception as e:
                            logger.error(f"Error cleaning temporary file {file_path}: {e}")
            
            # Add temp file cleanup results
            result['temp_files_cleaned'] = files_cleaned
        else:
            result['temp_files_cleaned'] = 0
            
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.exception(f"Error running maintenance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def get_settings_api():
    """Get all settings"""
    try:
        settings = get_all_settings()
        # Filter out sensitive settings
        sensitive_keys = ['smtp_password', 'webhook_headers']
        for key in sensitive_keys:
            if key in settings:
                settings[key] = '********' if settings[key] else ''
        
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        logger.exception(f"Error getting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings_api():
    """Update settings"""
    try:
        settings_data = request.json
        if not settings_data:
            return jsonify({'success': False, 'error': 'No settings provided'}), 400
            
        updated = []
        
        for key, value in settings_data.items():
            # Skip if value is masked
            if value == '********':
                continue
                
            # Convert boolean values to strings
            if isinstance(value, bool):
                value = 'true' if value else 'false'
                
            # Update setting
            if update_setting(key, value):
                updated.append(key)
                
        return jsonify({'success': True, 'updated': updated})
    except Exception as e:
        logger.exception(f"Error updating settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/email', methods=['POST'])
def test_email():
    """Send a test email notification"""
    try:
        # Create test data
        test_data = {
            'id': 'test-' + str(uuid.uuid4()),
            'media_source': 'Test Media Source',
            'media_type': 'test',
            'created_at': time.time(),
            'status': 'Test'
        }
        
        # Send notification
        result = notify('JOB_COMPLETED', test_data)
        
        if result.get('email'):
            return jsonify({'success': True, 'message': 'Test email sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send test email. Check SMTP settings.'})
    except Exception as e:
        logger.exception(f"Error sending test email: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/webhook', methods=['POST'])
def test_webhook():
    """Send a test webhook notification"""
    try:
        # Create test data
        test_data = {
            'id': 'test-' + str(uuid.uuid4()),
            'media_source': 'Test Media Source',
            'media_type': 'test',
            'created_at': time.time(),
            'status': 'Test'
        }
        
        # Send notification
        result = notify('JOB_COMPLETED', test_data)
        
        if result.get('webhook'):
            return jsonify({'success': True, 'message': 'Test webhook sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send test webhook. Check webhook settings.'})
    except Exception as e:
        logger.exception(f"Error sending test webhook: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/uploads/<path:filename>')
def download_file(filename):
    """Allow downloads from the complete directories"""
    # Security check - prevent path traversal
    if '..' in filename or filename.startswith('/'):
        abort(404)
    
    # Get configured output directories
    movies_dir = get_setting('movies_output_dir', os.path.join(COMPLETE_DIR, 'movies'))
    tv_dir = get_setting('tv_output_dir', os.path.join(COMPLETE_DIR, 'tv'))
    music_dir = get_setting('music_output_dir', os.path.join(COMPLETE_DIR, 'music'))
    other_dir = os.path.join(COMPLETE_DIR, 'other')
    
    # Check which directory the file might be in
    base_dirs = [movies_dir, tv_dir, music_dir, other_dir]
    
    for base_dir in base_dirs:
        file_path = os.path.join(base_dir, filename)
        
        # Normalize paths to prevent path traversal attacks
        real_base_dir = os.path.realpath(base_dir)
        real_file_path = os.path.realpath(file_path)
        
        # Check if the file is within the allowed directory
        if real_file_path.startswith(real_base_dir) and os.path.isfile(real_file_path):
            # Get directory and filename components
            directory = os.path.dirname(real_file_path)
            basename = os.path.basename(real_file_path)
            
            return send_from_directory(directory, basename, as_attachment=True)
    
    # If file not found in any allowed directory
    logger.warning(f"Attempted access to file not found: {filename}")
    abort(404)

@app.route('/job/<job_id>')
def job_status(job_id):
    """Job status page"""
    if not get_job(job_id):
        return redirect(url_for('index'))
    
    return render_template('job.html', job_id=job_id)

@app.route('/status')
def status_page():
    """System status page"""
    docker_status = get_docker_status() if is_macos() else {"installed": False, "running": False}
    return render_template('status.html', docker_status=docker_status)

@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template('settings.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup_interface():
    if request.method == 'POST':
        # Get user inputs
        media_dir = request.form.get('media_dir')
        output_format = request.form.get('output_format')
        video_quality = request.form.get('video_quality')
        
        # Update settings
        update_setting('media_dir', media_dir)
        update_setting('default_output_format', output_format)
        update_setting('video_quality', video_quality)
        
        # Create directories if they don't exist
        if media_dir:
            os.makedirs(media_dir, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(COMPLETE_DIR, exist_ok=True)
        
        return redirect(url_for('index'))
    
    # Check Docker status for macOS
    docker_status = get_docker_status() if is_macos() else None
    
    # Render setup page
    return render_template('setup.html', settings=get_all_settings(), docker_status=docker_status)

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        'success': False, 
        'error': f'File too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)}MB'
    }), 413

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return render_template('error.html', error='Server error occurred'), 500

def setup_default_settings():
    """Setup default settings if not already configured"""
    try:
        # Only initialize if settings don't exist 
        if get_setting('setup_completed') != 'true':
            logger.info("Setting up default configuration")
            
            # Add n8n default settings
            update_setting("n8n_data_dir", os.path.expanduser("~/n8n-data"))
            update_setting("n8n_port", "5678")
            update_setting("n8n_install_type", "docker")
            update_setting("n8n_health_check_interval", "300")
            
            # Add all setup code above this line
            
            # Mark setup as completed
            update_setting('setup_completed', 'true')
            logger.info("Default settings configuration completed")
    except Exception as e:
        logger.error(f"Error setting up default configuration: {e}")
    finally:
        logger.debug("Finished setup_default_settings function")

@app.route('/n8n/setup', methods=['GET', 'POST'])
def n8n_setup():
    """n8n setup page"""
    # Initialize n8n manager
    n8n = N8nManager()
    
    if request.method == 'POST':
        # Get form data
        data_dir = request.form.get('n8n_data_dir', os.path.expanduser("~/n8n-data"))
        port = int(request.form.get('n8n_port', "5678"))
        install_type = request.form.get('n8n_install_type', "docker")
        action = request.form.get('action')
        
        # Save settings
        update_setting("n8n_data_dir", data_dir)
        update_setting("n8n_port", str(port))
        update_setting("n8n_install_type", install_type)
        
        # Create n8n with updated settings
        n8n = N8nManager(data_dir)
        
        # Handle requested action
        if action == 'install':
            threading.Thread(target=n8n.install, 
                            args=(install_type == 'docker',), 
                            daemon=True).start()
            
            # Render processing page
            return render_template_string(
                PROCESSING_TEMPLATE,
                title="Installing n8n",
                message="Installing n8n workflow automation. This may take a few minutes...",
                redirect_url=url_for('n8n_setup')
            )
            
        elif action == 'start':
            threading.Thread(target=n8n.start, daemon=True).start()
            
            # Render processing page
            return render_template_string(
                PROCESSING_TEMPLATE,
                title="Starting n8n",
                message="Starting n8n workflow automation...",
                redirect_url=url_for('n8n_setup')
            )
            
        elif action == 'stop':
            threading.Thread(target=n8n.stop, daemon=True).start()
            
            # Render processing page
            return render_template_string(
                PROCESSING_TEMPLATE,
                title="Stopping n8n",
                message="Stopping n8n workflow automation...",
                redirect_url=url_for('n8n_setup')
            )
            
        elif action == 'uninstall':
            threading.Thread(target=n8n.uninstall, daemon=True).start()
            
            # Render processing page
            return render_template_string(
                PROCESSING_TEMPLATE,
                title="Uninstalling n8n",
                message="Uninstalling n8n workflow automation...",
                redirect_url=url_for('n8n_setup')
            )
            
        elif action == 'open':
            # Redirect to n8n web interface
            return redirect(f"http://localhost:{port}")
        
        # Redirect back to setup page for GET
        return redirect(url_for('n8n_setup'))
    
    # Get n8n status
    status = n8n.get_status()
    
    # Prepare template variables
    template_vars = {
        "is_installed": status["installed"],
        "installed_status": "Installed" if status["installed"] else "Not installed",
        "installed_class": "status-on" if status["installed"] else "status-off",
        "is_running": status["running"],
        "running_status": "Running" if status["running"] else "Stopped",
        "running_class": "status-on" if status["running"] else "status-off",
        "version": status.get("version", "Unknown"),
        "url": status["url"],
        "data_dir": status["data_dir"],
        "port": status["port"],
        "install_type": status["install_type"],
        "status_class": "status-success" if status["running"] else 
                        "status-warning" if status["installed"] else
                        "status-error"
    }
    
    # Render setup page
    return render_template_string(SETUP_TEMPLATE, **template_vars)

@app.route('/api/n8n/status')
def n8n_status_api():
    """Get n8n status"""
    n8n = N8nManager()
    return jsonify(n8n.get_status())

@app.route('/api/n8n/install', methods=['POST'])
def n8n_install_api():
    """Install n8n"""
    data_dir = request.json.get('data_dir', os.path.expanduser("~/n8n-data"))
    port = int(request.json.get('port', 5678))
    use_docker = request.json.get('use_docker', True)
    
    # Update settings
    update_setting("n8n_data_dir", data_dir)
    update_setting("n8n_port", str(port))
    update_setting("n8n_install_type", "docker" if use_docker else "npm")
    
    # Run in background thread
    def install_thread():
        n8n = N8nManager(data_dir)
        success = n8n.install(use_docker)
        if success:
            n8n.start()
    
    threading.Thread(target=install_thread, daemon=True).start()
    
    return jsonify({"success": True, "message": "n8n installation started"})

@app.route('/api/n8n/start', methods=['POST'])
def n8n_start_api():
    """Start n8n"""
    n8n = N8nManager()
    threading.Thread(target=n8n.start, daemon=True).start()
    return jsonify({"success": True, "message": "n8n start initiated"})

@app.route('/api/n8n/stop', methods=['POST'])
def n8n_stop_api():
    """Stop n8n"""
    n8n = N8nManager()
    threading.Thread(target=n8n.stop, daemon=True).start()
    return jsonify({"success": True, "message": "n8n stop initiated"})

# Schedule periodic cleanup
def run_scheduled_cleanup():
    """Run periodic maintenance tasks"""
    try:
        while True:
            # Get maintenance interval from settings
            try:
                maintenance_interval = int(get_setting('maintenance_interval_hours', '24'))
            except (ValueError, TypeError):
                maintenance_interval = 24
            
            # Convert to seconds
            sleep_time = maintenance_interval * 3600
            
            time.sleep(sleep_time)  # Wait for the configured interval
            
            try:
                result = run_db_maintenance()
                logger.info(f"Scheduled maintenance completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled maintenance: {e}")
    except Exception as e:
        logger.error(f"Error in scheduled maintenance: {e}")

def recover_active_jobs():
    """Recover active jobs from the database after a restart"""
    try:
        # Get all active jobs
        active_jobs = get_active_jobs()
        
        if active_jobs:
            logger.info(f"Found {len(active_jobs)} active jobs to recover")
            
            for job in active_jobs:
                # Mark jobs as failed with restart message
                job['status'] = 'failed'
                job['error'] = 'Job was interrupted by system restart'
                job['end_time'] = time.time()
                save_job(job)
                
                # Send notification
                notify('JOB_FAILED', job)
                
            logger.info("All interrupted jobs have been marked as failed")
    except Exception as e:
        logger.error(f"Error recovering active jobs: {e}")

@app.route('/docker', methods=['GET', 'POST'])
def docker_management():
    """Docker management page"""
    if not is_macos():
        return render_template('error.html', error='Docker management is only supported on macOS')
    
    # Handle actions
    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'start':
            if start_docker():
                message = {'type': 'success', 'text': 'Docker started successfully'}
            else:
                message = {'type': 'error', 'text': 'Failed to start Docker'}
        elif action == 'install':
            if install_docker():
                message = {'type': 'success', 'text': 'Docker installed successfully'}
            else:
                message = {'type': 'error', 'text': 'Failed to install Docker. See logs for details.'}
    
    # Get current status
    docker_status = get_docker_status()
    
    return render_template('docker.html', docker_status=docker_status, message=message)

@app.route('/api/docker/status')
def docker_status_api():
    """API endpoint for Docker status"""
    if not is_macos():
        return jsonify({'success': False, 'error': 'Docker status is only available on macOS'})
    
    return jsonify({'success': True, 'status': get_docker_status()})

@app.route('/api/docker/start', methods=['POST'])
def docker_start_api():
    """API endpoint to start Docker"""
    if not is_macos():
        return jsonify({'success': False, 'error': 'Docker management is only supported on macOS'})
    
    if not is_docker_installed():
        return jsonify({'success': False, 'error': 'Docker is not installed'})
    
    if is_docker_running():
        return jsonify({'success': True, 'message': 'Docker is already running'})
    
    if start_docker():
        return jsonify({'success': True, 'message': 'Docker started successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to start Docker'})
        
@app.route('/api/docker/install', methods=['POST'])
def docker_install_api():
    """API endpoint to install Docker"""
    if not is_macos():
        return jsonify({'success': False, 'error': 'Docker installation is only supported on macOS'})
    
    if is_docker_installed():
        return jsonify({'success': True, 'message': 'Docker is already installed'})
    
    if install_docker():
        return jsonify({'success': True, 'message': 'Docker installed successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to install Docker'})

def setup_directories():
    """Create necessary directories for the application"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        os.makedirs(os.path.join(UPLOADS_DIR, 'nzb'), exist_ok=True)
        os.makedirs(os.path.join(UPLOADS_DIR, 'torrents'), exist_ok=True)
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(os.path.join(DOWNLOADS_DIR, 'temp'), exist_ok=True)
        os.makedirs(os.path.join(DOWNLOADS_DIR, 'incomplete'), exist_ok=True)
        os.makedirs(COMPLETE_DIR, exist_ok=True)
        os.makedirs(os.path.join(COMPLETE_DIR, 'movies'), exist_ok=True)
        os.makedirs(os.path.join(COMPLETE_DIR, 'tv'), exist_ok=True)
        os.makedirs(os.path.join(COMPLETE_DIR, 'music'), exist_ok=True)
        os.makedirs(os.path.join(COMPLETE_DIR, 'other'), exist_ok=True)
        logger.debug("All required directories created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating directories: {e}")
        return False

if __name__ == '__main__':
    try:
        # Create required directories
        if not setup_directories():
            print("Failed to create required directories. Check permissions and try again.")
            sys.exit(1)
        
        # Initialize database
        init_db()
        
        # Set up default settings
        setup_default_settings()
        
        # Check for Docker on macOS
        if is_macos():
            docker_status = get_docker_status()
            if not docker_status['installed']:
                print("\nDocker is not installed. Docker is recommended for running the media converter.")
                print("You can install Docker from the setup page after starting the application.")
            elif not docker_status['running']:
                print("\nDocker is installed but not running.")
                response = input("Would you like to start Docker now? (y/n): ")
                if response.lower() in ('y', 'yes'):
                    if start_docker():
                        print("Docker started successfully.")
                    else:
                        print("Failed to start Docker. You can start it from the Docker management page.")
        
        # Recover active jobs
        recover_active_jobs()
        
        # Log system startup notification
        startup_info = {
            'hostname': os.uname().nodename,
            'timestamp': datetime.now().isoformat(),
            'python_version': sys.version
        }
        notify('SYSTEM_STARTUP', startup_info)
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=run_scheduled_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # Check disk space on startup
        min_disk_space = int(get_setting('min_disk_space_mb', str(app.config['MIN_DISK_SPACE_MB'])))
        free_mb = get_disk_space()
        logger.info(f"Available disk space: {free_mb}MB")
        
        if free_mb < min_disk_space:
            logger.warning(f"Low disk space on startup: {free_mb}MB available")
            # Send low disk space notification
            disk_info = {
                'free_mb': free_mb,
                'required_mb': min_disk_space,
                'hostname': os.uname().nodename,
                'timestamp': datetime.now().isoformat()
            }
            notify('DISK_SPACE_LOW', disk_info)
        
        # Print startup message
        print("\nStarting Universal Media Converter...")
        print(f"Open your browser and go to: http://localhost:8000")
        print("Press Ctrl+C to stop the server")
        
        # Start the app
        logger.info("Starting Universal Media Converter web interface")
        app.run(host='0.0.0.0', port=8000, debug=True)
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        # Send system error notification
        error_info = {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'hostname': os.uname().nodename,
            'timestamp': datetime.now().isoformat()
        }
        notify('SYSTEM_ERROR', error_info)
        sys.exit(1) 