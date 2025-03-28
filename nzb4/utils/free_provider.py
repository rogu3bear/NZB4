#!/usr/bin/env python3
"""
Free provider finder module
Searches for free content from various sources
"""

import os
import json
import logging
import urllib.parse
import subprocess
import re
import tempfile
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class FreeProviderFinder:
    """Class to find free content from public sources"""
    
    def __init__(self):
        """Initialize the provider finder"""
        # Define search endpoints for different media types
        self.youtube_search_url = "https://www.youtube.com/results?search_query="
        self.torrent_search_urls = [
            "https://nyaa.si/?f=0&c=0_0&q=",  # Anime
            "https://1337x.to/search/",  # General
            "https://www.limetorrents.info/search/all/",  # General
            "https://archive.org/search.php?query="  # Public domain and free content
        ]
        self.direct_search_urls = [
            "https://archive.org/search.php?query=",  # Internet Archive
            "https://search.freeflarum.com/search?q="  # Free movies
        ]
        
    def search_youtube(self, query):
        """
        Search for content on YouTube
        
        Args:
            query: Search query
            
        Returns:
            str: YouTube URL if found, None otherwise
        """
        try:
            # Use yt-dlp to search YouTube
            search_term = urllib.parse.quote(query)
            
            logger.info(f"Searching YouTube for: {query}")
            
            # First try ytsearch
            cmd = [
                "yt-dlp", 
                "--get-id", 
                "--get-title",
                "--get-duration",
                "--no-playlist",
                "--default-search", "ytsearch5",  # Search for 5 results
                query
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                
                # Process output (ID and title alternate in output)
                videos = []
                for i in range(0, len(lines), 3):  # Process in groups of 3 (title, id, duration)
                    if i+2 < len(lines):
                        title = lines[i]
                        video_id = lines[i+1]
                        duration = lines[i+2]
                        
                        # Convert duration to seconds
                        duration_sec = 0
                        try:
                            parts = duration.split(':')
                            if len(parts) == 3:  # hours:minutes:seconds
                                duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            elif len(parts) == 2:  # minutes:seconds
                                duration_sec = int(parts[0]) * 60 + int(parts[1])
                            else:
                                duration_sec = int(parts[0])
                        except:
                            duration_sec = 0
                            
                        videos.append({
                            'id': video_id,
                            'title': title,
                            'duration': duration_sec,
                            'url': f"https://www.youtube.com/watch?v={video_id}"
                        })
                
                # Filter out short videos (less than 3 minutes, likely trailers or clips)
                # And extremely long videos (more than 3 hours, likely full playlists)
                filtered_videos = [v for v in videos if 180 <= v['duration'] <= 10800]
                
                if filtered_videos:
                    # Sort by duration (longest first, assuming full content)
                    videos_sorted = sorted(filtered_videos, key=lambda x: x['duration'], reverse=True)
                    logger.info(f"Found {len(videos_sorted)} matching videos on YouTube")
                    best_match = videos_sorted[0]
                    logger.info(f"Best match: {best_match['title']} ({best_match['url']})")
                    return best_match['url']
                elif videos:
                    # If all videos were filtered out, return the first one anyway
                    logger.info(f"Found video on YouTube (no ideal length): {videos[0]['title']}")
                    return videos[0]['url']
            
            # If yt-dlp direct search didn't work, try using the YouTube search URL
            search_url = self.youtube_search_url + search_term
            logger.info(f"Trying alternate YouTube search method: {search_url}")
            
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                # Look for video IDs in the response
                video_ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', response.text)
                if video_ids:
                    # Remove duplicates
                    video_ids = list(dict.fromkeys(video_ids))
                    # Return first result
                    video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                    logger.info(f"Found video on YouTube: {video_url}")
                    return video_url
            
            logger.info("No videos found on YouTube")
            return None
            
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return None
    
    def search_torrent(self, query):
        """
        Search for torrents on public trackers
        
        Args:
            query: Search query
            
        Returns:
            str: Magnet link or torrent URL if found, None otherwise
        """
        try:
            search_term = urllib.parse.quote(query)
            
            logger.info(f"Searching for torrents: {query}")
            
            # Try multiple torrent sites
            for base_url in self.torrent_search_urls:
                try:
                    if "1337x.to" in base_url:
                        search_url = f"{base_url}{search_term}/1/"
                    elif "limetorrents.info" in base_url:
                        search_url = f"{base_url}{search_term}/"
                    else:
                        search_url = f"{base_url}{search_term}"
                        
                    logger.debug(f"Trying torrent search: {search_url}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    
                    response = requests.get(search_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Look for magnet links directly
                        magnet_links = []
                        
                        # Try to find magnet links
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            if href.startswith('magnet:?'):
                                magnet_links.append(href)
                        
                        if magnet_links:
                            logger.info(f"Found {len(magnet_links)} magnet links")
                            return magnet_links[0]  # Return first magnet link
                        
                        # Look for torrent detail pages
                        torrent_links = []
                        
                        if "nyaa.si" in base_url:
                            # Nyaa.si specific
                            rows = soup.select('tr.default, tr.success')
                            for row in rows:
                                # Filter out small torrents (less than 100MB)
                                size_cell = row.select_one('td.text-center:nth-child(4)')
                                if size_cell and 'GiB' in size_cell.text:
                                    links = row.select('td a')
                                    for link in links:
                                        href = link.get('href', '')
                                        if href.startswith('magnet:?'):
                                            torrent_links.append(href)
                                            break
                                
                        elif "1337x.to" in base_url:
                            # 1337x specific
                            links = soup.select('a[href^="/torrent/"]')
                            for link in links:
                                href = link.get('href')
                                if href and '/torrent/' in href:
                                    detail_url = f"https://1337x.to{href}"
                                    torrent_links.append(detail_url)
                        
                        elif "limetorrents.info" in base_url:
                            # Limetorrents specific
                            links = soup.select('a.tt-name')
                            for link in links:
                                href = link.get('href')
                                if href and href.startswith('/'):
                                    detail_url = f"https://www.limetorrents.info{href}"
                                    torrent_links.append(detail_url)
                        
                        elif "archive.org" in base_url:
                            # Internet Archive specific
                            links = soup.select('a.titleLink')
                            for link in links:
                                href = link.get('href')
                                if href:
                                    detail_url = f"https://archive.org{href}"
                                    torrent_links.append(detail_url)
                        
                        # Follow torrent links to get magnet links if needed
                        if torrent_links:
                            for detail_url in torrent_links[:2]:  # Limit to first 2 results
                                try:
                                    detail_response = requests.get(detail_url, headers=headers, timeout=10)
                                    if detail_response.status_code == 200:
                                        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                                        
                                        # Find magnet links in detail page
                                        for link in detail_soup.find_all('a', href=True):
                                            href = link['href']
                                            if href.startswith('magnet:?'):
                                                logger.info(f"Found magnet link from {detail_url}")
                                                return href
                                except Exception as e:
                                    logger.warning(f"Error fetching detail page {detail_url}: {e}")
                
                except Exception as e:
                    logger.warning(f"Error searching {base_url}: {e}")
            
            logger.info("No torrent found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for torrents: {e}")
            return None
    
    def search_direct(self, query):
        """
        Search for direct download links
        
        Args:
            query: Search query
            
        Returns:
            str: Direct download URL if found, None otherwise
        """
        try:
            search_term = urllib.parse.quote(query)
            
            logger.info(f"Searching for direct downloads: {query}")
            
            # Try Internet Archive first - most reliable free source
            search_url = f"https://archive.org/search.php?query={search_term}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for item links
                item_links = []
                for link in soup.select('a.popUp'):
                    href = link.get('href')
                    if href and href.startswith('/details/'):
                        item_links.append(f"https://archive.org{href}")
                
                # Check item pages for video files
                for item_url in item_links[:3]:  # Check first 3 items
                    try:
                        item_response = requests.get(item_url, headers=headers, timeout=10)
                        if item_response.status_code == 200:
                            item_soup = BeautifulSoup(item_response.text, 'html.parser')
                            
                            # Look for MP4 links
                            for link in item_soup.select('a[href$=".mp4"]'):
                                href = link.get('href')
                                if href:
                                    if href.startswith('//'):
                                        href = f"https:{href}"
                                    elif href.startswith('/'):
                                        href = f"https://archive.org{href}"
                                    logger.info(f"Found direct video link: {href}")
                                    return href
                            
                            # Look for download options
                            for link in item_soup.select('a.format-summary'):
                                format_text = link.text.strip().lower()
                                href = link.get('href')
                                if (format_text in ['mpeg4', 'mp4', 'h.264'] or 'video' in format_text) and href:
                                    if href.startswith('//'):
                                        href = f"https:{href}"
                                    elif href.startswith('/'):
                                        href = f"https://archive.org{href}"
                                    logger.info(f"Found video format link: {href}")
                                    return href
                    except Exception as e:
                        logger.warning(f"Error checking item page {item_url}: {e}")
            
            # Try other search sources
            # This is more complex, as each site has different structures
            # Add more specialized implementations for specific sites here
            
            logger.info("No direct download found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for direct downloads: {e}")
            return None 