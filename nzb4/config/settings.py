#!/usr/bin/env python3
"""
Configuration module for the NZB4 application.
This handles loading and validating configuration from various sources.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration"""
    type: str = "sqlite"
    path: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "data" / "nzb4.db"))
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate database configuration"""
        errors = []
        
        if self.type not in ("sqlite", "postgresql", "mysql"):
            errors.append(f"Unsupported database type: {self.type}")
        
        if self.type == "sqlite":
            # Ensure path is writable
            db_dir = os.path.dirname(self.path)
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                except Exception as e:
                    errors.append(f"Could not create database directory: {e}")
            elif not os.access(db_dir, os.W_OK):
                errors.append(f"Database directory is not writable: {db_dir}")
        else:
            # For other database types, ensure required fields are provided
            if not self.host:
                errors.append("Database host is required")
            if not self.port:
                errors.append("Database port is required")
            if not self.username:
                errors.append("Database username is required")
            if not self.database:
                errors.append("Database name is required")
        
        return errors


@dataclass
class MediaConfig:
    """Media configuration"""
    download_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "downloads"))
    complete_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "complete"))
    movies_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "complete" / "movies"))
    tv_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "complete" / "tv"))
    music_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "complete" / "music"))
    other_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "complete" / "other"))
    min_disk_space_mb: int = 500
    default_output_format: str = "mp4"
    default_video_quality: str = "high"
    default_media_type: str = "movie"
    keep_original_default: bool = False
    concurrent_conversions: int = 2
    
    def validate(self) -> List[str]:
        """Validate media configuration"""
        errors = []
        
        # Ensure directories exist or can be created
        dirs = [
            self.download_dir, 
            self.complete_dir,
            self.movies_dir,
            self.tv_dir,
            self.music_dir,
            self.other_dir
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    errors.append(f"Could not create directory: {dir_path} - {e}")
            elif not os.access(dir_path, os.W_OK):
                errors.append(f"Directory is not writable: {dir_path}")
        
        # Validate other settings
        if self.min_disk_space_mb < 100:
            errors.append(f"min_disk_space_mb is too small: {self.min_disk_space_mb}")
        
        if self.default_output_format not in ("mp4", "mkv", "avi", "mov", "mp3", "aac"):
            errors.append(f"Unsupported default_output_format: {self.default_output_format}")
        
        if self.default_video_quality not in ("low", "medium", "high", "ultra", "original"):
            errors.append(f"Unsupported default_video_quality: {self.default_video_quality}")
        
        if self.default_media_type not in ("movie", "tv", "music", "other"):
            errors.append(f"Unsupported default_media_type: {self.default_media_type}")
        
        if self.concurrent_conversions < 1:
            errors.append(f"concurrent_conversions must be at least 1: {self.concurrent_conversions}")
        
        return errors


@dataclass
class NetworkConfig:
    """Network configuration"""
    host: str = "127.0.0.1"
    port: int = 8000
    base_url: str = "/"
    ssl_enabled: bool = False
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    download_speed_limit_kb: int = 0
    max_connections: int = 10
    retry_attempts: int = 3
    connection_timeout: int = 30
    proxy_url: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate network configuration"""
        errors = []
        
        if self.port < 1 or self.port > 65535:
            errors.append(f"Invalid port number: {self.port}")
        
        if self.ssl_enabled:
            if not self.ssl_cert:
                errors.append("SSL certificate path is required when SSL is enabled")
            elif not os.path.exists(self.ssl_cert):
                errors.append(f"SSL certificate not found: {self.ssl_cert}")
                
            if not self.ssl_key:
                errors.append("SSL key path is required when SSL is enabled")
            elif not os.path.exists(self.ssl_key):
                errors.append(f"SSL key not found: {self.ssl_key}")
        
        if self.download_speed_limit_kb < 0:
            errors.append("download_speed_limit_kb cannot be negative")
        
        if self.max_connections < 1:
            errors.append("max_connections must be at least 1")
        
        if self.retry_attempts < 0:
            errors.append("retry_attempts cannot be negative")
        
        if self.connection_timeout < 1:
            errors.append("connection_timeout must be at least 1")
        
        return errors


@dataclass
class N8nConfig:
    """n8n integration configuration"""
    enabled: bool = True
    data_dir: str = field(default_factory=lambda: str(Path.home() / "n8n-data"))
    port: int = 5678
    install_type: str = "docker"
    health_check_interval: int = 300  # In seconds
    
    def validate(self) -> List[str]:
        """Validate n8n configuration"""
        errors = []
        
        if self.port < 1 or self.port > 65535:
            errors.append(f"Invalid port number: {self.port}")
        
        if self.install_type not in ("docker", "npm"):
            errors.append(f"Unsupported install_type: {self.install_type}")
        
        if self.health_check_interval < 30:
            errors.append("health_check_interval must be at least 30 seconds")
        
        # Ensure data directory exists or can be created
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Could not create n8n data directory: {e}")
        elif not os.access(self.data_dir, os.W_OK):
            errors.append(f"n8n data directory is not writable: {self.data_dir}")
        
        return errors


