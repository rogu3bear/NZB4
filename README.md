# Universal Media Converter (NZB4)

A comprehensive dockerized solution that converts media from various sources to video files. This tool is designed to be **completely free** and requires no paid accounts. It features deep integration with N8N for powerful workflow automation.

## Features

- **No Paid Accounts Required**: Utilizes only free sources for content
- **Multiple Source Types**: Handles NZB files, torrents, direct URLs, and search queries
- **Smart Content Finding**: If given a search term, automatically finds the content from free sources
- **Automatic Media Organization**: Places media in proper folders (movies, TV shows, music) based on content type
- **User-Friendly Web Interface**: Easy-to-use web UI for searching, uploading, and tracking conversions
- **Source Fallback**: If one source fails, automatically tries alternatives
- **Fully Containerized**: No need to install dependencies locally
- **N8N Integration**: Deep integration with N8N workflow automation platform for endless customization possibilities
- **Security Features**: Strong input validation, path traversal prevention, and resource monitoring
- **Persistent Storage**: SQLite database to track job history and system configurations 
- **Notification System**: Email and webhook notifications for job events

## Architecture

NZB4 is built with a clean domain-driven design architecture:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Orchestrates domain services and provides application-specific features
- **Infrastructure Layer**: Database, file system, and external service integrations
- **Web Interface**: Flask-based UI for easy management

## Quick Start

### Prerequisites

- Docker and Docker Compose

### Setup and Run

1. Clone this repository:
   ```
   git clone https://github.com/rogu3bear/NZB4.git
   cd NZB4
   ```

2. Build and start the container:
   ```
   docker-compose up -d
   ```

3. Open the web interface:
   ```
   http://localhost:8000
   ```

4. Use the web interface to:
   - Search for content by name
   - Upload NZB or torrent files
   - Specify media type (movie, TV show, music)
   - Track conversion progress
   - Download converted files
   - Configure automation workflows

## Using the Command Line

You can also use the command line for starting conversions:

```bash
# Use the simple helper script
./run.sh "Movie Name" movies      # Puts in movies folder
./run.sh "TV Show S01E01" tv      # Puts in TV folder

# Or use docker-compose directly
docker-compose exec nzb4 convert -t movie "Movie Name"
```

## Directory Structure

- `nzb4/` - Main application code
  - `domain/` - Core domain models and business logic
  - `application/` - Application services and workflows
  - `infrastructure/` - Data storage and external services
  - `web/` - Web interface and API
- `downloads/` - Temporary download location
- `complete/` - Root folder for all converted media
  - `complete/movies/` - Organized movie files
  - `complete/tv/` - Organized TV shows
  - `complete/music/` - Organized music files
- `config/` - Application configuration

## N8N Integration

NZB4 includes deep integration with [N8N](https://n8n.io/), a powerful workflow automation platform. This allows for:

### Pre-built Workflows

- **Media Job Status Notifications**: Get notified when jobs complete via email or webhooks
- **Media Content Detection**: Automatically detect and tag media metadata
- **Scheduled Downloads**: Set up recurring downloads at specific times
- **Custom Post-Processing**: Add your own processing steps after conversion

### Creating Custom Workflows

1. Access the N8N interface at `http://localhost:5678`
2. Create new workflows that interact with NZB4 through webhooks
3. Connect to external services like Slack, Discord, or your own applications
4. Trigger workflows on events like job completion, download progress, etc.

### Example: Media Processing Workflow

1. Detect when a new media file is added
2. Automatically fetch metadata from TMDB or OMDB
3. Convert to your preferred format
4. Organize into the correct folder
5. Send a notification when complete

## Security Features

NZB4 implements comprehensive security measures:

- **Input Validation**: Strict validation of all inputs to prevent injection attacks
- **Path Traversal Prevention**: Secure file handling to prevent unauthorized access
- **Resource Monitoring and Limiting**: Protection against resource exhaustion
- **File Upload Safeguards**: Content verification and size limitations
- **Authentication**: Optional user authentication for the web interface
- **HTTPS Support**: Secure communication with proper configuration

## Monitoring and Management

The web interface provides comprehensive monitoring tools:

- **Job Status Dashboard**: Real-time status of all conversion jobs
- **Disk Space Monitor**: Track storage usage and receive low space warnings
- **System Health**: Monitor CPU, memory, and network usage
- **Audit Logs**: Track all system actions for troubleshooting

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
- **Search Queries**: Automatically searches for content from free sources

## Customization

NZB4 is designed for extensive customization:

- **Conversion Options**: Control quality, format, and processing flags
- **Organization Rules**: Define custom rules for organizing media
- **Notification Templates**: Customize email and webhook notifications
- **N8N Workflows**: Build your own automation workflows
- **API Integration**: Integrate with your existing systems

## API

NZB4 provides a comprehensive RESTful API:

- **Job Management**: Create, monitor, and control conversion jobs
- **Media Library**: Browse and search your media library
- **System Management**: Configure and monitor the system
- **Webhook Integration**: Register webhooks for event notifications

## Web Interfaces

- **NZB4 Web UI**: http://localhost:8000
- **N8N Workflow Editor**: http://localhost:5678

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 