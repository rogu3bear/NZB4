# NZB4 - Universal Media Converter

A comprehensive media conversion system with support for various file formats and sources, built with a focus on security, reliability, and maintainability.

![NZB4 Logo](https://via.placeholder.com/800x200/3498db/ffffff?text=NZB4+Universal+Media+Converter)

## Features

- **Multi-format Media Conversion**: Convert NZB files, torrents, direct video files and more to standardized video formats (MP4/MOV)
- **Dual API Implementation**:
  - Python Flask API with robust error handling and input validation
  - TypeScript Express.js API with type safety and modern web security features
- **Security Features**:
  - Input validation and sanitization
  - Path traversal prevention
  - Rate limiting
  - Sanitized error responses
  - Request ID tracking for traceability
- **Containerized Architecture**:
  - Modular container system
  - Consistent volume mappings
  - Environment-based configuration
  - Multi-stage Docker builds for smaller images
  - Health checks for all services
- **User Experience**:
  - Web-based dashboard for management
  - Visual service status indicators
  - One-click service control
  - Integrated log viewer

## Quick Start

The quickest way to get started with NZB4 is by using the provided setup script:

```bash
# Clone the repository
git clone https://github.com/yourusername/NZB4.git
cd NZB4

# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

The setup script will:
1. Check for required dependencies (Docker and Docker Compose)
2. Create necessary directories with appropriate permissions
3. Build and start the containers
4. Provide you with access URLs and next steps

After setup, you can open the dashboard:

```bash
./dashboard.sh
```

## Container Architecture

NZB4 uses a modular container architecture:

- **Flask API Container**: Handles Python-based API requests for media conversion
- **Express API Container**: Provides TypeScript-based API for web applications

All user data is stored in mapped volumes:
- `./complete`: Stores converted media files
- `./downloads`: Temporary storage for downloaded content

## Directory Structure

```
NZB4/
├── app.py                   # Flask API implementation
├── server.ts                # Express.js TypeScript implementation
├── Dockerfile.flask         # Multi-stage Dockerfile for Flask API
├── Dockerfile.express       # Multi-stage Dockerfile for Express API
├── docker-compose.yml       # Service orchestration
├── setup.sh                 # One-click setup script
├── run.sh                   # Helper script for common operations
├── dashboard.sh             # Dashboard launcher
├── Makefile                 # Optional: Make targets for common tasks
├── dashboard/               # Web-based management dashboard
├── complete/                # Volume: Completed media files
│   ├── movies/              # Organized by media type
│   ├── tv/
│   ├── music/
│   └── other/
└── downloads/               # Volume: Temporary download location
```

## Permission Management

NZB4 is designed to minimize permission issues across platforms:

- **Linux**: Containers run as a non-root user with the same UID/GID as the host user
- **macOS/Windows**: Uses Docker Desktop's built-in permission handling

The setup script and helper scripts automatically handle the appropriate permissions for your platform.

## Managing Your NZB4 Installation

### Using the Dashboard

The web dashboard provides an intuitive interface for:
- Monitoring service status
- Starting, stopping, and restarting services
- Viewing logs in real-time
- Accessing API endpoints

### Using Helper Scripts

The `run.sh` script provides command-line access to common operations:

```bash
# Show available commands
./run.sh help

# Start all services
./run.sh start

# Stop all services
./run.sh stop

# Show service status
./run.sh status

# View logs
./run.sh logs

# View logs for a specific service
./run.sh logs-flask
./run.sh logs-express

# Reset everything (be careful!)
./run.sh reset
```

### Using Makefile (Alternative)

If you prefer `make` commands, you can use these instead:

```bash
# Show available commands
make help

# Start all services
make start

# Start in development mode
make dev

# Other commands
make stop
make restart
make logs
make reset
```

## API Documentation

Both APIs expose the same endpoints:

### GET /status

Returns the current status of the API.

**Response:**
```json
{
  "status": "operational",
  "version": "1.0.0",
  "output_dir": "/complete",
  "download_dir": "/downloads"
}
```

### POST /convert

Converts media from a source path to the specified format.

**Request Body:**
```json
{
  "source_path": "/path/to/file.nzb",
  "target_format": "mp4"
}
```

**Response:**
```json
{
  "message": "Conversion successful",
  "output": "/complete/movies/my_video.mp4",
  "format": "mp4",
  "processing_time": "5.23s",
  "request_id": "a1b2c3d4"
}
```

## Cross-Platform Compatibility

NZB4 has been tested and works on:

- **Linux**: Ubuntu 20.04+, Debian 10+, CentOS 8+
- **macOS**: macOS 10.15+ (Catalina), macOS 11+ (Big Sur), macOS 12+ (Monterey)
- **Windows**: Windows 10, Windows 11 with Docker Desktop

## Troubleshooting

### Common Issues

**Permission Errors**:
- On Linux, run `UID=$(id -u) GID=$(id -g) docker-compose up -d`
- On macOS/Windows, ensure Docker Desktop has permission to access the relevant folders

**Port Conflicts**:
- Edit the `docker-compose.yml` file to change the port mappings if ports 5000 or 3000 are already in use

**For more help**:
- Check the logs: `./run.sh logs`
- Look at the FAQ in the [documentation](docs/README.md)
- Submit an issue on GitHub

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 