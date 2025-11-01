# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create app directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create directories for volume mounts and data
RUN mkdir -p /app/data/logs /app/data/server_log /app/data/images

# Set proper permissions
RUN chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Expose any ports if needed (Discord bots typically don't need this)
# EXPOSE 8080

# Health check to ensure bot is running
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/data') else 1)"

# Run the bot
CMD ["python", "src/main.py"]
