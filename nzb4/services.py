import os
import logging
import shutil  # Added for dependency check

from nzb4.config import settings
from nzb4.infrastructure.database.sqlite_repository import SqliteMediaRepository, SqliteConversionJobRepository

from nzb4.services_impl import (
    ConcreteMediaDetectionService,
    ConcreteMediaDownloadService,
    ConcreteMediaConversionService,
    ConcreteMediaOrganizationService,
    MediaService,
)

logger = logging.getLogger(__name__)

media_service = None
_services_initialized = False  # Flag to prevent re-initialization

def _check_dependencies(tools: list[str]) -> bool:
	"""Check if required command-line tools are available in PATH."""
	all_found = True
	missing = []
	for tool in tools:
		if shutil.which(tool) is None:
			missing.append(tool)
			all_found = False
	
	if not all_found:
		logger.error(f"Missing critical external dependencies: {', '.join(missing)}")
		logger.error("Please install them and ensure they are in the system's PATH.")
		# Depending on severity, you might raise an exception here
		# raise EnvironmentError(f"Missing dependencies: {', '.join(missing)}")
	return all_found

def _validate_and_create_dir(dir_path: str) -> bool:
	"""Validate directory path, create if not exists, check writability."""
	try:
		if not os.path.exists(dir_path):
			logger.info(f"Directory not found, creating: {dir_path}")
			os.makedirs(dir_path, exist_ok=True)
		# Check for write permissions
		if not os.access(dir_path, os.W_OK):
			logger.error(f"Directory is not writable: {dir_path}")
			return False
		return True
	except OSError as e:
		logger.error(f"Failed to create or access directory {dir_path}: {e}")
		return False

def init_services(force_reinit: bool = False):
    """Initialize all services. Call this once at application startup."""
    global _services_initialized, media_repo, job_repo, detector, downloader, converter, organizer, media_service
    
    if _services_initialized and not force_reinit:
        logger.debug("Services already initialized.")
        return media_service

    logger.info("Initializing services...")

    # --- 1. Configuration Validation ---
    try:
        db_path = settings.config.database.path
        download_dir = settings.config.media.download_dir
        complete_dir = settings.config.media.complete_dir
        temp_dir = settings.config.media.temp_dir # Assuming temp_dir is needed
        logger.debug("Configuration paths loaded.")
    except AttributeError as e:
        logger.critical(f"Missing essential configuration key: {e}. Cannot initialize services.")
        raise ValueError(f"Missing essential configuration: {e}")

    # --- 2. Directory Validation & Creation ---
    if not _validate_and_create_dir(download_dir) or \
       not _validate_and_create_dir(complete_dir) or \
       not _validate_and_create_dir(temp_dir):
        raise OSError("Failed to validate or create necessary media directories. Check paths and permissions.")
    logger.debug("Media directories validated/created.")

    # Initialize repositories
    # --- 3. Database Initialization ---
    try:
        logger.debug(f"Initializing database at: {db_path}")
        media_repo = SqliteMediaRepository(db_path=db_path)
        job_repo = SqliteConversionJobRepository(db_path=db_path)
        media_repo.initialize() # Assuming exists
        job_repo.initialize()   # Assuming exists
        logger.info("Database repositories initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database repositories at {db_path}: {e}", exc_info=True)
        raise ConnectionError(f"Failed to initialize database: {e}") # Or specific DB error

    # --- 4. External Dependency Check ---
    required_tools = ['ffmpeg', 'aria2c', 'yt-dlp'] # Add others like sabnzbd, transmission-cli if used directly
    if not _check_dependencies(required_tools):
        logger.warning("Some external dependencies are missing. Functionality may be limited.")
        # raise EnvironmentError("Missing critical external tools.")
    else:
        logger.debug("External dependencies checked.")

    # Initialize services
    detector = ConcreteMediaDetectionService()
    downloader = ConcreteMediaDownloadService(download_dir=download_dir)
    converter = ConcreteMediaConversionService()
    organizer = ConcreteMediaOrganizationService()
    
    media_service = MediaService(
        media_repo=media_repo,
        job_repo=job_repo,
        detector=detector,
        downloader=downloader,
        converter=converter,
        organizer=organizer
    )
    
    _services_initialized = True
    logger.info("All services initialized successfully.")
    return media_service 