#!/usr/bin/env python3

"""
LED Grid Web Server

This script starts the web server for the LED Grid dashboard.
"""

import os
import sys
from flask_socketio import SocketIO

# Add the parent directory to the path so we can import server modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from server.config.grid_config import DEFAULT_CONFIG
from server.core.server import LEDServer
from server.web import create_app, socketio


def main():
    """Main entry point for the web server"""
    print("\n=== Starting LED Grid Web Server ===")

    # Create LED server
    led_server = LEDServer(DEFAULT_CONFIG)

    # Start LED server components
    print("Starting LED server components...")
    led_server.start()

    # Create Flask app
    app = create_app(led_server)

    # Get port from environment or use default
    port = int(os.environ.get("WEB_PORT", 5001))

    # Start web server
    print(f"Starting web server on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
