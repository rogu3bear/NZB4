#!/usr/bin/env python3
"""
Universal Media Converter
Downloads media content from various sources and converts to MP4/MOV
"""

import os
import sys
import argparse
import logging
import tempfile
import time
import re
import json
import urllib.parse
import shutil
from pathlib import Path

# Import utility modules
from nzb4.utils.usenet import UsenetDownloader
from nzb4.utils.torrent import TorrentDownloader
from nzb4.utils.direct import DirectDownloader
from nzb4.utils.video import VideoConverter
from nzb4.utils.free_provider import FreeProviderFinder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def determine_download_method(media_source):
    """Determine the appropriate download method based on the file or URL provided"""
    
    # Check if it's a file path or URL
    if os.path.exists(media_source):
        # Check file extension
        if media_source.lower().endswith('.nzb'):
            logger.info("NZB file detected, using Usenet downloader")
            return "usenet", media_source
        elif media_source.lower().endswith(('.torrent', '.magnet')):
            logger.info("Torrent file detected, using Torrent downloader")
            return "torrent", media_source
        else:
            # Check if it's a video file already
            if any(media_source.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv']):
                logger.info("Video file detected, will convert directly")
                return "direct_file", media_source
    else:
        # Check if it's a URL
        if media_source.startswith(('http://', 'https://', 'ftp://')):
            # Check URL type
            if 'youtube.com' in media_source or 'youtu.be' in media_source:
                logger.info("YouTube URL detected, using YouTube downloader")
                return "youtube", media_source
            elif 'magnet:?' in media_source:
                logger.info("Magnet link detected, using Torrent downloader")
                return "torrent", media_source
            else:
                logger.info("URL detected, attempting direct download")
                return "direct_url", media_source
        
        # Try to interpret as a search query for public content
        if not os.path.exists(media_source) and ' ' in media_source:
            logger.info("Search query detected, searching for free content")
            return "search", media_source
    
    # Default to search if method couldn't be determined
    logger.info("Couldn't determine download method, using search")
    return "search", media_source

def detect_media_type(search_term, filename):
    """
    Detect the type of media (movie, TV show, music) based on the search term and filename
    
    Returns:
        str: 'movie', 'tv', 'music', or 'other'
    """
    # Common patterns for media types
    movie_patterns = [
        r'\b\d{4}\b',  # Year like 2020
        r'\b(720p|1080p|2160p|4k)\b',  # Common resolution markers
        r'\b(BRRIP|BLURAY|WEBDL|DVDRIP)\b',  # Common source markers
        r'directors.cut',
        r'extended.edition'
    ]
    
    tv_patterns = [
        r'\bS\d{1,2}E\d{1,2}\b',  # S01E01 format
        r'\b\d{1,2}x\d{1,2}\b',  # 1x01 format
        r'season \d{1,2}',
        r'episode \d{1,2}',
        r'\b(complete series|complete season)\b'
    ]
    
    music_patterns = [
        r'\b(MP3|FLAC|WAV|AAC|ALAC|AIFF)\b',  # Common audio formats
        r'\b(album|discography|OST|soundtrack)\b',
        r'\bVA -',  # Various Artists
        r'\b\d{3,4}kbps\b',  # Bitrate
        r'\bCDDA\b'
    ]
    
    # Combine terms to search
    combined_term = (search_term + " " + filename).lower()
    
    # Check patterns
    for pattern in movie_patterns:
        if re.search(pattern, combined_term, re.IGNORECASE):
            return 'movie'
            
    for pattern in tv_patterns:
        if re.search(pattern, combined_term, re.IGNORECASE):
            return 'tv'
            
    for pattern in music_patterns:
        if re.search(pattern, combined_term, re.IGNORECASE):
            return 'music'
    
    # Default
    return 'other'

def organize_output_path(base_output_dir, search_term, media_type=None):
    """
    Create an organized output path based on media type and search term
    
    Args:
        base_output_dir: Base output directory
        search_term: Search term or title
        media_type: Detected media type (movie, tv, music)
        
    Returns:
        str: Organized output path
    """
    # Clean up search term for folder name
    clean_name = re.sub(r'[^\w\s-]', '', search_term).strip()
    clean_name = re.sub(r'[-\s]+', '_', clean_name)
    
    # Detect media type if not provided
    if not media_type:
        media_type = detect_media_type(search_term, clean_name)
    
    # Create organized path
    if media_type == 'movie':
        # Extract year if present
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', search_term)
        year = year_match.group(0) if year_match else ''
        
        if year:
            folder_name = f"{clean_name}_{year}"
            output_path = os.path.join(base_output_dir, 'movies', folder_name)
        else:
            output_path = os.path.join(base_output_dir, 'movies', clean_name)
            
    elif media_type == 'tv':
        # Try to extract show name and season
        season_match = re.search(r'\bS(\d{1,2})\b|\bSeason\s+(\d{1,2})\b', search_term, re.IGNORECASE)
        
        if season_match:
            season_num = season_match.group(1) or season_match.group(2)
            show_name = clean_name.split('_S')[0].split('_Season')[0]
            output_path = os.path.join(base_output_dir, 'tv', show_name, f"Season_{season_num}")
        else:
            output_path = os.path.join(base_output_dir, 'tv', clean_name)
            
    elif media_type == 'music':
        # Try to extract artist and album
        artist_album = clean_name.replace('-', '_').split('_', 1)
        
        if len(artist_album) > 1:
            artist, album = artist_album[0].strip(), artist_album[1].strip()
            output_path = os.path.join(base_output_dir, 'music', artist, album)
        else:
            output_path = os.path.join(base_output_dir, 'music', clean_name)
    else:
        output_path = os.path.join(base_output_dir, 'other', clean_name)
    
    # Ensure the path exists
    os.makedirs(output_path, exist_ok=True)
    
    return output_path

def process_media(media_source, output_dir, video_format="mp4", download_dir="/downloads", keep_original=False, verbose=False, organize=True):
    """Process media from the source to a video file"""
    
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create directories if they don't exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(download_dir, exist_ok=True)
    
    # Determine download method
    method, source = determine_download_method(media_source)
    
    # Initialize downloaders
    usenet_downloader = UsenetDownloader(download_dir=download_dir)
    torrent_downloader = TorrentDownloader(download_dir=download_dir)
    direct_downloader = DirectDownloader(download_dir=download_dir)
    video_converter = VideoConverter()
    provider_finder = FreeProviderFinder()
    
    downloaded_files = []
    search_term = media_source
    
    try:
        # Process based on method
        if method == "usenet":
            # Try Usenet first, if it fails, use torrent search
            try:
                downloaded_files = usenet_downloader.download(source)
                if not downloaded_files:
                    raise Exception("No files downloaded from Usenet")
            except Exception as e:
                logger.warning(f"Usenet download failed: {e}. Trying free alternatives...")
                # Get NZB content name and search for torrent
                nzb_name = os.path.basename(source).replace('.nzb', '')
                search_term = nzb_name.replace('.', ' ').replace('_', ' ')
                torrent_url = provider_finder.search_torrent(search_term)
                if torrent_url:
                    downloaded_files = torrent_downloader.download(torrent_url)
        
        elif method == "torrent":
            downloaded_files = torrent_downloader.download(source)
            if os.path.exists(source):
                # Extract search term from torrent filename
                torrent_name = os.path.basename(source).replace('.torrent', '')
                search_term = torrent_name.replace('.', ' ').replace('_', ' ')
            
        elif method == "direct_file":
            # Just use the file directly
            downloaded_files = [source]
            file_name = os.path.basename(source).split('.')[0]
            search_term = file_name.replace('.', ' ').replace('_', ' ')
            
        elif method == "direct_url":
            downloaded_files = direct_downloader.download(source)
            
        elif method == "youtube":
            downloaded_files = direct_downloader.download_youtube(source)
            
        elif method == "search":
            # Try to find content from free sources
            
            # First try YouTube
            youtube_url = provider_finder.search_youtube(search_term)
            if youtube_url:
                logger.info(f"Found content on YouTube: {youtube_url}")
                downloaded_files = direct_downloader.download_youtube(youtube_url)
            
            # If that fails, try public torrents
            if not downloaded_files:
                torrent_url = provider_finder.search_torrent(search_term)
                if torrent_url:
                    logger.info(f"Found torrent: {torrent_url}")
                    downloaded_files = torrent_downloader.download(torrent_url)
            
            # If that fails, try direct download sites
            if not downloaded_files:
                direct_url = provider_finder.search_direct(search_term)
                if direct_url:
                    logger.info(f"Found direct download: {direct_url}")
                    downloaded_files = direct_downloader.download(direct_url)
        
        # Filter for video files
        video_files = [f for f in downloaded_files if any(
            f.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        )]
        
        if not video_files:
            logger.error("No video files found in downloaded content")
            sys.exit(1)
            
        # Sort by size (largest first)
        video_files.sort(key=lambda x: os.path.getsize(x) if os.path.exists(x) else 0, reverse=True)
        
        # Convert the largest video file to the desired format
        largest_video = video_files[0]
        
        # Determine media type from content
        media_type = detect_media_type(search_term, os.path.basename(largest_video))
        
        # Generate output filename and path
        if method == "search" or organize:
            # Organized output path
            final_output_dir = organize_output_path(output_dir, search_term, media_type)
            output_name = re.sub(r'[^\w\s-]', '', search_term).strip()
            output_name = re.sub(r'[-\s]+', '_', output_name)[:70]  # Limit filename length
        else:
            # Direct output path based on source name
            final_output_dir = output_dir
            output_name = os.path.basename(source).split('.')[0]
            
        output_file = os.path.join(final_output_dir, f"{output_name}.{video_format}")
        
        # Make sure we're not overwriting the source file
        if output_file == largest_video:
            output_file = os.path.join(final_output_dir, f"{output_name}_converted.{video_format}")
        
        # Convert video
        success = video_converter.convert(largest_video, output_file, video_format)
        
        if success:
            logger.info(f"Conversion successful. Output file: {output_file}")
            
            # Clean up downloaded files if requested
            if not keep_original:
                for file in downloaded_files:
                    if file != source and os.path.exists(file):  # Don't delete original source file
                        logger.debug(f"Cleaning up: {file}")
                        if os.path.isfile(file):
                            try:
                                os.remove(file)
                            except Exception:
                                pass
            
            return output_file
        else:
            logger.error("Conversion failed")
            sys.exit(1)
            
    except Exception as e:
        logger.exception(f"Error processing media: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Universal Media Converter - Download and convert media from various sources")
    parser.add_argument("source", help="Media source (NZB file, torrent file, URL, or search query)")
    parser.add_argument("-o", "--output-dir", default="/complete", help="Output directory (default: /complete)")
    parser.add_argument("-d", "--download-dir", default="/downloads", help="Download directory (default: /downloads)")
    parser.add_argument("-f", "--format", choices=["mp4", "mov"], default="mp4", help="Output format (default: mp4)")
    parser.add_argument("-k", "--keep-original", action="store_true", help="Keep original downloaded files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-n", "--no-organize", action="store_true", help="Disable automatic content organization")
    parser.add_argument("-t", "--media-type", choices=["movie", "tv", "music", "other"], help="Manually specify media type")
    
    args = parser.parse_args()
    
    organize = not args.no_organize
    media_type = args.media_type if args.media_type else None
    
    # If media type is specified, ensure output directory is updated
    if media_type and organize:
        base_dir = args.output_dir
        if base_dir == "/complete":
            if media_type == "movie":
                args.output_dir = "/media/movies"
            elif media_type == "tv":
                args.output_dir = "/media/tv"
            elif media_type == "music":
                args.output_dir = "/media/music"
    
    process_media(
        args.source,
        args.output_dir,
        args.format,
        args.download_dir,
        args.keep_original,
        args.verbose,
        organize
    )

if __name__ == "__main__":
    main() 