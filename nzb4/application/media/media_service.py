#!/usr/bin/env python3
"""
Application service for media handling.
Implements the application layer logic for media operations.
"""

import os
import threading
import logging
import shutil
import time
from typing import List, Dict, Any, Optional, Union, Tuple
from uuid import UUID
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

from nzb4.domain.media.entities import (
    Media, ConversionJob, MediaType, MediaSource, 
    ConversionStatus, OutputFormat, VideoQuality, ConversionOptions, MediaMetadata
)
from nzb4.domain.media.services import (
    MediaService, MediaDetectionService, MediaDownloadService,
    MediaConversionService, MediaOrganizationService
)
from nzb4.domain.media.repositories import MediaRepository, ConversionJobRepository
from nzb4.domain.media.queries import (
    MediaByIdQuery, MediaByStatusQuery, MediaByTypeQuery, MediaSearchQuery,
    JobByIdQuery, JobsByMediaIdQuery, ActiveJobsQuery, CompletedJobsQuery,
    FailedJobsQuery, DiskSpaceQuery
)
from nzb4.config.settings import config
from nzb4.application.media.security import SecurityValidator, ResourceMonitor

# Set up logging
logger = logging.getLogger(__name__)


class MediaApplicationService:
    """
    Application service for media handling.
    This class orchestrates all media-related operations, providing a clean API
    for the web interface and other consumers.
    """
    
    def __init__(
        self,
        media_service: MediaService,
        media_repo: MediaRepository,
        job_repo: ConversionJobRepository,
        detector: MediaDetectionService,
        downloader: MediaDownloadService,
        converter: MediaConversionService,
        organizer: MediaOrganizationService
    ):
        self.media_service = media_service
        self.media_repo = media_repo
        self.job_repo = job_repo
        self.detector = detector
        self.downloader = downloader
        self.converter = converter
        self.organizer = organizer
        
        # Map to track active job worker threads
        self._job_workers = {}
        self._job_locks = {}
        
        # Ensure required directories exist
        self._ensure_directories()
        
        # Start background processing thread for pending jobs
        self._start_job_processor()
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        directories = [
            config.media.download_dir,
            config.media.complete_dir,
            config.media.movies_dir,
            config.media.tv_dir,
            config.media.music_dir,
            config.media.other_dir,
            config.temp_dir
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def _start_job_processor(self) -> None:
        """Start background thread to process pending jobs"""
        processor_thread = threading.Thread(
            target=self._process_pending_jobs,
            daemon=True,
            name="MediaJobProcessor"
        )
        processor_thread.start()
    
    def _process_pending_jobs(self) -> None:
        """Process pending jobs in a loop"""
        while True:
            try:
                # Check for disk space before processing any jobs
                has_space, space_info = ResourceMonitor.check_disk_space()
                if not has_space:
                    logger.warning(f"Low disk space: {space_info.get('free_mb', 0):.2f} MB free. Pausing job processing.")
                    time.sleep(60)  # Check again in a minute
                    continue
                
                # Check if system is overloaded
                if ResourceMonitor.should_throttle():
                    logger.warning("System resources are low. Throttling job processing.")
                    time.sleep(30)  # Wait before checking again
                    continue
                
                # Get pending jobs
                pending_jobs = self.job_repo.get_by_status(
                    ConversionStatus.PENDING, 
                    limit=config.media.concurrent_conversions
                )
                
                # Start a worker thread for each pending job
                for job in pending_jobs:
                    if job.id not in self._job_workers or not self._job_workers[job.id].is_alive():
                        # Acquire lock for this job
                        self._job_locks[job.id] = threading.Lock()
                        
                        # Start worker thread
                        worker = threading.Thread(
                            target=self._process_job,
                            args=(job.id,),
                            daemon=True,
                            name=f"JobWorker-{job.id}"
                        )
                        self._job_workers[job.id] = worker
                        worker.start()
            
            except Exception as e:
                logger.error(f"Error in job processor: {e}")
            
            # Sleep for a few seconds before checking for more jobs
            time.sleep(5)
    
    def _check_disk_space(self) -> bool:
        """
        Check if there's enough disk space for processing
        
        Returns:
            bool: True if enough space, False otherwise
        """
        has_space, _ = ResourceMonitor.check_disk_space()
        return has_space
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal and command injection
        
        Args:
            filename: The filename to sanitize
            
        Returns:
            str: Sanitized filename
        """
        return SecurityValidator.sanitize_filename(filename)
    
    def _process_job(self, job_id: str) -> None:
        """
        Process a job in a separate thread
        
        Args:
            job_id: ID of the job to process
        """
        job = self.job_repo.get_by_id(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        
        media = self.media_repo.get_by_id(job.media_id)
        if not media:
            logger.error(f"Media not found for job: {job_id}")
            job.fail("Media not found")
            self.job_repo.save(job)
            return
        
        try:
            # Start job
            with self._job_locks.get(job_id, threading.Lock()):
                job.start()
                self.job_repo.save(job)
                
                # Download phase
                media.update_status(ConversionStatus.DOWNLOADING)
                self.media_repo.save(media)
                
                # Prepare download path
                safe_filename = self._sanitize_filename(os.path.basename(media.source))
                download_dir = SecurityValidator.create_safe_directory(config.media.download_dir, media.id)
                downloaded_path = os.path.join(download_dir, safe_filename)
                
                # Validate the final path to ensure no traversal
                is_valid, error = SecurityValidator.validate_filepath(downloaded_path, config.media.download_dir)
                if not is_valid:
                    raise ValueError(f"Invalid download path: {error}")
                
                # Download
                logger.info(f"Downloading {media.source} to {downloaded_path}")
                if not self.downloader.download(media, downloaded_path):
                    raise Exception("Download failed")
                
                # Validate downloaded file
                is_valid, error = SecurityValidator.validate_file_type(downloaded_path)
                if not is_valid:
                    raise ValueError(f"Invalid file: {error}")
                
                media.downloaded_path = downloaded_path
                self.media_repo.save(media)
                
                # Processing phase
                media.update_status(ConversionStatus.PROCESSING)
                self.media_repo.save(media)
                
                # Extract metadata
                try:
                    metadata_dict = self.detector.extract_metadata(
                        downloaded_path, media.media_type
                    )
                    media.metadata = MediaMetadata(**metadata_dict)
                    self.media_repo.save(media)
                except Exception as e:
                    logger.warning(f"Metadata extraction failed: {e}")
                
                # Conversion phase
                media.update_status(ConversionStatus.CONVERTING)
                self.media_repo.save(media)
                
                # Prepare output path
                output_ext = job.options.output_format.name.lower()
                output_filename = f"{safe_filename.split('.')[0]}.{output_ext}"
                temp_output_path = os.path.join(config.temp_dir, output_filename)
                
                # Validate the temp output path
                is_valid, error = SecurityValidator.validate_filepath(temp_output_path, config.temp_dir)
                if not is_valid:
                    raise ValueError(f"Invalid temp output path: {error}")
                
                # Convert
                logger.info(f"Converting {downloaded_path} to {temp_output_path}")
                job.add_log(f"Starting conversion to {output_ext.upper()}")
                if not self.converter.convert(media, job.options):
                    raise Exception("Conversion failed")
                
                # Organization phase
                media.update_status(ConversionStatus.ORGANIZING)
                self.media_repo.save(media)
                
                # Determine final path
                if job.options.organize_media:
                    media.output_path = self.organizer.organize(media, config.media.complete_dir)
                else:
                    # Just move to complete directory if not organizing
                    media.output_path = os.path.join(config.media.complete_dir, output_filename)
                    
                    # Validate the final output path
                    is_valid, error = SecurityValidator.validate_filepath(media.output_path, config.media.complete_dir)
                    if not is_valid:
                        raise ValueError(f"Invalid output path: {error}")
                        
                    shutil.move(temp_output_path, media.output_path)
                
                # Calculate file hash for integrity verification
                try:
                    file_hash = SecurityValidator.calculate_file_hash(media.output_path)
                    media.metadata.custom_metadata["file_hash"] = file_hash
                    media.metadata.custom_metadata["hash_algorithm"] = "sha256"
                except Exception as e:
                    logger.warning(f"Failed to calculate file hash: {e}")
                
                # Update media with final path
                self.media_repo.save(media)
                
                # Cleanup if needed
                if not job.options.keep_original and os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
                
                # Complete job
                media.update_status(ConversionStatus.COMPLETED)
                self.media_repo.save(media)
                
                job.complete()
                job.add_log(f"Completed! Output at: {media.output_path}")
                self.job_repo.save(job)
                
                logger.info(f"Job {job_id} completed successfully")
        
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            
            error_message = str(e)
            
            # Update job and media status
            with self._job_locks.get(job_id, threading.Lock()):
                media.update_status(ConversionStatus.FAILED, error_message)
                self.media_repo.save(media)
                
                job.fail(error_message)
                job.add_log(f"Error: {error_message}")
                self.job_repo.save(job)
    
    def submit_job(self, source: str, options_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a new media conversion job
        
        Args:
            source: Media source (URL, file path, etc.)
            options_dict: Conversion options
            
        Returns:
            Dict: Job information
        """
        try:
            # Validate source
            if not source:
                return {"error": "Empty source provided"}
            
            # Validate source based on type
            source_type = MediaSource.detect_from_string(source)
            
            if source_type == MediaSource.LOCAL_FILE:
                # Validate local file path
                is_valid, error = SecurityValidator.validate_filepath(source)
                if not is_valid:
                    return {"error": f"Invalid file path: {error}"}
                    
                if not os.path.exists(source):
                    return {"error": f"Local file not found: {source}"}
                    
            elif source_type == MediaSource.DIRECT_URL:
                # Validate URL
                is_valid, error = SecurityValidator.validate_url(source)
                if not is_valid:
                    return {"error": f"Invalid URL: {error}"}
            
            # Check system resources before accepting the job
            if ResourceMonitor.should_throttle():
                return {"error": "System is currently overloaded. Please try again later."}
            
            # Convert options dict to ConversionOptions
            options = self._dict_to_conversion_options(options_dict)
            
            # Process media
            job_id = self.media_service.process_media(source, options)
            
            # Get created job
            job = self.job_repo.get_by_id(job_id)
            if not job:
                return {"error": "Failed to create job"}
            
            # Return job info
            return {
                "job_id": job_id,
                "status": "pending",
                "message": "Job submitted successfully"
            }
        
        except Exception as e:
            logger.error(f"Error submitting job: {e}", exc_info=True)
            return {"error": str(e)}
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """
        Get job information
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dict: Job information
        """
        try:
            return self.media_service.get_job_status(job_id)
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return {"error": str(e)}
    
    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """
        Cancel a job
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            Dict: Result information
        """
        try:
            result = self.media_service.cancel_job(job_id)
            if result:
                return {"success": True, "message": "Job cancelled successfully"}
            else:
                return {"success": False, "error": "Failed to cancel job"}
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_active_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get active jobs
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List[Dict]: List of active job information
        """
        try:
            return self.media_service.get_active_jobs(limit)
        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")
            return []
    
    def get_job_history(self, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get job history with pagination
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Tuple[List[Dict], int]: List of job information and total count
        """
        try:
            # Sanitize input
            page = max(1, page)
            page_size = min(100, max(1, page_size))  # Limit page size between 1 and 100
            
            offset = (page - 1) * page_size
            jobs = self.job_repo.get_all(limit=page_size, offset=offset)
            total = len(self.job_repo.get_all())
            
            result = []
            for job in jobs:
                media = self.media_repo.get_by_id(job.media_id)
                if not media:
                    continue
                
                result.append({
                    "id": job.id,
                    "status": job.status.name,
                    "created_at": job.created_at.isoformat(),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "media": {
                        "id": media.id,
                        "source": media.source,
                        "type": media.media_type.name,
                        "title": media.metadata.title if media.metadata else None,
                        "output_path": media.output_path
                    }
                })
            
            return result, total
        
        except Exception as e:
            logger.error(f"Error getting job history: {e}")
            return [], 0
    
    def get_job_logs(self, job_id: str) -> List[str]:
        """
        Get logs for a job
        
        Args:
            job_id: ID of the job
            
        Returns:
            List[str]: Job logs
        """
        try:
            job = self.job_repo.get_by_id(job_id)
            if not job:
                return []
            
            return job.output_log
        
        except Exception as e:
            logger.error(f"Error getting logs for job {job_id}: {e}")
            return []
    
    def get_disk_space_info(self) -> Dict[str, Any]:
        """
        Get disk space information
        
        Returns:
            Dict: Disk space information
        """
        try:
            info = {}
            
            # Check download directory
            _, download_info = ResourceMonitor.check_disk_space(config.media.download_dir)
            if "error" not in download_info:
                info["download_dir"] = {
                    "path": config.media.download_dir,
                    "total_gb": download_info["total_mb"] / 1024,
                    "used_gb": download_info["used_mb"] / 1024,
                    "free_gb": download_info["free_mb"] / 1024,
                    "percent_used": download_info["percent_used"]
                }
            
            # Check complete directory
            _, complete_info = ResourceMonitor.check_disk_space(config.media.complete_dir)
            if "error" not in complete_info:
                info["complete_dir"] = {
                    "path": config.media.complete_dir,
                    "total_gb": complete_info["total_mb"] / 1024,
                    "used_gb": complete_info["used_mb"] / 1024,
                    "free_gb": complete_info["free_mb"] / 1024,
                    "percent_used": complete_info["percent_used"]
                }
            
            # Check temp directory
            _, temp_info = ResourceMonitor.check_disk_space(config.temp_dir)
            if "error" not in temp_info:
                info["temp_dir"] = {
                    "path": config.temp_dir,
                    "total_gb": temp_info["total_mb"] / 1024,
                    "used_gb": temp_info["used_mb"] / 1024,
                    "free_gb": temp_info["free_gb"] / 1024,
                    "percent_used": temp_info["percent_used"]
                }
            
            # Warning flags
            info["warnings"] = {
                "download_dir_low": info.get("download_dir", {}).get("free_gb", 0) < (config.media.min_disk_space_mb / 1024),
                "complete_dir_low": info.get("complete_dir", {}).get("free_gb", 0) < (config.media.min_disk_space_mb / 1024),
                "temp_dir_low": info.get("temp_dir", {}).get("free_gb", 0) < (config.media.min_disk_space_mb / 1024)
            }
            
            # Add system resource information
            info["system"] = ResourceMonitor.check_system_resources()
            
            return info
        
        except Exception as e:
            logger.error(f"Error getting disk space info: {e}")
            return {"error": str(e)}
    
    def get_conversion_formats(self, media_type: Union[str, MediaType]) -> List[str]:
        """
        Get available conversion formats for a media type
        
        Args:
            media_type: Media type
            
        Returns:
            List[str]: Available formats
        """
        try:
            if isinstance(media_type, str):
                media_type = MediaType.from_string(media_type)
            
            formats = self.converter.get_available_formats(media_type)
            return [f.name for f in formats]
        
        except Exception as e:
            logger.error(f"Error getting conversion formats: {e}")
            return []
    
    def search_media(self, keyword: str, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search for media
        
        Args:
            keyword: Search keyword
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Tuple[List[Dict], int]: List of media information and total count
        """
        try:
            # Sanitize input
            page = max(1, page)
            page_size = min(100, max(1, page_size))  # Limit page size between 1 and 100
            
            # Sanitize keyword to prevent injection
            keyword = re.sub(r'[;\'\"<>]', '', keyword)
            
            offset = (page - 1) * page_size
            media_list = self.media_repo.search(keyword, limit=page_size, offset=offset)
            total = len(self.media_repo.search(keyword))
            
            result = []
            for media in media_list:
                result.append({
                    "id": media.id,
                    "source": media.source,
                    "type": media.media_type.name,
                    "status": media.status.name,
                    "title": media.metadata.title if media.metadata else None,
                    "year": media.metadata.year if media.metadata else None,
                    "created_at": media.created_at.isoformat(),
                    "output_path": media.output_path
                })
            
            return result, total
        
        except Exception as e:
            logger.error(f"Error searching media: {e}")
            return [], 0
    
    def get_media_stats(self) -> Dict[str, Any]:
        """
        Get statistics about media
        
        Returns:
            Dict: Media statistics
        """
        try:
            stats = {
                "total_media": len(self.media_repo.get_all()),
                "by_status": {},
                "by_type": {},
                "recent": {
                    "completed": 0,
                    "failed": 0
                }
            }
            
            # Count by status
            for status in ConversionStatus:
                count = len(self.media_repo.get_by_status(status))
                stats["by_status"][status.name] = count
            
            # Count by type
            for media_type in MediaType:
                count = len(self.media_repo.get_by_type(media_type))
                stats["by_type"][media_type.name] = count
            
            # Count recent (last 24 hours)
            yesterday = datetime.now() - timedelta(days=1)
            all_media = self.media_repo.get_all()
            
            for media in all_media:
                if media.updated_at >= yesterday:
                    if media.status == ConversionStatus.COMPLETED:
                        stats["recent"]["completed"] += 1
                    elif media.status == ConversionStatus.FAILED:
                        stats["recent"]["failed"] += 1
            
            # Add system information
            stats["system"] = ResourceMonitor.check_system_resources()
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting media stats: {e}")
            return {"error": str(e)}
    
    def cleanup_old_jobs(self, days_to_keep: int = None) -> Dict[str, Any]:
        """
        Clean up old jobs
        
        Args:
            days_to_keep: Number of days to keep jobs (default from config)
            
        Returns:
            Dict: Cleanup results
        """
        try:
            if days_to_keep is None:
                days_to_keep = config.retention_days
            
            if days_to_keep < 1:
                return {"error": "days_to_keep must be at least 1"}
            
            # Clean up old jobs
            count = self.job_repo.cleanup_old_jobs(days_to_keep)
            
            # Clean up temp files
            if config.auto_clean_temp:
                temp_files_removed = 0
                now = time.time()
                for root, dirs, files in os.walk(config.temp_dir):
                    for file in files:
                        path = os.path.join(root, file)
                        if os.path.exists(path):
                            # Remove files older than retention_days
                            mtime = os.path.getmtime(path)
                            if now - mtime > days_to_keep * 86400:  # 86400 seconds in a day
                                try:
                                    is_valid, _ = SecurityValidator.validate_filepath(path, config.temp_dir)
                                    if is_valid:
                                        os.remove(path)
                                        temp_files_removed += 1
                                except Exception as e:
                                    logger.warning(f"Failed to remove temp file {path}: {e}")
            
            return {
                "success": True,
                "jobs_removed": count,
                "temp_files_removed": temp_files_removed if config.auto_clean_temp else 0,
                "days_kept": days_to_keep
            }
        
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            return {"error": str(e)}
    
    def _dict_to_conversion_options(self, options_dict: Dict[str, Any]) -> ConversionOptions:
        """
        Convert a dictionary to ConversionOptions
        
        Args:
            options_dict: Dictionary with options
            
        Returns:
            ConversionOptions: Conversion options object
        """
        # Set defaults from config
        output_format = options_dict.get('output_format', config.media.default_output_format)
        video_quality = options_dict.get('video_quality', config.media.default_video_quality)
        keep_original = options_dict.get('keep_original', config.media.keep_original_default)
        
        # Convert string values to enums
        if isinstance(output_format, str):
            output_format = OutputFormat.from_string(output_format)
        
        if isinstance(video_quality, str):
            video_quality = VideoQuality.from_string(video_quality)
        
        # Sanitize custom ffmpeg args if provided
        custom_ffmpeg_args = options_dict.get('custom_ffmpeg_args', [])
        if custom_ffmpeg_args:
            # Filter out potentially dangerous args
            dangerous_patterns = ['-f', 'format', 'concat', 'protocol_whitelist']
            safe_args = [arg for arg in custom_ffmpeg_args if not any(pattern in arg for pattern in dangerous_patterns)]
            custom_ffmpeg_args = safe_args
        
        # Validate output directory if provided
        output_directory = options_dict.get('output_directory')
        if output_directory:
            is_valid, error = SecurityValidator.validate_filepath(output_directory)
            if not is_valid:
                # Default to config directory if invalid
                logger.warning(f"Invalid output directory: {error}. Using default.")
                output_directory = None
        
        # Create options object
        return ConversionOptions(
            output_format=output_format,
            video_quality=video_quality,
            keep_original=keep_original,
            audio_quality=options_dict.get('audio_quality', "192k"),
            subtitle_language=options_dict.get('subtitle_language'),
            audio_language=options_dict.get('audio_language'),
            custom_ffmpeg_args=custom_ffmpeg_args,
            output_directory=output_directory,
            organize_media=options_dict.get('organize_media', True)
        ) 