FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for scapy/network scanning and pinging
RUN apt-get update && apt-get install -y \
    iputils-ping \
    arp-scan \
    nmap \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create directory for SQLite database
RUN mkdir -p /app/data

# Expose the API port (handled by docker-compose usually, but good practice)
EXPOSE 36912

# Run uvicorn server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "36912"]
