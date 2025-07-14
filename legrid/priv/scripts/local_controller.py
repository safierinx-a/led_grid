#!/usr/bin/env python3
"""
Local LED Controller for Same-Machine Deployment

This script runs as a subprocess of the Elixir server and communicates
directly via stdin/stdout, eliminating WebSocket overhead.
"""

import sys
import time
import struct
import signal
import logging
import argparse
from typing import Dict, Tuple, List

# Add the py_controller directory to the path
sys.path.insert(0, "../../py_controller")

from hardware import create_hardware, MockHardware
from frame import FrameProcessor


class LocalLEDController:
    """Local LED controller that communicates via stdin/stdout"""

    def __init__(self, width: int, height: int, led_pin: int, led_count: int):
        self.width = width
        self.height = height
        self.led_pin = led_pin
        self.led_count = led_count

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("local-controller")

        # Initialize components
        self.running = True
        self.hardware = None
        self.frame_processor = None

        # Statistics
        self.frames_processed = 0
        self.last_frame_time = time.time()
        self.fps = 0.0

        # Set up signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info(
            f"Local LED Controller starting: {width}x{height}, {led_count} LEDs on pin {led_pin}"
        )

    def initialize(self):
        """Initialize hardware and frame processor"""
        try:
            # Create hardware interface
            config = {
                "width": self.width,
                "height": self.height,
                "led_count": self.led_count,
                "led_pin": self.led_pin,
                "brightness": 255,
                "layout": "serpentine",
                "flip_x": False,
                "flip_y": False,
                "transpose": False,
            }

            self.hardware = create_hardware(config)

            # Initialize frame processor
            self.frame_processor = FrameProcessor(
                width=self.width,
                height=self.height,
                layout="serpentine",
                flip_x=False,
                flip_y=False,
                transpose=False,
            )

            # Clear the display
            self.hardware.clear()

            self.logger.info("Local controller initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize controller: {e}")
            return False

    def run(self):
        """Main run loop - read frames from stdin and display them"""
        if not self.initialize():
            return False

        self.logger.info("Local controller running. Reading frames from stdin...")

        try:
            while self.running:
                # Read frame data from stdin
                frame_data = self._read_frame()
                if frame_data is None:
                    continue

                # Process and display the frame
                self._process_frame(frame_data)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()

        return True

    def _read_frame(self) -> bytes:
        """Read frame data from stdin"""
        try:
            # Read frame length (4 bytes, little-endian)
            length_bytes = sys.stdin.buffer.read(4)
            if not length_bytes or len(length_bytes) < 4:
                return None

            frame_length = struct.unpack("<I", length_bytes)[0]

            # Read frame data
            frame_data = sys.stdin.buffer.read(frame_length)
            if not frame_data or len(frame_data) < frame_length:
                return None

            return frame_data

        except Exception as e:
            self.logger.error(f"Error reading frame: {e}")
            return None

    def _process_frame(self, frame_data: bytes):
        """Process a frame and update the LEDs"""
        try:
            # Convert binary data to Frame object
            frame = self.frame_processor.process_binary_frame(frame_data)
            if not frame:
                return

            # Map logical frame to physical LED layout
            physical_pixels = self.frame_processor.map_led_layout(frame)

            # Update the hardware
            self._update_leds(physical_pixels)

            # Update statistics
            self._update_stats()

        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")

    def _update_leds(self, pixels: List[Tuple[int, int, int]]):
        """Update the physical LEDs with pixel data"""
        if not pixels:
            return

        # Set each pixel
        for i, (r, g, b) in enumerate(pixels):
            if i < self.hardware.led_count:
                self.hardware.set_pixel(i, r, g, b)

        # Show the updated pixels
        self.hardware.show()

    def _update_stats(self):
        """Update frame statistics"""
        current_time = time.time()
        self.frames_processed += 1

        # Calculate FPS
        if self.last_frame_time > 0:
            delta_time = current_time - self.last_frame_time
            if delta_time > 0:
                instant_fps = 1.0 / delta_time
                self.fps = self.fps * 0.8 + instant_fps * 0.2

        self.last_frame_time = current_time

        # Send stats back to Elixir process periodically
        if self.frames_processed % 30 == 0:  # Every 30 frames
            self._send_stats()

    def _send_stats(self):
        """Send statistics back to the Elixir process"""
        stats = {
            "frames_processed": self.frames_processed,
            "fps": round(self.fps, 1),
            "hardware_type": "Mock"
            if isinstance(self.hardware, MockHardware)
            else "NeoPixel",
        }

        # Send stats as binary data
        stats_bytes = str(stats).encode("utf-8")
        length_bytes = struct.pack("<I", len(stats_bytes))

        try:
            sys.stdout.buffer.write(length_bytes)
            sys.stdout.buffer.write(stats_bytes)
            sys.stdout.buffer.flush()
        except Exception as e:
            self.logger.error(f"Error sending stats: {e}")

    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up...")

        if self.hardware:
            self.hardware.clear()
            self.hardware.cleanup()

        self.logger.info("Local controller shutdown complete")

    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        self.logger.info(f"Received signal {sig}")
        self.running = False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Local LED Controller")
    parser.add_argument("--width", type=int, default=25, help="Grid width")
    parser.add_argument("--height", type=int, default=24, help="Grid height")
    parser.add_argument("--led-pin", type=int, default=18, help="LED data pin")
    parser.add_argument(
        "--led-count", type=int, help="Number of LEDs (default: width*height)"
    )

    args = parser.parse_args()

    # Calculate LED count if not provided
    led_count = args.led_count or (args.width * args.height)

    # Create and run controller
    controller = LocalLEDController(
        width=args.width, height=args.height, led_pin=args.led_pin, led_count=led_count
    )

    success = controller.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
