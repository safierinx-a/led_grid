#!/usr/bin/env python3
"""
Test script for the Python LED controller
Runs the controller with mock hardware and prints detailed logs
"""

import os
import sys
import logging
import websocket

# Enable websocket detailed logging
websocket.enableTrace(True)

# Set up environment variables for testing
# Update to use local IP (192.168.1.5 instead of 192.168.1.11)
os.environ["LEGRID_SERVER_URL"] = "ws://192.168.1.5:4000/controller/websocket"
os.environ["LEGRID_LOG_LEVEL"] = "DEBUG"
os.environ["LEGRID_WIDTH"] = "25"
os.environ["LEGRID_HEIGHT"] = "24"
os.environ["LEGRID_LED_COUNT"] = "600"
os.environ["LEGRID_LAYOUT"] = "serpentine"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set all loggers to DEBUG level
for logger_name in ["websocket", "legrid-controller"]:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

print("=" * 60)
print("LED GRID CONTROLLER TEST")
print("=" * 60)
print(f"Server URL: {os.environ['LEGRID_SERVER_URL']}")
print(
    f"Grid: {os.environ['LEGRID_WIDTH']}x{os.environ['LEGRID_HEIGHT']} ({os.environ['LEGRID_LED_COUNT']} LEDs)"
)
print(f"Layout: {os.environ['LEGRID_LAYOUT']}")
print("=" * 60)

# Import and run the controller
from main import LegridController

if __name__ == "__main__":
    print("Starting LED Grid Controller in mock mode for testing...")
    controller = LegridController()
    try:
        controller.start()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during test: {e}")
    finally:
        print("Test completed")
