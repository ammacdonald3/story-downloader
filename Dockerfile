# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Install system dependencies required for Pillow
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -u 1000 -m appuser

# Set up application directory
WORKDIR /story-downloader
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create data directories and set permissions
RUN mkdir -p app/data/epubs app/data/logs && \
    chown -R appuser:appuser /story-downloader

# Switch to non-root user
USER appuser

# Set environment variables
ENV FLASK_APP=app
ENV FLASK_ENV=production

# Expose port
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0"]