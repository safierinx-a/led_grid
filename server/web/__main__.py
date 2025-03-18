#!/usr/bin/env python3

"""
LED Grid Web Server

This script starts the web server for the LED Grid dashboard.
"""

import os
import sys
from flask_socketio import SocketIO
import ssl

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

    # Get SSL configuration from environment
    ssl_cert = os.environ.get("SSL_CERT")
    ssl_key = os.environ.get("SSL_KEY")
    use_https = (
        ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key)
    )

    # Configure SSL context if using HTTPS
    ssl_context = None
    if use_https:
        print(f"HTTPS enabled with certificate: {ssl_cert}")
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(ssl_cert, ssl_key)
    else:
        print("HTTPS not enabled. Using HTTP only.")
        print("To enable HTTPS, set SSL_CERT and SSL_KEY environment variables.")

    # Start web server
    print(f"Starting {'HTTPS' if use_https else 'HTTP'} web server on port {port}...")
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        ssl_context=ssl_context,
    )


if __name__ == "__main__":
    main()