@dataclass
class AppConfig:
    """Main application configuration"""
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"
    temp_dir: str = field(default_factory=lambda: str(Path.home() / "nzb4" / "temp"))
    auto_clean_temp: bool = True
    retention_days: int = 30
    ui_theme: str = "dark"
    jobs_per_page: int = 20
    
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    n8n: N8nConfig = field(default_factory=N8nConfig)
    
    def validate(self) -> List[str]:
        """Validate all configuration"""
        errors = []
        
        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_log_levels:
            errors.append(f"Invalid log_level: {self.log_level}")
        
        # Validate environment
        valid_environments = {"development", "testing", "production"}
        if self.environment not in valid_environments:
            errors.append(f"Invalid environment: {self.environment}")
        
        # Validate temp directory
        if not os.path.exists(self.temp_dir):
            try:
                os.makedirs(self.temp_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Could not create temp directory: {e}")
        elif not os.access(self.temp_dir, os.W_OK):
            errors.append(f"Temp directory is not writable: {self.temp_dir}")
        
        # Validate retention days
        if self.retention_days < 1:
            errors.append("retention_days must be at least 1")
        
        # Validate UI theme
        if self.ui_theme not in ("light", "dark", "auto"):
            errors.append(f"Invalid ui_theme: {self.ui_theme}")
        
        # Validate jobs_per_page
        if self.jobs_per_page < 1:
            errors.append("jobs_per_page must be at least 1")
        
        # Validate other configs
        errors.extend(self.database.validate())
        errors.extend(self.media.validate())
        errors.extend(self.network.validate())
        errors.extend(self.n8n.validate())
        
        return errors
    
    @classmethod
    def from_file(cls, file_path: str) -> 'AppConfig':
        """Load configuration from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            return cls.from_dict(config_data)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {file_path}")
            return cls()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file: {file_path}")
            return cls()
        except Exception as e:
            logger.error(f"Error loading config from {file_path}: {e}")
            return cls()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AppConfig':
        """Create configuration from a dictionary"""
        # Extract nested configs
        database_dict = config_dict.pop('database', {})
        media_dict = config_dict.pop('media', {})
        network_dict = config_dict.pop('network', {})
        n8n_dict = config_dict.pop('n8n', {})
        
        # Create nested configs
        database_config = DatabaseConfig(**database_dict)
        media_config = MediaConfig(**media_dict)
        network_config = NetworkConfig(**network_dict)
        n8n_config = N8nConfig(**n8n_dict)
        
        # Create main config
        return cls(
            **config_dict,
            database=database_config,
            media=media_config,
            network=network_config,
            n8n=n8n_config
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary"""
        # Helper function to convert a dataclass to dict
        def dataclass_to_dict(obj):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                if hasattr(value, '__dataclass_fields__'):
                    result[field_name] = dataclass_to_dict(value)
                else:
                    result[field_name] = value
            return result
        
        return dataclass_to_dict(self)
    
    def save_to_file(self, file_path: str) -> bool:
        """Save configuration to a JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write config to file
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving config to {file_path}: {e}")
            return False


# Default config file locations
DEFAULT_CONFIG_PATHS = [
    # /etc/nzb4/config.json for system-wide configuration
    "/etc/nzb4/config.json",
    
    # ~/.config/nzb4/config.json for user configuration
    os.path.expanduser("~/.config/nzb4/config.json"),
    
    # ./config.json for local configuration
    os.path.join(os.getcwd(), "config.json")
]


def load_config() -> AppConfig:
    """
    Load configuration from environment and files
    
    Configuration is loaded in the following order (later sources override earlier ones):
    1. Default values
    2. System config file (/etc/nzb4/config.json)
    3. User config file (~/.config/nzb4/config.json)
    4. Local config file (./config.json)
    5. Environment variables (NZB4_*)
    """
    # Start with default config
    config = AppConfig()
    
    # Load from config files
    for config_path in DEFAULT_CONFIG_PATHS:
        if os.path.exists(config_path):
            logger.info(f"Loading config from {config_path}")
            file_config = AppConfig.from_file(config_path)
            
            # Update with file config values
            config = AppConfig.from_dict({**config.to_dict(), **file_config.to_dict()})
    
    # Override with environment variables
    # TODO: Implement environment variable loading
    
    # Validate config
    errors = config.validate()
    if errors:
        for error in errors:
            logger.warning(f"Config validation error: {error}")
    
    return config


# Global configuration instance
config = load_config() 