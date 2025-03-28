#!/usr/bin/env python3
"""
Repository interfaces for the Media domain.
These define abstract classes for data access operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from .entities import Media, ConversionJob, MediaType, ConversionStatus


class MediaRepository(ABC):
    """Repository interface for Media entities"""
    
    @abstractmethod
    def save(self, media: Media) -> Media:
        """Save a media entity to the repository"""
        pass
    
    @abstractmethod
    def get_by_id(self, media_id: Union[str, UUID]) -> Optional[Media]:
        """Get a media entity by ID"""
        pass
    
    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get all media entities with pagination"""
        pass
    
    @abstractmethod
    def get_by_status(self, status: ConversionStatus, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get media entities by status"""
        pass
    
    @abstractmethod
    def get_by_type(self, media_type: MediaType, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get media entities by type"""
        pass
    
    @abstractmethod
    def delete(self, media_id: Union[str, UUID]) -> bool:
        """Delete a media entity"""
        pass
    
    @abstractmethod
    def update_status(self, media_id: Union[str, UUID], status: ConversionStatus, 
                     error_message: Optional[str] = None) -> bool:
        """Update media status"""
        pass
    
    @abstractmethod
    def update_progress(self, media_id: Union[str, UUID], download_progress: Optional[int] = None,
                       conversion_progress: Optional[int] = None) -> bool:
        """Update media progress"""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 100, offset: int = 0) -> List[Media]:
        """Search for media entities"""
        pass


class ConversionJobRepository(ABC):
    """Repository interface for ConversionJob entities"""
    
    @abstractmethod
    def save(self, job: ConversionJob) -> ConversionJob:
        """Save a conversion job to the repository"""
        pass
    
    @abstractmethod
    def get_by_id(self, job_id: Union[str, UUID]) -> Optional[ConversionJob]:
        """Get a conversion job by ID"""
        pass
    
    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[ConversionJob]:
        """Get all conversion jobs with pagination"""
        pass
    
    @abstractmethod
    def get_by_status(self, status: ConversionStatus, limit: int = 100, offset: int = 0) -> List[ConversionJob]:
        """Get conversion jobs by status"""
        pass
    
    @abstractmethod
    def get_by_media_id(self, media_id: Union[str, UUID]) -> List[ConversionJob]:
        """Get all conversion jobs for a media entity"""
        pass
    
    @abstractmethod
    def get_active_jobs(self, limit: int = 100, offset: int = 0) -> List[ConversionJob]:
        """Get all active (non-completed) conversion jobs"""
        pass
    
    @abstractmethod
    def delete(self, job_id: Union[str, UUID]) -> bool:
        """Delete a conversion job"""
        pass
    
    @abstractmethod
    def update_status(self, job_id: Union[str, UUID], status: ConversionStatus,
                     error_message: Optional[str] = None) -> bool:
        """Update job status"""
        pass
    
    @abstractmethod
    def add_log(self, job_id: Union[str, UUID], log_message: str) -> bool:
        """Add a log message to a conversion job"""
        pass
    
    @abstractmethod
    def get_job_stats(self) -> Dict[str, Any]:
        """Get statistics about conversion jobs"""
        pass
    
    @abstractmethod
    def cleanup_old_jobs(self, days_to_keep: int = 30) -> int:
        """Clean up old conversion jobs"""
        pass 