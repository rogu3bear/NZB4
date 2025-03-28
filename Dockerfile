FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, SABnzbd, FFmpeg, Transmission and other dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-sabyenc \
    python3-bs4 \
    par2 \
    unrar \
    unzip \
    ffmpeg \
    curl \
    git \
    transmission-cli \
    transmission-daemon \
    aria2 \
    yt-dlp \
    wget \
    jq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install sabnzbd requests beautifulsoup4 lxml pyyaml qbittorrent-api flask psutil

# Create app directory
WORKDIR /app

# Copy script and utils
COPY *.py /app/
COPY utils/ /app/utils/
COPY templates/ /app/templates/
COPY static/ /app/static/
RUN chmod +x /app/*.py

# Create directories
RUN mkdir -p /downloads /complete /config /nzb /torrents

# Set up configuration directories
RUN mkdir -p /config/sabnzbd /config/transmission

# Expose ports for SABnzbd, Transmission and web interface
EXPOSE 8080 9091 5000

# Set volumes
VOLUME ["/downloads", "/complete", "/config", "/nzb", "/torrents"]

# Create entrypoint script
RUN echo '#!/bin/bash\n\
# Start Transmission daemon in background\n\
mkdir -p /config/transmission\n\
transmission-daemon -g /config/transmission &\n\
\n\
# Set Transmission settings\n\
sleep 3\n\
SETTINGS="/config/transmission/settings.json"\n\
if [ -f "$SETTINGS" ]; then\n\
  service transmission-daemon stop\n\
  jq ".\"download-dir\" = \"/downloads\"" "$SETTINGS" > /tmp/settings.json\n\
  mv /tmp/settings.json "$SETTINGS"\n\
  service transmission-daemon start\n\
fi\n\
\n\
if [ "$1" = "sabnzbd" ]; then\n\
  sabnzbd -b 0 -f /config/sabnzbd\n\
elif [ "$1" = "convert" ]; then\n\
  shift\n\
  /app/media_converter.py "$@"\n\
elif [ "$1" = "webui" ]; then\n\
  python3 /app/web_interface.py\n\
else\n\
  exec "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

# Default command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["webui"] 