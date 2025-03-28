FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV DEBIAN_FRONTEND=noninteractive

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    transmission-cli \
    wget \
    curl \
    netcat \
    unzip \
    p7zip-full \
    sqlite3 \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install n8n globally
RUN npm install -g n8n

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /data/downloads /data/complete /data/temp /data/complete/movies /data/complete/tv /data/complete/music /data/complete/other /data/n8n

# Make sure scripts are executable
RUN chmod +x /app/scripts/*.sh

# Run setup script
RUN python -m nzb4.scripts.setup

# Expose ports
# Web UI
EXPOSE 8000
# N8N
EXPOSE 5678

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint script
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Default command
CMD ["app"] 