#!/usr/bin/env python3
import os
import sys
import time
import signal
import logging
import argparse
from typing import Dict

# Local module imports
from config import Config
from hardware import create_hardware, MockHardware
from frame import FrameProcessor
from connection import ConnectionManager


class LegridController:
    """Main controller application class"""

    def __init__(self, config_file=None):
        # Load configuration
        self.config = Config.load(config_file)

        # Set up logging
        self.logger = Config.setup_logging(self.config["log_level"])
        self.logger.info("Legrid Controller starting...")

        # Extract config values
        self.width = self.config["width"]
        self.height = self.config["height"]
        self.led_count = self.config["led_count"]
        self.server_url = self.config["server_url"]
        self.layout = self.config["layout"]
        self.flip_x = self.config["flip_x"]
        self.flip_y = self.config["flip_y"]
        self.transpose = self.config["transpose"]

        # Print configuration
        self.logger.info(
            f"Grid configuration: {self.width}x{self.height}, {self.led_count} LEDs"
        )
        self.logger.info(
            f"Layout: {self.layout}, flip_x={self.flip_x}, flip_y={self.flip_y}, transpose={self.transpose}"
        )
        self.logger.info(f"Server URL: {self.server_url}")

        # Initialize components
        self.running = True
        self.hardware = None
        self.frame_processor = None
        self.connection = None

        # Set up signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def initialize(self):
        """Initialize all controller components"""
        self.logger.info("Initializing controller components...")

        # Initialize hardware first
        self.hardware = create_hardware(self.config)

        # Initialize frame processor
        self.frame_processor = FrameProcessor(
            width=self.width,
            height=self.height,
            layout=self.layout,
            flip_x=self.flip_x,
            flip_y=self.flip_y,
            transpose=self.transpose,
        )

        # Initialize connection manager
        self.connection = ConnectionManager(
            server_url=self.server_url,
            on_frame_callback=self._process_frame,
            config=self.config,
        )

        # Add grid configuration to connection for stats reporting
        self.connection.width = self.width
        self.connection.height = self.height
        self.connection.layout = self.layout
        self.connection.flip_x = self.flip_x
        self.connection.flip_y = self.flip_y
        self.connection.transpose = self.transpose
        self.connection.is_hardware_available = not isinstance(
            self.hardware, MockHardware
        )

        # Clear the display
        self.hardware.clear()

        return True

    def start(self):
        """Start the controller and connect to the server"""
        if not self.initialize():
            self.logger.error("Failed to initialize controller components")
            return False

        # Connect to the server
        self.logger.info("Connecting to server...")
        self.connection.connect()

        # Main loop
        try:
            self.logger.info("Controller running. Press Ctrl+C to exit.")
            while self.running:
                # Main thread just keeps the program alive
                # Actual work is done in callback methods and other threads
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.cleanup()

        return True

    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up...")

        if self.hardware:
            self.hardware.clear()
            self.hardware.cleanup()

        if self.connection:
            self.connection.disconnect()

        self.logger.info("Controller shutdown complete")

    def _process_frame(self, binary_data):
        """Process an incoming binary frame"""
        try:
            # Convert binary data to Frame object
            frame = self.frame_processor.process_binary_frame(binary_data)
            if not frame:
                self.logger.warning("Failed to process frame data")
                return

            # Map logical frame to physical LED layout
            physical_pixels = self.frame_processor.map_led_layout(frame)

            # Update the hardware
            self._update_leds(physical_pixels)

        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")

    def _update_leds(self, pixels):
        """Update the physical LEDs with pixel data"""
        if not pixels:
            return

        # Set each pixel
        for i, (r, g, b) in enumerate(pixels):
            if i < self.hardware.led_count:
                self.hardware.set_pixel(i, r, g, b)

        # Show the updated pixels
        self.hardware.show()

    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        self.logger.info(f"Received signal {sig}")
        self.running = False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Legrid LED Controller")

    parser.add_argument("--config", type=str, help="Path to configuration file")

    parser.add_argument("--width", type=int, help="Grid width")

    parser.add_argument("--height", type=int, help="Grid height")

    parser.add_argument("--led-count", type=int, help="Number of LEDs")

    parser.add_argument("--led-pin", type=int, help="GPIO pin for LED data")

    parser.add_argument("--brightness", type=int, help="LED brightness (0-255)")

    parser.add_argument("--server-url", type=str, help="WebSocket server URL")

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    parser.add_argument(
        "--layout",
        type=str,
        choices=["linear", "serpentine"],
        help="LED strip layout pattern",
    )

    parser.add_argument("--flip-x", action="store_true", help="Flip grid horizontally")

    parser.add_argument("--flip-y", action="store_true", help="Flip grid vertically")

    parser.add_argument(
        "--transpose", action="store_true", help="Transpose grid (swap X and Y axes)"
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Convert args to config dict
    config_file = args.config

    # Command-line args override config file
    config_updates = {}
    for key, value in vars(args).items():
        if value is not None and key != "config":
            # Convert arg names to config keys
            config_key = key.replace("-", "_")
            config_updates[config_key] = value

    # Set environment variables for args
    for key, value in config_updates.items():
        os.environ[f"LEGRID_{key.upper()}"] = str(value)

    # Create and start controller
    controller = LegridController(config_file)
    return 0 if controller.start() else 1


if __name__ == "__main__":
    sys.exit(main())
