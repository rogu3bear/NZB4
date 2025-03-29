#!/bin/bash
# NZB4 Universal Media Converter - Setup Script
# This script handles first-time setup of the NZB4 environment

set -e  # Exit on error

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "=================================================="
echo "  NZB4 Universal Media Converter - Setup Script   "
echo "=================================================="
echo -e "${NC}"

echo -e "${YELLOW}This script will set up your NZB4 environment for the first time.${NC}"
echo -e "It will:"
echo -e " - Check for required dependencies"
echo -e " - Create necessary directories"
echo -e " - Set appropriate permissions"
echo -e " - Configure environment settings"
echo -e " - Start the services"
echo ""

# Detect OS for platform-specific adjustments
OS="$(uname -s)"
case "${OS}" in
    Linux*)     OS_TYPE=linux;;
    Darwin*)    OS_TYPE=macos;;
    CYGWIN*)    OS_TYPE=windows;;
    MINGW*)     OS_TYPE=windows;;
    *)          OS_TYPE=unknown
esac

echo -e "${BLUE}Detected operating system: ${OS_TYPE}${NC}"
echo ""

# Step 1: Check dependencies
echo -e "${BLUE}Step 1: Checking dependencies...${NC}"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for Docker Compose
docker_compose_cmd="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}docker-compose command not found, checking for Docker Compose plugin...${NC}"
    if docker compose version &> /dev/null; then
        docker_compose_cmd="docker compose"
        echo -e "${GREEN}Docker Compose plugin found!${NC}"
    else
        echo -e "${RED}Error: Docker Compose not available${NC}"
        echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
fi

# Check if curl is installed (needed for health checks)
if ! command -v curl &> /dev/null; then
    echo -e "${YELLOW}Warning: curl is not installed. Some health checks may not work.${NC}"
fi

echo -e "${GREEN}All required dependencies are available.${NC}"
echo ""

# Step 2: Create directories
echo -e "${BLUE}Step 2: Creating directories...${NC}"

# Define directories
COMPLETE_DIR="./complete"
DOWNLOADS_DIR="./downloads"
DASHBOARD_DIR="./dashboard"

# Create main directories
mkdir -p "$COMPLETE_DIR" "$DOWNLOADS_DIR"

# Create subdirectories for better organization
mkdir -p "$COMPLETE_DIR/movies" "$COMPLETE_DIR/tv" "$COMPLETE_DIR/music" "$COMPLETE_DIR/other"

# Set permissions based on platform
if [ "$OS_TYPE" = "linux" ]; then
    echo -e "${YELLOW}Setting Linux permissions...${NC}"
    chmod 755 "$COMPLETE_DIR" "$DOWNLOADS_DIR"
    
    # Export current user UID/GID for docker-compose
    export UID=$(id -u)
    export GID=$(id -g)
    
    echo -e "${GREEN}Directories created with UID:$UID and GID:$GID${NC}"
elif [ "$OS_TYPE" = "macos" ]; then
    echo -e "${YELLOW}Setting macOS permissions...${NC}"
    chmod 755 "$COMPLETE_DIR" "$DOWNLOADS_DIR"
    echo -e "${GREEN}Directories created with default permissions${NC}"
    echo -e "${YELLOW}Note: On macOS, Docker Desktop manages permissions automatically${NC}"
else
    echo -e "${YELLOW}Setting generic permissions...${NC}"
    chmod 755 "$COMPLETE_DIR" "$DOWNLOADS_DIR"
    echo -e "${YELLOW}Note: You may need to adjust permissions manually for your OS${NC}"
fi

echo -e "${GREEN}Directories created successfully.${NC}"
echo ""

# Step 3: Copy over run.sh script and make it executable
echo -e "${BLUE}Step 3: Setting up helper scripts...${NC}"

# Ensure run.sh is executable
if [ -f "run.sh" ]; then
    chmod +x run.sh
    echo -e "${GREEN}Made run.sh executable.${NC}"
else
    echo -e "${YELLOW}Warning: run.sh not found in current directory.${NC}"
fi

# Make setup.sh executable (this script)
chmod +x "$0"

# Create simple dashboard launcher if it doesn't exist
if [ ! -f "dashboard.sh" ]; then
    cat > dashboard.sh << 'EOF'
#!/bin/bash
# Simple dashboard launcher
if [ -d "dashboard" ]; then
    echo "Opening dashboard in browser..."
    # Try different methods based on OS
    if command -v xdg-open &> /dev/null; then
        xdg-open dashboard/index.html
    elif command -v open &> /dev/null; then
        open dashboard/index.html
    elif command -v start &> /dev/null; then
        start dashboard/index.html
    else
        echo "Could not open browser automatically."
        echo "Please open dashboard/index.html manually in your browser."
    fi
else
    echo "Dashboard not found. Please run setup.sh first."
fi
EOF
    chmod +x dashboard.sh
    echo -e "${GREEN}Created dashboard.sh launcher.${NC}"
fi

echo -e "${GREEN}Helper scripts configured.${NC}"
echo ""

# Step 4: Build and start services
echo -e "${BLUE}Step 4: Building and starting services...${NC}"
echo -e "${YELLOW}This may take several minutes for the first build.${NC}"
echo ""

# Start services
if [ "$docker_compose_cmd" = "docker-compose" ]; then
    docker-compose up -d --build
else
    docker compose up -d --build
fi

echo -e "${GREEN}Services built and started!${NC}"
echo ""

# Step 5: Display summary and next steps
echo -e "${BLUE}Step 5: Setup complete!${NC}"
echo ""
echo -e "${GREEN}NZB4 Universal Media Converter has been set up successfully.${NC}"
echo ""
echo -e "You can manage your NZB4 installation with the following commands:"
echo -e "  ${YELLOW}./run.sh start${NC}    - Start all services"
echo -e "  ${YELLOW}./run.sh stop${NC}     - Stop all services"
echo -e "  ${YELLOW}./run.sh status${NC}   - Check service status"
echo -e "  ${YELLOW}./run.sh logs${NC}     - View logs"
echo -e "  ${YELLOW}./run.sh help${NC}     - Show all available commands"
echo ""
echo -e "Your NZB4 services are available at:"
echo -e "  ${YELLOW}Flask API:${NC}    http://localhost:5000"
echo -e "  ${YELLOW}Express API:${NC}  http://localhost:3000"
echo -e "  ${YELLOW}Dashboard:${NC}    file://$PWD/dashboard/index.html"
echo ""
echo -e "To open the dashboard, run: ${YELLOW}./dashboard.sh${NC}"
echo ""
echo -e "${BLUE}Thank you for using NZB4 Universal Media Converter!${NC}" 