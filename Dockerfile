# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Debug: Show base image info
RUN echo "🚀 Starting Railway build..." && python --version && pip --version

# Install system dependencies for PostgreSQL
RUN echo "📦 Installing system dependencies..." && \
    apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* && \
    echo "✅ System dependencies installed"

# Set the working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Debug: Show requirements content
RUN echo "📋 Requirements content:" && cat requirements.txt

# Install Python dependencies
RUN echo "🐍 Installing Python dependencies..." && \
    pip install --no-cache-dir -r requirements.txt && \
    echo "✅ Python dependencies installed"

# Copy the rest of the application
COPY . .

# Make start script executable
RUN chmod +x start.sh && echo "📄 Start script made executable"

# Expose port (Railway will override this)
EXPOSE 8000

# Final debug message
RUN echo "🎉 Docker build completed successfully"

# Use the start script
CMD ["bash", "start.sh"]
