# Universal Media Converter (Docker Edition)

A comprehensive dockerized solution that converts media from various sources to MP4/MOV video files. This tool is designed to be **completely free** and requires no paid accounts.

## Features

- **No Paid Accounts Required**: Utilizes only free sources for content
- **Multiple Source Types**: Handles NZB files, torrents, direct URLs, and search queries
- **Smart Content Finding**: If given a search term, automatically finds the content from free sources
- **Automatic Media Organization**: Places media in proper folders (movies, TV shows, music) based on content type
- **User-Friendly Web Interface**: Easy-to-use web UI for searching, uploading, and tracking conversions
- **Source Fallback**: If one source fails, automatically tries alternatives
- **Fully Containerized**: No need to install dependencies locally

## Quick Start

### Prerequisites

- Docker and Docker Compose

### Setup and Run

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/media-converter.git
   cd media-converter
   ```

2. Build and start the container:
   ```
   docker-compose up -d
   ```

3. Open the web interface:
   ```
   http://localhost:5000
   ```

4. Use the web interface to:
   - Search for content by name
   - Upload NZB or torrent files
   - Specify media type (movie, TV show, music)
   - Track conversion progress
   - Download converted files

## Using the Command Line

You can also use the command line for starting conversions:

```bash
# Use the simple helper script
./run.sh "Movie Name" movies      # Puts in movies folder
./run.sh "TV Show S01E01" tv      # Puts in TV folder

# Or use docker-compose directly
docker-compose exec media-converter convert -t movie "Movie Name"
```

## Directory Structure

- `nzb/` - Place your NZB files here
- `torrents/` - Place your torrent files here
- `downloads/` - Temporary download location
- `complete/` - Root folder for all converted media
  - `complete/movies/` - Organized movie files
  - `complete/tv/` - Organized TV shows
  - `complete/music/` - Organized music files
- `config/` - Configuration for SABnzbd and Transmission

## Custom Media Folders

You can specify custom media folders in two ways:

1. Using environment variables with docker-compose:
   ```
   MOVIES_DIR=/path/to/movies MUSIC_DIR=/path/to/music docker-compose up -d
   ```

2. Editing the volume mappings in docker-compose.yml:
   ```yaml
   volumes:
     - /my/movies/folder:/media/movies
     - /my/tv/folder:/media/tv
     - /my/music/folder:/media/music
   ```

## Supported Input Types

- **NZB Files**: Automatically processed using free Usenet servers
- **Torrent Files**: Processed using Transmission
- **Magnet Links**: Direct torrent downloads
- **YouTube URLs**: Downloaded and converted automatically
- **Direct Download URLs**: Handled with parallel downloader
- **Search Queries**: Automatically searches for content from free sources:
  - YouTube
  - Public domain archives
  - Public torrent sites
  - Free direct download sites

## Web Interfaces

- **Media Converter UI**: http://localhost:5000
- **SABnzbd**: http://localhost:8080
- **Transmission**: http://localhost:9091

## Notes

- The automated search and download feature works best for content that is freely available
- For better results with search queries, include specific details (year, quality, etc.)
- No login or paid accounts are required for any functionality
- All included tools and utilities are free and open source

## Folder Organization
The media converter now automatically organizes output files into subfolders based on media type (movies, TV shows, music). Customize these paths via environment variables in the docker-compose.yml file.

## Web Interface
A new Flask-based web interface allows you to convert media easily via your browser.

**Usage:**

1. Start the web interface:
   ```bash
   python3 web_interface.py
   ```
2. Open your browser and navigate to [http://localhost:5000](http://localhost:5000) to start converting files. 