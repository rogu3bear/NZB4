#!/bin/bash
# Media Converter Helper Script
# Makes it easy to target specific output folders

# Usage information
function show_usage {
  echo "Usage: $0 <media> [folder_type] [format]"
  echo ""
  echo "Arguments:"
  echo "  media        Media to convert (file path, URL, or search term)"
  echo "  folder_type  Optional: Target folder type (movies, tv, music)"
  echo "  format       Optional: Output format (mp4, mov) - default: mp4"
  echo ""
  echo "Examples:"
  echo "  $0 \"Movie Name\" movies      # Puts in movies folder"
  echo "  $0 \"TV Show Name\" tv        # Puts in TV folder"
  echo "  $0 /nzb/file.nzb movies mov  # Convert NZB to MOV in movies folder"
  echo "  $0 \"https://youtube.com/watch?v=xxxx\" music  # Download to music folder"
  exit 1
}

# Check for at least one argument
if [ $# -lt 1 ]; then
  show_usage
fi

MEDIA="$1"
FOLDER_TYPE="${2:-default}"
FORMAT="${3:-mp4}"

# Determine output path based on folder type
case "$FOLDER_TYPE" in
  movies|movie)
    OUTPUT_PATH="/media/movies"
    ;;
  tv|tvshow|tvshows|series)
    OUTPUT_PATH="/media/tv"
    ;;
  music|audio|songs)
    OUTPUT_PATH="/media/music"
    ;;
  *)
    OUTPUT_PATH="/complete"
    ;;
esac

# Create the target directory if needed
mkdir -p "./complete"
mkdir -p "./complete/movies"
mkdir -p "./complete/tv"
mkdir -p "./complete/music"

# Check if media is a local file
if [ -f "$MEDIA" ]; then
  # Using the file directly
  echo "Converting file: $MEDIA to $OUTPUT_PATH"
  docker-compose exec media-converter convert -o "$OUTPUT_PATH" -f "$FORMAT" "$MEDIA"
else
  # Assuming it's a URL or search term
  echo "Converting: '$MEDIA' to $OUTPUT_PATH"
  docker-compose exec media-converter convert -o "$OUTPUT_PATH" -f "$FORMAT" "$MEDIA"
fi 