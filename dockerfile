FROM python:3.11-slim

# Install system dependencies for network scanning
RUN apt-get update && apt-get install -y \
    nmap \
    net-tools \
    iputils-ping \
    iproute2 \
    dnsutils \
    samba-common-bin \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Run the application
CMD ["sh", "-c", "gunicorn --worker-class eventlet -w 1 --bind ${HOST:-0.0.0.0}:${PORT:-5000} app:app"]