# Minimal, fast Dockerfile for Railway
FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install system dependencies quietly
RUN apk add --no-cache gcc musl-dev postgresql-dev --quiet

# Copy and install Python requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --quiet -r requirements.txt

# Copy application code
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Railway will set PORT automatically
EXPOSE 8000

# Start with sh (Alpine doesn't have bash by default)
CMD ["sh", "start.sh"]
