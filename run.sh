#!/bin/bash
# Media Converter Helper Script
# Makes it easy to target specific output folders

# Default settings
CONTENT_NAME=""
CONTENT_TYPE="movie"  # Default type is movie
OUTPUT_FORMAT="mp4"   # Default output format
QUALITY="high"        # Default quality

# Help function
function show_help {
    echo "NZB4 - Universal Media Converter"
    echo "--------------------------------"
    echo "Usage: ./run.sh [options] \"content name or path\""
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE       Set content type (movie, tv, music, ebook)"
    echo "  -f, --format FORMAT   Set output format (mp4, mkv, mp3, etc.)"
    echo "  -q, --quality QUALITY Set quality (low, medium, high, ultra, original)"
    echo "  -k, --keep            Keep original files after conversion"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run.sh \"Movie Title\"                     # Convert movie with default settings"
    echo "  ./run.sh -t tv \"TV Show S01E01\"           # Convert TV episode"
    echo "  ./run.sh -t music -f mp3 \"Artist - Song\"  # Convert music to MP3"
    echo "  ./run.sh -f mkv -q ultra \"Movie Title\"    # Convert to MKV at ultra quality"
    echo ""
    echo "Docker Commands:"
    echo "  ./run.sh start          # Start NZB4 services"
    echo "  ./run.sh stop           # Stop NZB4 services"
    echo "  ./run.sh restart        # Restart NZB4 services"
    echo "  ./run.sh logs           # View logs"
    echo "  ./run.sh n8n            # Start N8N service only"
    echo ""
    echo "Web Interface: http://localhost:8000"
    echo "N8N Interface: http://localhost:5678"
}

# Docker service management functions
function start_services {
    docker-compose up -d
    echo "NZB4 services started!"
    echo "Web Interface: http://localhost:8000"
    echo "N8N Interface: http://localhost:5678"
}

function stop_services {
    docker-compose down
    echo "NZB4 services stopped!"
}

function show_logs {
    docker-compose logs -f
}

# Parse command-line arguments
KEEP_ORIGINAL=false
COMMAND_ARGS=""

# Check for service commands first
if [ "$1" == "start" ]; then
    start_services
    exit 0
elif [ "$1" == "stop" ]; then
    stop_services
    exit 0
elif [ "$1" == "restart" ]; then
    stop_services
    start_services
    exit 0
elif [ "$1" == "logs" ]; then
    show_logs
    exit 0
elif [ "$1" == "n8n" ]; then
    docker-compose exec nzb4 n8n
    exit 0
fi

# Parse content conversion options
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -t|--type)
            CONTENT_TYPE="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -q|--quality)
            QUALITY="$2"
            shift 2
            ;;
        -k|--keep)
            KEEP_ORIGINAL=true
            shift
            ;;
        *)
            CONTENT_NAME="$1"
            shift
            ;;
    esac
done

# Check if content name is provided
if [ -z "$CONTENT_NAME" ]; then
    echo "Error: No content name or path provided!"
    show_help
    exit 1
fi

# Build command arguments
COMMAND_ARGS="--type $CONTENT_TYPE --format $OUTPUT_FORMAT --quality $QUALITY"

if [ "$KEEP_ORIGINAL" == "true" ]; then
    COMMAND_ARGS="$COMMAND_ARGS --keep-original"
fi

# Make sure services are running
if ! docker-compose ps | grep -q "nzb4.*Up"; then
    echo "NZB4 services are not running. Starting..."
    start_services
fi

# Run the conversion
echo "Converting: $CONTENT_NAME"
echo "Type: $CONTENT_TYPE, Format: $OUTPUT_FORMAT, Quality: $QUALITY"
docker-compose exec nzb4 cli convert $COMMAND_ARGS "$CONTENT_NAME"

echo ""
echo "Job submitted! Track progress at http://localhost:8000" 