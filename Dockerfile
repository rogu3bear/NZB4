FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV DEBIAN_FRONTEND=noninteractive
ENV APP_USER=nzb4
ENV APP_UID=1000
ENV APP_GID=1000
ENV APP_DIR=/app
ENV DATA_DIR=/data
ENV DIR_MODE=750

# Working directory
WORKDIR ${APP_DIR}

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

# Create non-root user and groups
RUN groupadd -g ${APP_GID} ${APP_USER} && \
    useradd -m -u ${APP_UID} -g ${APP_GID} -s /bin/bash ${APP_USER}

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p ${DATA_DIR}/downloads ${DATA_DIR}/complete ${DATA_DIR}/temp \
    ${DATA_DIR}/complete/movies ${DATA_DIR}/complete/tv ${DATA_DIR}/complete/music \
    ${DATA_DIR}/complete/other ${DATA_DIR}/n8n ${DATA_DIR}/db && \
    chown -R ${APP_USER}:${APP_USER} ${DATA_DIR} && \
    chmod -R ${DIR_MODE} ${DATA_DIR}

# Copy application code
COPY --chown=${APP_USER}:${APP_USER} . .

# Make sure scripts are executable
RUN chmod +x ${APP_DIR}/scripts/*.sh

# Switch to non-root user
USER ${APP_USER}

# Expose ports
# Web UI
EXPOSE 8000
# N8N
EXPOSE 5678

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint script
ENTRYPOINT ["scripts/entrypoint.sh"]

# Default command
CMD ["app"] 