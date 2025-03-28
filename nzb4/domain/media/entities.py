#!/usr/bin/env python3
"""
Media domain entities for the NZB4 application.
These classes represent the core business objects related to media.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Any
import os
import uuid


class MediaType(Enum):
    """The type of media content"""
    MOVIE = auto()
    TV_SHOW = auto()
    MUSIC = auto()
    EBOOK = auto()
    OTHER = auto()
    
    @classmethod
    def from_string(cls, value: str) -> 'MediaType':
        """Convert a string to a MediaType enum value"""
        mapping = {
            'movie': cls.MOVIE,
            'tv': cls.TV_SHOW,
            'tvshow': cls.TV_SHOW,
            'tv_show': cls.TV_SHOW,
            'series': cls.TV_SHOW,
            'music': cls.MUSIC,
            'audio': cls.MUSIC,
            'song': cls.MUSIC,
            'album': cls.MUSIC,
            'ebook': cls.EBOOK,
            'book': cls.EBOOK,
            'other': cls.OTHER
        }
        
        normalized = value.lower().strip()
        return mapping.get(normalized, cls.OTHER)


class MediaSource(Enum):
    """Source of the media content"""
    NZB = auto()
    TORRENT = auto()
    DIRECT_URL = auto()
    LOCAL_FILE = auto()
    SEARCH_TERM = auto()
    
    @classmethod
    def detect_from_string(cls, value: str) -> 'MediaSource':
        """Detect the media source type from a string"""
        if not value:
            return cls.SEARCH_TERM
            
        value = value.lower().strip()
        
        if value.endswith('.nzb'):
            return cls.NZB
        elif value.endswith('.torrent'):
            return cls.TORRENT
        elif value.startswith(('http://', 'https://', 'ftp://')):
            return cls.DIRECT_URL
        elif os.path.exists(value):
            return cls.LOCAL_FILE
        else:
            return cls.SEARCH_TERM


class ConversionStatus(Enum):
    """Status of a media conversion job"""
    PENDING = auto()
    DOWNLOADING = auto()
    PROCESSING = auto()
    CONVERTING = auto()
    ORGANIZING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    PAUSED = auto()


class OutputFormat(Enum):
    """Supported output formats"""
    MP4 = auto()
    MKV = auto()
    AVI = auto()
    MOV = auto()
    MP3 = auto()
    AAC = auto()
    PDF = auto()
    EPUB = auto()
    
    @classmethod
    def from_string(cls, value: str) -> 'OutputFormat':
        """Convert a string to an OutputFormat enum value"""
        mapping = {
            'mp4': cls.MP4,
            'mkv': cls.MKV,
            'avi': cls.AVI,
            'mov': cls.MOV,
            'mp3': cls.MP3,
            'aac': cls.AAC,
            'pdf': cls.PDF,
            'epub': cls.EPUB
        }
        
        normalized = value.lower().strip()
        return mapping.get(normalized, cls.MP4)  # Default to MP4


class VideoQuality(Enum):
    """Video quality presets"""
    LOW = auto()      # 480p
    MEDIUM = auto()   # 720p
    HIGH = auto()     # 1080p
    ULTRA = auto()    # 4K
    ORIGINAL = auto() # Source quality
    
    @classmethod
    def from_string(cls, value: str) -> 'VideoQuality':
        """Convert a string to a VideoQuality enum value"""
        mapping = {
            'low': cls.LOW,
            '480p': cls.LOW,
            'medium': cls.MEDIUM,
            '720p': cls.MEDIUM,
            'high': cls.HIGH,
            '1080p': cls.HIGH,
            'ultra': cls.ULTRA,
            '4k': cls.ULTRA,
            'original': cls.ORIGINAL,
            'source': cls.ORIGINAL
        }
        
        normalized = value.lower().strip()
        return mapping.get(normalized, cls.HIGH)  # Default to HIGH


@dataclass
class MediaMetadata:
    """Metadata for media content"""
    title: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration: Optional[int] = None  # In seconds
    resolution: Optional[str] = None  # e.g., "1920x1080"
    framerate: Optional[float] = None  # e.g., 24.0
    codec: Optional[str] = None
    bitrate: Optional[int] = None  # In kbps
    size: Optional[int] = None  # In bytes
    
    # TV Show specific
    season: Optional[int] = None
    episode: Optional[int] = None
    series_name: Optional[str] = None
    
    # Music specific
    artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    
    # Additional metadata
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionOptions:
    """Options for media conversion"""
    output_format: OutputFormat = OutputFormat.MP4
    video_quality: VideoQuality = VideoQuality.HIGH
    keep_original: bool = False
    audio_quality: str = "192k"  # Audio bitrate
    subtitle_language: Optional[str] = None
    audio_language: Optional[str] = None
    custom_ffmpeg_args: List[str] = field(default_factory=list)
    output_directory: Optional[str] = None
    organize_media: bool = True


@dataclass
class Media:
    """Core media entity representing content to be processed"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # URL, file path, or search term
    source_type: MediaSource
    media_type: MediaType
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: MediaMetadata = field(default_factory=MediaMetadata)
    status: ConversionStatus = ConversionStatus.PENDING
    
    # File paths
    downloaded_path: Optional[str] = None
    output_path: Optional[str] = None
    
    # For error tracking
    error_message: Optional[str] = None
    
    # Progress tracking (0-100)
    download_progress: int = 0
    conversion_progress: int = 0
    
    @classmethod
    def create_from_source(cls, source: str, media_type: Union[str, MediaType]) -> 'Media':
        """Factory method to create a Media instance from source"""
        if isinstance(media_type, str):
            media_type = MediaType.from_string(media_type)
            
        source_type = MediaSource.detect_from_string(source)
        
        return cls(
            source=source,
            source_type=source_type,
            media_type=media_type
        )
    
    def update_status(self, status: ConversionStatus, error: Optional[str] = None) -> None:
        """Update the status of this media entity"""
        self.status = status
        self.updated_at = datetime.now()
        
        if error:
            self.error_message = error
    
    def update_progress(self, download_progress: Optional[int] = None, 
                        conversion_progress: Optional[int] = None) -> None:
        """Update progress percentages"""
        if download_progress is not None:
            self.download_progress = max(0, min(100, download_progress))
            
        if conversion_progress is not None:
            self.conversion_progress = max(0, min(100, conversion_progress))
            
        self.updated_at = datetime.now()
    
    def is_complete(self) -> bool:
        """Check if the media conversion is complete"""
        return self.status == ConversionStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if the media conversion has failed"""
        return self.status == ConversionStatus.FAILED


@dataclass
class ConversionJob:
    """A job for converting media from one format to another"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    media_id: str
    options: ConversionOptions
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ConversionStatus = ConversionStatus.PENDING
    error_message: Optional[str] = None
    
    # Commands and output logging
    command: Optional[str] = None
    output_log: List[str] = field(default_factory=list)
    
    def start(self) -> None:
        """Mark the job as started"""
        self.started_at = datetime.now()
        self.status = ConversionStatus.DOWNLOADING
    
    def complete(self) -> None:
        """Mark the job as completed"""
        self.completed_at = datetime.now()
        self.status = ConversionStatus.COMPLETED
    
    def fail(self, error_message: str) -> None:
        """Mark the job as failed"""
        self.completed_at = datetime.now()
        self.status = ConversionStatus.FAILED
        self.error_message = error_message
    
    def add_log(self, message: str) -> None:
        """Add a log message"""
        self.output_log.append(message)
    
    def update_status(self, status: ConversionStatus) -> None:
        """Update the job status"""
        self.status = status 