# Universal Media Converter for macOS

This is the macOS-specific distribution of the Universal Media Converter, providing a native macOS application experience with integrated Docker management.

## Features

- Native macOS application bundle
- Automatic Docker installation and management
- GUI launcher with server controls
- Complete NZB and media conversion capabilities

## Prerequisites

- macOS 10.14 or newer
- Python 3.7 or newer
- Internet connection for Docker installation (if not already installed)

## Installation

### Option 1: Run the app directly

1. Download the latest release from the GitHub releases page
2. Double-click the `.app` file to run it
3. When prompted, allow the application to install dependencies if needed

### Option 2: Build from source

1. Clone this repository
2. Make sure you have Python 3.7+ installed
3. Run the build script: `./build_macos_app.sh`
4. Find the app in the `dist` directory

## Using Docker

The application will automatically detect if Docker is installed on your system. If not, it can install Docker for you using Homebrew and Colima (a lightweight Docker Desktop alternative).

### Docker Installation Process

When you choose to install Docker through the application:

1. Homebrew will be used to install the necessary packages
2. Docker CLI and Docker Compose will be installed
3. Colima will be installed and configured as the Docker backend
4. The application will verify the installation and start Docker

### Manual Docker Installation

If you prefer to install Docker manually:

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker CLI and Docker Compose
brew install docker docker-compose

# Install Colima (Docker backend)
brew install colima

# Start Colima
colima start
```

## Troubleshooting

If you encounter any issues:

1. Check Docker status in the Docker Management section
2. Verify that directories have the correct permissions
3. Check the application logs for detailed error messages

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 