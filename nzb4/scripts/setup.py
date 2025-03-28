#!/usr/bin/env python3
"""
Setup script for NZB4 application.
This script initializes the database and ensures the application is ready to use.
"""

import os
import sys
import logging
from pathlib import Path

# Make sure nzb4 is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from nzb4.config.settings import config
from nzb4.infrastructure.database.sqlite_repository import SQLiteDatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def setup_database() -> bool:
    """
    Set up the database
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Setting up database at {config.database.path}")
        
        # Ensure database directory exists
        db_dir = os.path.dirname(config.database.path)
        os.makedirs(db_dir, exist_ok=True)
        
        # Initialize database
        db_manager = SQLiteDatabaseManager(config.database.path)
        db_manager.initialize_database()
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False


def ensure_directories():
    """Ensure all required directories exist"""
    try:
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
            logger.info(f"Created directory: {directory}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating directories: {e}")
        return False


def main():
    """Main setup function"""
    logger.info("Starting NZB4 setup")
    
    # Ensure all directories exist
    if not ensure_directories():
        logger.error("Failed to create directories")
        sys.exit(1)
    
    # Set up database
    if not setup_database():
        logger.error("Failed to set up database")
        sys.exit(1)
    
    logger.info("NZB4 setup completed successfully")


if __name__ == "__main__":
    main() 