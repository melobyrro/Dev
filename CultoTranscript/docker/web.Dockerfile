# Stage 1: Build React UI
FROM node:20-slim AS ui-builder

WORKDIR /ui

# Copy package files
COPY UI/package*.json ./

# Install dependencies
RUN npm ci

# Copy UI source
COPY UI/ ./

# Build the React app
RUN npm run build

# Stage 2: Python application
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copy application code
COPY app/ /app/app/
COPY Backend/ /app/Backend/
COPY migrations/ /app/migrations/
COPY shared/ /app/shared/

# Copy built React UI from builder stage
COPY --from=ui-builder /ui/dist /app/ui-dist

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
