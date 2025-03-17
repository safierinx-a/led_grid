"""
Web server module for LED Grid control dashboard.

This module provides a web interface for controlling the LED Grid,
including pattern selection, parameter adjustment, and interactive
pixel-level control.
"""

from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
import os
import json
from pathlib import Path

# Create Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")

# Enable CORS for all routes
CORS(app)

# Configure SocketIO with async mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Store reference to LED server
led_server = None


def create_app(server):
    """
    Create and configure the Flask application.

    Args:
        server: The LEDServer instance to use for LED control

    Returns:
        The configured Flask app
    """
    global led_server
    led_server = server

    # Configure app
    app.config["SECRET_KEY"] = os.getenv(
        "FLASK_SECRET_KEY", "dev_key_change_in_production"
    )

    # Import routes after app is created to avoid circular imports
    import server.web.routes

    print("LED Grid web dashboard initialized")
    return app
