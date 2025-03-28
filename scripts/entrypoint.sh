#!/bin/bash
set -e

# Setup environment
export N8N_DATA_FOLDER=${N8N_DATA_FOLDER:-/data/n8n}
export DOWNLOADS_DIR=${DOWNLOADS_DIR:-/data/downloads}
export COMPLETE_DIR=${COMPLETE_DIR:-/data/complete}
export TEMP_DIR=${TEMP_DIR:-/data/temp}
export MOVIES_DIR=${MOVIES_DIR:-/data/complete/movies}
export TV_DIR=${TV_DIR:-/data/complete/tv}
export MUSIC_DIR=${MUSIC_DIR:-/data/complete/music}
export OTHER_DIR=${OTHER_DIR:-/data/complete/other}
export WEB_PORT=${WEB_PORT:-8000}
export N8N_PORT=${N8N_PORT:-5678}
export N8N_ENABLED=${N8N_ENABLED:-true}

# Create required directories
mkdir -p $DOWNLOADS_DIR $COMPLETE_DIR $TEMP_DIR $MOVIES_DIR $TV_DIR $MUSIC_DIR $OTHER_DIR $N8N_DATA_FOLDER

# Generate config if it doesn't exist
if [ ! -f /app/config.json ]; then
    echo "Generating default configuration..."
    cat > /app/config.json <<EOL
{
    "debug": false,
    "log_level": "INFO",
    "environment": "production",
    "temp_dir": "${TEMP_DIR}",
    "auto_clean_temp": true,
    "retention_days": 30,
    "ui_theme": "dark",
    "jobs_per_page": 20,
    "database": {
        "type": "sqlite",
        "path": "/data/nzb4.db"
    },
    "media": {
        "download_dir": "${DOWNLOADS_DIR}",
        "complete_dir": "${COMPLETE_DIR}",
        "movies_dir": "${MOVIES_DIR}",
        "tv_dir": "${TV_DIR}",
        "music_dir": "${MUSIC_DIR}",
        "other_dir": "${OTHER_DIR}",
        "min_disk_space_mb": 500,
        "default_output_format": "mp4",
        "default_video_quality": "high",
        "default_media_type": "movie",
        "keep_original_default": false,
        "concurrent_conversions": 2
    },
    "network": {
        "host": "0.0.0.0",
        "port": ${WEB_PORT},
        "base_url": "/",
        "ssl_enabled": false,
        "download_speed_limit_kb": 0,
        "max_connections": 10,
        "retry_attempts": 3,
        "connection_timeout": 30
    },
    "n8n": {
        "enabled": ${N8N_ENABLED},
        "data_dir": "${N8N_DATA_FOLDER}",
        "port": ${N8N_PORT},
        "install_type": "npm",
        "health_check_interval": 300
    }
}
EOL
fi

# Check what command to run
if [ "$1" = "app" ]; then
    echo "Starting NZB4 Web Application..."
    
    # Start N8N if enabled
    if [ "$N8N_ENABLED" = "true" ]; then
        echo "Starting N8N in background..."
        n8n start &
    fi
    
    # Start the web application
    python -m nzb4.web.app
    
elif [ "$1" = "n8n" ]; then
    echo "Starting N8N standalone..."
    n8n start
    
elif [ "$1" = "worker" ]; then
    echo "Starting NZB4 background worker..."
    python -m nzb4.worker
    
elif [ "$1" = "cli" ]; then
    shift
    echo "Running NZB4 CLI command: $@"
    python -m nzb4.cli "$@"
    
elif [ "$1" = "shell" ]; then
    echo "Starting interactive shell..."
    exec /bin/bash
    
else
    echo "Unknown command: $1"
    echo "Available commands: app, n8n, worker, cli, shell"
    exit 1
fi 