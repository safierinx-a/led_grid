FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY server/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for the web server
RUN pip install --no-cache-dir flask flask-socketio flask-cors python-dotenv

# Copy the rest of the application
COPY . .

# Expose ports
EXPOSE 5001
EXPOSE 5555

# Set environment variables
ENV PYTHONPATH=/app
ENV WEB_PORT=5001
ENV ZMQ_PORT=5555
ENV MQTT_HOST=mqtt
ENV MQTT_PORT=1883

# Run the server
CMD ["python", "-m", "server.pattern_server"] 