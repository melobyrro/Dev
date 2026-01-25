# Tracker Monitor Dockerfile
# Alpine Linux + Python 3.11 for minimal image size

FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for compiled Python packages)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY reddit_monitor.py .
COPY keyword_matcher.py .
COPY state_manager.py .
COPY notifier.py .
COPY config_loader.py .
COPY api.py .
COPY language_extractor.py .

# Create data directory for SQLite database
RUN mkdir -p /app/data && chmod 777 /app/data

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Health check (verify app can start)
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s \
    CMD python -c "import sys; sys.exit(0)"

# Run the application
CMD ["python", "-u", "app.py"]
