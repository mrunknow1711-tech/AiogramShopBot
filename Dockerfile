# ============================================
# RAILWAY-OPTIMIZED DOCKERFILE
# ============================================

# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Optional: Install SQLCipher for encrypted database
# Uncomment if using DB_ENCRYPTION=true
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     sqlcipher \
#     libsqlcipher-dev \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Optional: Install SQLCipher Python package if needed
# Uncomment if using DB_ENCRYPTION=true
# RUN pip install --no-cache-dir sqlcipher3

# Copy application code
COPY . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Railway will set PORT automatically
# But we expose common ports just in case
EXPOSE 8000

# Health check endpoint (optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Run the bot
CMD ["python", "run.py"]

# ============================================
# RAILWAY DEPLOYMENT NOTES
# ============================================
# 1. Railway automatically detects this Dockerfile
# 2. Set environment variables in Railway Dashboard
# 3. Railway provides:
#    - Automatic PORT assignment
#    - HTTPS with SSL certificate
#    - Public URL for webhooks
# 4. No ngrok needed!
