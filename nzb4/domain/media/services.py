#!/usr/bin/env python3
"""
Domain services for media handling.
These services implement business logic for media operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from .entities import (
    Media, ConversionJob, MediaType, MediaSource, 
    ConversionStatus, OutputFormat, VideoQuality, ConversionOptions
)
from .repositories import MediaRepository, ConversionJobRepository


class MediaDetectionService(ABC):
    """Service for detecting media type and metadata"""
    
    @abstractmethod
    def detect_media_type(self, source: str) -> MediaType:
        """
        Detect the type of media from the source
        
        Args:
            source: The media source (URL, file path, etc.)
            
        Returns:
            MediaType: The detected media type
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, source: str, media_type: MediaType) -> Dict[str, Any]:
        """
        Extract metadata from the media source
        
        Args:
            source: The media source
            media_type: The media type
            
        Returns:
            Dict: The extracted metadata
        """
        pass


class MediaDownloadService(ABC):
    """Service for downloading media from various sources"""
    
    @abstractmethod
    def download(self, media: Media, output_path: str) -> bool:
        """
        Download media from source
        
        Args:
            media: The media to download
            output_path: Path to save the downloaded content
            
        Returns:
            bool: True if download successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cancel_download(self, media_id: Union[str, UUID]) -> bool:
        """
        Cancel an ongoing download
        
        Args:
            media_id: ID of the media being downloaded
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_download_progress(self, media_id: Union[str, UUID]) -> int:
        """
        Get download progress percentage
        
        Args:
            media_id: ID of the media being downloaded
            
        Returns:
            int: Download progress (0-100)
        """
        pass


class MediaConversionService(ABC):
    """Service for converting media between formats"""
    
    @abstractmethod
    def convert(self, media: Media, options: ConversionOptions) -> bool:
        """
        Convert media to the target format
        
        Args:
            media: The media to convert
            options: Conversion options
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cancel_conversion(self, media_id: Union[str, UUID]) -> bool:
        """
        Cancel an ongoing conversion
        
        Args:
            media_id: ID of the media being converted
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_conversion_progress(self, media_id: Union[str, UUID]) -> int:
        """
        Get conversion progress percentage
        
        Args:
            media_id: ID of the media being converted
            
        Returns:
            int: Conversion progress (0-100)
        """
        pass
    
    @abstractmethod
    def get_available_formats(self, media_type: MediaType) -> List[OutputFormat]:
        """
        Get available output formats for a media type
        
        Args:
            media_type: The type of media
            
        Returns:
            List[OutputFormat]: Available output formats
        """
        pass


class MediaOrganizationService(ABC):
    """Service for organizing media files into appropriate directories"""
    
    @abstractmethod
    def organize(self, media: Media, base_path: str) -> str:
        """
        Organize media files into appropriate directories
        
        Args:
            media: The media to organize
            base_path: Base path for organization
            
        Returns:
            str: Path where the media was organized
        """
        pass
    
    @abstractmethod
    def get_suggested_path(self, media: Media, base_path: str) -> str:
        """
        Get suggested path for organizing media without moving it
        
        Args:
            media: The media to organize
            base_path: Base path for organization
            
        Returns:
            str: Suggested path
        """
        pass


class MediaService:
    """
    High-level service that orchestrates media operations
    using the specialized services above.
    """
    
    def __init__(
        self,
        media_repo: MediaRepository,
        job_repo: ConversionJobRepository,
        detector: MediaDetectionService,
        downloader: MediaDownloadService,
        converter: MediaConversionService,
        organizer: MediaOrganizationService
    ):
        self.media_repo = media_repo
        self.job_repo = job_repo
        self.detector = detector
        self.downloader = downloader
        self.converter = converter
        self.organizer = organizer
    
    def process_media(self, source: str, conversion_options: ConversionOptions) -> str:
        """
        Process media from source to output with the given options
        
        Args:
            source: Media source (URL, file path, etc.)
            conversion_options: Options for conversion
            
        Returns:
            str: Job ID of the created conversion job
        """
        # Detect media type
        media_type = self.detector.detect_media_type(source)
        
        # Create media entity
        media = Media.create_from_source(source, media_type)
        media = self.media_repo.save(media)
        
        # Create conversion job
        job = ConversionJob(media_id=media.id, options=conversion_options)
        job = self.job_repo.save(job)
        
        # Start processing in a new thread or task queue
        # For now, we'll just return the job ID
        return job.id
    
    def get_job_status(self, job_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Get status of a conversion job
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dict: Job status information
        """
        job = self.job_repo.get_by_id(job_id)
        if not job:
            return {"error": "Job not found"}
        
        media = self.media_repo.get_by_id(job.media_id)
        if not media:
            return {"error": "Media not found"}
        
        return {
            "id": job.id,
            "status": job.status.name,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "media": {
                "id": media.id,
                "source": media.source,
                "type": media.media_type.name,
                "source_type": media.source_type.name,
                "download_progress": media.download_progress,
                "conversion_progress": media.conversion_progress,
                "output_path": media.output_path
            },
            "options": {
                "output_format": job.options.output_format.name,
                "video_quality": job.options.video_quality.name,
                "keep_original": job.options.keep_original,
                "output_directory": job.options.output_directory,
                "organize_media": job.options.organize_media
            }
        }
    
    def cancel_job(self, job_id: Union[str, UUID]) -> bool:
        """
        Cancel a conversion job
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        job = self.job_repo.get_by_id(job_id)
        if not job:
            return False
        
        media = self.media_repo.get_by_id(job.media_id)
        if not media:
            return False
        
        # Cancel based on current status
        if job.status == ConversionStatus.DOWNLOADING:
            self.downloader.cancel_download(media.id)
        elif job.status in (ConversionStatus.PROCESSING, ConversionStatus.CONVERTING):
            self.converter.cancel_conversion(media.id)
        
        # Update status
        job.update_status(ConversionStatus.CANCELLED)
        self.job_repo.save(job)
        
        media.update_status(ConversionStatus.CANCELLED)
        self.media_repo.save(media)
        
        return True
    
    def get_active_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get active conversion jobs
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List[Dict]: List of active job information
        """
        jobs = self.job_repo.get_active_jobs(limit=limit)
        result = []
        
        for job in jobs:
            media = self.media_repo.get_by_id(job.media_id)
            if not media:
                continue
                
            result.append({
                "id": job.id,
                "status": job.status.name,
                "created_at": job.created_at.isoformat(),
                "media": {
                    "source": media.source,
                    "type": media.media_type.name,
                    "download_progress": media.download_progress,
                    "conversion_progress": media.conversion_progress
                }
            })
            
        return result 