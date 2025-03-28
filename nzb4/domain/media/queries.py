#!/usr/bin/env python3
"""
Query models for the Media domain
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from nzb4.domain.media.entities import MediaType, MediaStatus, MediaJobType


@dataclass
class MediaByIdQuery:
    """Query to find media by its ID"""
    id: str


@dataclass
class MediaByPathQuery:
    """Query to find media by its file path"""
    file_path: str


@dataclass
class MediaByStatusQuery:
    """Query to find media by its status"""
    status: MediaStatus


@dataclass
class MediaByTypeQuery:
    """Query to find media by its type"""
    media_type: MediaType


@dataclass
class MediaByMetadataQuery:
    """Query to find media by its metadata attributes"""
    title: Optional[str] = None
    year: Optional[int] = None
    director: Optional[str] = None
    genre: Optional[str] = None
    actor: Optional[str] = None
    series: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    artist: Optional[str] = None
    album: Optional[str] = None


@dataclass
class AllMediaQuery:
    """Query to fetch all media, optionally paginated"""
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"


@dataclass
class MediaSearchQuery:
    """Query to search for media by keyword across multiple fields"""
    keyword: str
    fields: Optional[List[str]] = None
    page: int = 1
    page_size: int = 20


@dataclass
class JobByIdQuery:
    """Query to find job by its ID"""
    id: str


@dataclass
class JobsByMediaIdQuery:
    """Query to find jobs associated with a specific media ID"""
    media_id: str


@dataclass
class JobsByStatusQuery:
    """Query to find jobs by their status"""
    status: MediaStatus
    job_type: Optional[MediaJobType] = None


@dataclass
class ActiveJobsQuery:
    """Query to find all active jobs"""
    job_type: Optional[MediaJobType] = None


@dataclass
class CompletedJobsQuery:
    """Query to find all completed jobs within a time range"""
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    job_type: Optional[MediaJobType] = None
    page: int = 1
    page_size: int = 20


@dataclass
class FailedJobsQuery:
    """Query to find all failed jobs within a time range"""
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    job_type: Optional[MediaJobType] = None
    page: int = 1
    page_size: int = 20


@dataclass
class DiskSpaceQuery:
    """Query to get disk space information for a directory"""
    directory: Optional[str] = None


@dataclass
class MediaStatisticsQuery:
    """Query to get statistics about media in the system"""
    group_by: Optional[str] = None  # e.g., "type", "status", "month"
    since: Optional[datetime] = None
    until: Optional[datetime] = None 