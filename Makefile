# NZB4 Universal Media Converter Makefile
# Provides simple commands for managing the application

.PHONY: help setup start stop restart status logs logs-flask logs-express build clean reset dev prod

# Default goal when running `make` without arguments
.DEFAULT_GOAL := help

# Determine OS for platform-specific settings
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    # Export user UID/GID for Linux
    export UID := $(shell id -u)
    export GID := $(shell id -g)
    PLATFORM := linux
else ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
else
    PLATFORM := other
endif

# Directories
COMPLETE_DIR := ./complete
DOWNLOADS_DIR := ./downloads

# Help command - lists all available commands with descriptions
help:
	@echo "NZB4 Universal Media Converter - Make Commands"
	@echo "=========================================="
	@echo
	@echo "Usage: make [command]"
	@echo
	@echo "Commands:"
	@echo "  setup       - Create required directories and set permissions"
	@echo "  start       - Start all services in detached mode"
	@echo "  stop        - Stop all services"
	@echo "  restart     - Restart all services"
	@echo "  status      - Show status of all services"
	@echo "  logs        - View all logs (press Ctrl+C to exit)"
	@echo "  logs-flask  - View Flask API logs only"
	@echo "  logs-express- View Express API logs only"
	@echo "  build       - Rebuild all containers"
	@echo "  clean       - Remove stopped containers and unused images"
	@echo "  reset       - Remove all containers, volumes, and reset directories"
	@echo "  dev         - Start services in development mode (with debug enabled)"
	@echo "  prod        - Start services in production mode"
	@echo "  help        - Show this help message"
	@echo
	@echo "Platform: $(PLATFORM)"
	@if [ "$(PLATFORM)" = "linux" ]; then \
		echo "UID: $(UID), GID: $(GID)"; \
	fi

# Setup command - create required directories and set permissions
setup:
	@echo "Setting up required directories..."
	@mkdir -p $(COMPLETE_DIR) $(DOWNLOADS_DIR)
	@mkdir -p $(COMPLETE_DIR)/movies $(COMPLETE_DIR)/tv $(COMPLETE_DIR)/music $(COMPLETE_DIR)/other
	@chmod 755 $(COMPLETE_DIR) $(DOWNLOADS_DIR)
	@echo "Setup complete!"

# Start services
start:
	@echo "Starting services in detached mode..."
	@docker-compose up -d
	@echo "Services started!"
	@echo "Flask API: http://localhost:5000"
	@echo "Express API: http://localhost:3000"

# Stop services
stop:
	@echo "Stopping services..."
	@docker-compose down
	@echo "Services stopped"

# Restart services
restart:
	@echo "Restarting services..."
	@docker-compose restart
	@echo "Services restarted"

# Show service status
status:
	@echo "Service status:"
	@docker-compose ps

# View all logs
logs:
	@echo "Viewing logs (press Ctrl+C to exit)..."
	@docker-compose logs -f

# View Flask API logs
logs-flask:
	@echo "Viewing Flask API logs (press Ctrl+C to exit)..."
	@docker-compose logs -f flask-api

# View Express API logs
logs-express:
	@echo "Viewing Express API logs (press Ctrl+C to exit)..."
	@docker-compose logs -f express-api

# Rebuild all containers
build:
	@echo "Building all containers..."
	@docker-compose build --no-cache
	@echo "Build complete"

# Clean up Docker resources
clean:
	@echo "Cleaning up Docker resources..."
	@docker-compose down --remove-orphans
	@docker image prune -f
	@echo "Cleanup complete"

# Reset everything
reset:
	@echo "WARNING: This will remove all containers, volumes, and reset directories."
	@read -p "Are you sure you want to proceed? (y/n) " answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		echo "Resetting everything..."; \
		docker-compose down -v --remove-orphans; \
		rm -rf $(COMPLETE_DIR) $(DOWNLOADS_DIR); \
		mkdir -p $(COMPLETE_DIR) $(DOWNLOADS_DIR); \
		mkdir -p $(COMPLETE_DIR)/movies $(COMPLETE_DIR)/tv $(COMPLETE_DIR)/music $(COMPLETE_DIR)/other; \
		chmod 755 $(COMPLETE_DIR) $(DOWNLOADS_DIR); \
		echo "Reset complete"; \
	else \
		echo "Reset cancelled"; \
	fi

# Start services in development mode with debug enabled
dev:
	@echo "Starting services in development mode..."
	@FLASK_DEBUG=1 docker-compose up -d
	@echo "Services started in development mode!"
	@echo "Flask API: http://localhost:5000"
	@echo "Express API: http://localhost:3000"

# Start services in production mode (explicit)
prod:
	@echo "Starting services in production mode..."
	@FLASK_DEBUG=0 docker-compose up -d
	@echo "Services started in production mode!"
	@echo "Flask API: http://localhost:5000"
	@echo "Express API: http://localhost:3000" 