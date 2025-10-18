# Use Python 3.13 slim image
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    C_FORCE_ROOT=true

# Set work directory
WORKDIR /app

# Install system dependencies including supervisor for multi-process management
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create staticfiles directory with proper permissions
RUN mkdir -p /app/staticfiles

# Create start script that collects static files at runtime
COPY --chown=appuser:appuser start.sh /app/start.sh

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app \
    && chmod +x /app/start.sh

USER appuser

# Expose port (Railway will override this with PORT env var)
EXPOSE 8080

# Run start script
CMD ["/app/start.sh"]
