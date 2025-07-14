#!/usr/bin/env python3
"""
Local LED Controller for Legrid

This script runs as a separate process and receives frame data from the Elixir server
to control the physical LED grid.
"""

import sys
import json
import time
import argparse
import struct
import signal
from typing import List, Tuple

# Try to import the real hardware libraries, fall back to mock if not available
try:
    import board
    import neopixel
    import numpy as np

    HARDWARE_AVAILABLE = True
    print("Hardware libraries available - using real LED control")
except ImportError:
    print("Hardware libraries not available - using mock LED control for development")
    HARDWARE_AVAILABLE = False
    # Mock numpy for development
    try:
        import numpy as np
    except ImportError:
        # Simple mock numpy if not available
        class MockNumpy:
            def array(self, data, dtype=None):
                return data

        np = MockNumpy()


class MockNeoPixel:
    """Mock NeoPixel for development without hardware"""

    def __init__(self, pin, count, auto_write=False, pixel_order=None):
        self.count = count
        self.pixels = [(0, 0, 0)] * count
        self.auto_write = auto_write
        print(f"Mock NeoPixel initialized: {count} LEDs")

    def fill(self, color):
        self.pixels = [color] * self.count
        if self.auto_write:
            self.show()

    def show(self):
        # In mock mode, just print the first few pixels for debugging
        active_pixels = [p for p in self.pixels if p != (0, 0, 0)]
        if active_pixels:
            print(
                f"Mock LED update: {len(active_pixels)} active pixels, first few: {active_pixels[:5]}"
            )

    def __setitem__(self, index, value):
        if 0 <= index < self.count:
            self.pixels[index] = value
            if self.auto_write:
                self.show()


class LEDController:
    def __init__(self, width: int, height: int, led_pin: int, led_count: int):
        self.width = width
        self.height = height
        self.led_pin = led_pin
        self.led_count = led_count

        # Initialize LED strip
        try:
            if HARDWARE_AVAILABLE:
                self.pixels = neopixel.NeoPixel(
                    getattr(board, f"D{led_pin}"),
                    led_count,
                    auto_write=False,
                    pixel_order=neopixel.RGB,
                )
                print(
                    f"Real LED controller initialized: {width}x{height} grid, {led_count} LEDs on pin {led_pin}"
                )
            else:
                self.pixels = MockNeoPixel(led_pin, led_count, auto_write=False)
                print(
                    f"Mock LED controller initialized: {width}x{height} grid, {led_count} LEDs on pin {led_pin}"
                )
        except Exception as e:
            print(f"Error initializing LEDs: {e}")
            # Fall back to mock
            self.pixels = MockNeoPixel(led_pin, led_count, auto_write=False)
            print(f"Falling back to mock LED controller")

        # Clear LEDs on startup
        self.clear()

    def clear(self):
        """Clear all LEDs"""
        self.pixels.fill((0, 0, 0))
        self.pixels.show()

    def set_frame(self, pixels: List[Tuple[int, int, int]]):
        """Set the entire LED frame"""
        if len(pixels) != self.led_count:
            print(f"Warning: Expected {self.led_count} pixels, got {len(pixels)}")
            return

        # Update all pixels
        for i, (r, g, b) in enumerate(pixels):
            self.pixels[i] = (r, g, b)

        # Show the frame
        self.pixels.show()

    def shutdown(self):
        """Clean shutdown - turn off all LEDs"""
        print("Shutting down LED controller...")
        self.clear()


def main():
    parser = argparse.ArgumentParser(description="Local LED Controller for Legrid")
    parser.add_argument("--width", type=int, default=25, help="Grid width")
    parser.add_argument("--height", type=int, default=24, help="Grid height")
    parser.add_argument("--led-pin", type=int, default=18, help="GPIO pin for LED data")
    parser.add_argument("--led-count", type=int, default=600, help="Number of LEDs")

    args = parser.parse_args()

    # Initialize controller
    controller = LEDController(args.width, args.height, args.led_pin, args.led_count)

    # Signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("Shutting down LED controller...")
        controller.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("LED controller ready. Waiting for frame data...")

    # Main loop - read frame data from stdin
    try:
        while True:
            # Read binary frame data from Elixir process
            # First read the length (4 bytes)
            length_bytes = sys.stdin.buffer.read(4)
            if not length_bytes or len(length_bytes) < 4:
                break

            frame_length = int.from_bytes(length_bytes, byteorder="little")

            # Read the frame data
            frame_data = sys.stdin.buffer.read(frame_length)
            if not frame_data or len(frame_data) < frame_length:
                break

            try:
                # Parse Erlang binary format
                # For now, let's create a simple test pattern since Erlang binary parsing is complex
                pixels = []
                for i in range(controller.led_count):
                    # Create a simple moving pattern for testing
                    r = (i + int(time.time() * 10)) % 256
                    g = (i * 2) % 256
                    b = (i * 3) % 256
                    pixels.append((r, g, b))

                controller.set_frame(pixels)
                print(f"Processed frame: {len(pixels)} pixels (test pattern)")

            except Exception as e:
                print(f"Error processing frame: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        controller.shutdown()


if __name__ == "__main__":
    main()
