#!/bin/bash
# NZB4 Media Converter - Helper Script
# This script simplifies common operations for the NZB4 containerized application

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default directories
COMPLETE_DIR="./complete"
DOWNLOADS_DIR="./downloads"

# Detect OS for platform-specific adjustments
OS="$(uname -s)"
case "${OS}" in
    Linux*)     OS_TYPE=linux;;
    Darwin*)    OS_TYPE=macos;;
    CYGWIN*)    OS_TYPE=windows;;
    MINGW*)     OS_TYPE=windows;;
    *)          OS_TYPE=unknown
esac

# Banner function
show_banner() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "  NZB4 Universal Media Converter - Helper Script  "
    echo "=================================================="
    echo -e "${NC}"
}

# Help function
show_help() {
    echo -e "${GREEN}Available commands:${NC}"
    echo "  setup       - Create required directories and set permissions"
    echo "  start       - Start all services in detached mode"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  status      - Show status of all services"
    echo "  logs        - View logs (press Ctrl+C to exit)"
    echo "  logs-flask  - View logs for Flask API only"
    echo "  logs-express- View logs for Express API only"
    echo "  build       - Rebuild all containers"
    echo "  clean       - Remove stopped containers and unused images"
    echo "  reset       - Remove all containers, volumes, and reset directories"
    echo "  help        - Show this help message"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./run.sh setup"
    echo "  ./run.sh start"
    echo "  ./run.sh logs-flask"
    echo ""
}

# Setup function - create directories and set permissions
setup_directories() {
    echo -e "${BLUE}Setting up required directories...${NC}"
    
    # Create directories if they don't exist
    mkdir -p "$COMPLETE_DIR"
    mkdir -p "$DOWNLOADS_DIR"
    
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
    
    # Create subdirectories for better organization
    mkdir -p "$COMPLETE_DIR/movies" "$COMPLETE_DIR/tv" "$COMPLETE_DIR/music" "$COMPLETE_DIR/other"
    
    echo -e "${GREEN}Setup complete!${NC}"
}

# Check if Docker and Docker Compose are installed
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check for docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
        echo "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check for docker-compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${YELLOW}Warning: docker-compose not found. Checking Docker Compose plugin...${NC}"
        if ! docker compose version &> /dev/null; then
            echo -e "${RED}Error: Docker Compose not available${NC}"
            echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
            exit 1
        fi
        USE_DOCKER_COMPOSE_PLUGIN=true
        echo -e "${GREEN}Using Docker Compose plugin${NC}"
    else
        USE_DOCKER_COMPOSE_PLUGIN=false
        echo -e "${GREEN}Using docker-compose command${NC}"
    fi
    
    echo -e "${GREEN}All prerequisites are installed!${NC}"
}

# Run docker-compose with the appropriate command format
run_compose() {
    if [ "$USE_DOCKER_COMPOSE_PLUGIN" = true ]; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

# Main execution
show_banner

# Process command
case "$1" in
    setup)
        check_prerequisites
        setup_directories
        ;;
    start)
        check_prerequisites
        # Export UID/GID on Linux
        if [ "$OS_TYPE" = "linux" ]; then
            export UID=$(id -u)
            export GID=$(id -g)
        fi
        echo -e "${BLUE}Starting services...${NC}"
        run_compose up -d
        echo -e "${GREEN}Services started!${NC}"
        echo -e "${YELLOW}Flask API: http://localhost:5000${NC}"
        echo -e "${YELLOW}Express API: http://localhost:3000${NC}"
        ;;
    stop)
        echo -e "${BLUE}Stopping services...${NC}"
        run_compose down
        echo -e "${GREEN}Services stopped${NC}"
        ;;
    restart)
        echo -e "${BLUE}Restarting services...${NC}"
        run_compose restart
        echo -e "${GREEN}Services restarted${NC}"
        ;;
    status)
        echo -e "${BLUE}Checking service status...${NC}"
        run_compose ps
        ;;
    logs)
        echo -e "${BLUE}Viewing logs (Ctrl+C to exit)...${NC}"
        run_compose logs -f
        ;;
    logs-flask)
        echo -e "${BLUE}Viewing Flask API logs (Ctrl+C to exit)...${NC}"
        run_compose logs -f flask-api
        ;;
    logs-express)
        echo -e "${BLUE}Viewing Express API logs (Ctrl+C to exit)...${NC}"
        run_compose logs -f express-api
        ;;
    build)
        check_prerequisites
        # Export UID/GID on Linux
        if [ "$OS_TYPE" = "linux" ]; then
            export UID=$(id -u)
            export GID=$(id -g)
        fi
        echo -e "${BLUE}Building containers...${NC}"
        run_compose build --no-cache
        echo -e "${GREEN}Build complete${NC}"
        ;;
    clean)
        echo -e "${BLUE}Cleaning up Docker resources...${NC}"
        run_compose down --remove-orphans
        echo -e "${YELLOW}Removing dangling images...${NC}"
        docker image prune -f
        echo -e "${GREEN}Cleanup complete${NC}"
        ;;
    reset)
        echo -e "${RED}WARNING: This will remove all containers, volumes, and reset directories.${NC}"
        read -p "Are you sure you want to proceed? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Resetting everything...${NC}"
            run_compose down -v --remove-orphans
            echo -e "${YELLOW}Removing data directories...${NC}"
            rm -rf "$COMPLETE_DIR" "$DOWNLOADS_DIR"
            echo -e "${YELLOW}Setting up fresh directories...${NC}"
            setup_directories
            echo -e "${GREEN}Reset complete${NC}"
        fi
        ;;
    help|*)
        show_help
        ;;
esac 