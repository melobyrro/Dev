FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Intel GPU + media processing
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gpg \
    ffmpeg \
    git \
    # Intel GPU compute runtime dependencies
    libigdgmm12 \
    # Build tools for PyAV and Python packages
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Add Intel GPU compute runtime repository
RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy client" | \
    tee /etc/apt/sources.list.d/intel-gpu-jammy.list

# Install Intel compute runtime
RUN apt-get update && apt-get install -y \
    intel-opencl-icd \
    intel-level-zero-gpu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

# Copy application code
COPY app/ /app/app/
COPY analytics/ /app/analytics/

# Create directory for temporary files
RUN mkdir -p /app/tmp

# Run worker
CMD ["python", "-m", "app.worker.main"]
