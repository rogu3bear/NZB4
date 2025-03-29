#!/bin/bash
set -e

# Default values if not set in environment
APP_USER=${APP_USER:-nzb4}
APP_UID=${APP_UID:-1000}
APP_GID=${APP_GID:-1000}
APP_DIR=${APP_DIR:-/app}
DATA_DIR=${DATA_DIR:-/data}
DIR_MODE=${DIR_MODE:-750}

# Function to set up data directory permissions
setup_permissions() {
    echo "Setting up permissions for data directories..."
    
    # Create required directories if they don't exist
    mkdir -p ${DATA_DIR}/downloads
    mkdir -p ${DATA_DIR}/complete
    mkdir -p ${DATA_DIR}/complete/movies
    mkdir -p ${DATA_DIR}/complete/tv
    mkdir -p ${DATA_DIR}/complete/music
    mkdir -p ${DATA_DIR}/complete/other
    mkdir -p ${DATA_DIR}/temp
    mkdir -p ${DATA_DIR}/n8n
    mkdir -p ${DATA_DIR}/db
    
    # Ensure directories have the correct ownership and permissions
    chown -R ${APP_USER}:${APP_USER} ${DATA_DIR}
    chmod -R ${DIR_MODE} ${DATA_DIR}
    
    echo "Permissions setup complete"
}

# Function to initialize the database
init_database() {
    echo "Initializing database..."
    
    if [ ! -f "${DATA_DIR}/db/nzb4.db" ]; then
        echo "Creating new database..."
        python -m nzb4.application.database.init_db
    else
        echo "Database already exists, checking for migrations..."
        python -m nzb4.application.database.migrate_db
    fi
    
    echo "Database initialization complete"
}

# Generate a random key for the application
generate_app_key() {
    if [ ! -f "${DATA_DIR}/app_key.txt" ]; then
        echo "Generating new application key..."
        openssl rand -hex 32 > "${DATA_DIR}/app_key.txt"
        chown ${APP_USER}:${APP_USER} "${DATA_DIR}/app_key.txt"
        chmod 600 "${DATA_DIR}/app_key.txt"
    fi
    
    export APP_KEY=$(cat "${DATA_DIR}/app_key.txt")
    echo "Application key configured"
}

# Health check function
health_check() {
    # Wait for services to start
    sleep 5
    
    # Check if web server is running
    for i in {1..12}; do
        if curl -s http://localhost:8000/health > /dev/null; then
            echo "Web server is healthy"
            return 0
        fi
        echo "Waiting for web server to start... ($i/12)"
        sleep 5
    done
    
    echo "Web server health check failed"
    return 1
}

# Function to start the main application
start_app() {
    echo "Starting NZB4 application..."
    cd ${APP_DIR}
    
    # Apply database migrations if needed
    python -m nzb4.application.database.migrate_db
    
    # Start the web server
    # Using gunicorn for production
    gunicorn -w 4 -b 0.0.0.0:8000 --access-logfile - --error-logfile - nzb4.application.web.wsgi:app
}

# Function to start N8N
start_n8n() {
    echo "Starting N8N service..."
    cd ${DATA_DIR}/n8n
    
    # Export N8N environment variables
    export N8N_USER_FOLDER="${DATA_DIR}/n8n"
    
    # Run N8N in the background
    n8n start &
    
    # Wait for N8N to start
    for i in {1..12}; do
        if curl -s http://localhost:5678/healthz > /dev/null; then
            echo "N8N service is healthy"
            break
        fi
        echo "Waiting for N8N to start... ($i/12)"
        sleep 5
    done
}

# Ensure secure file permissions for mounted volumes
init_secure_environment() {
    # Set up timezone
    if [ ! -z "$TZ" ]; then
        ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
    fi
    
    # Create a secure temporary directory
    if [ -d "/tmp" ]; then
        chmod 1777 /tmp
    fi
    
    # Set umask for new files
    umask 027
    
    # Ensure proper permissions for sensitive files
    find ${APP_DIR} -name "*.py" -exec chmod 640 {} \;
    find ${APP_DIR} -name "*.sh" -exec chmod 750 {} \;
    
    echo "Secure environment initialized"
}

# Main execution logic
main() {
    # Check if running as root and do initial setup
    if [ "$(id -u)" = "0" ]; then
        echo "Running as root, performing initial setup..."
        
        # Initialize secure environment
        init_secure_environment
        
        # Set up directories and permissions
        setup_permissions
        
        # Generate application key
        generate_app_key
        
        # Drop privileges and re-exec the entrypoint script
        echo "Switching to user ${APP_USER}..."
        exec su-exec ${APP_USER} "$0" "$@"
    else
        # Running as non-root user
        echo "Running as non-root user: $(id -un)"
    fi
    
    # Initialize database
    init_database
    
    # Determine what to start based on command
    case "$1" in
        app)
            start_app
            ;;
        n8n)
            start_n8n
            ;;
        both)
            start_n8n &
            start_app
            ;;
        debug)
            echo "Starting in debug mode..."
            cd ${APP_DIR}
            python -m nzb4.application.web.app
            ;;
        health)
            health_check
            ;;
        bash|sh)
            exec /bin/bash
            ;;
        *)
            echo "Unknown command: $1"
            echo "Available commands: app, n8n, both, debug, health, bash"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 