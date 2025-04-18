#!/usr/bin/env python3
"""
Batch Frame Test Script for LeGrid Controller

This script demonstrates how to send batched frames to the LeGrid controller
for improved connection stability and more efficient animation playback.

Features:
- Creates and sends batched animation frames
- Supports both priority and normal frame batches
- Demonstrates frame generation and batching
- Provides connection management and reconnection

Usage:
    python batch-test.py [--server-url URL] [--pattern NAME] [--frames COUNT]
"""

import websocket
import json
import time
import struct
import base64
import argparse
import logging
import threading
import math
import random
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("batch-test")

# Default values
DEFAULT_SERVER_URL = "ws://192.168.1.11:4000/controller/websocket"
DEFAULT_CONTROLLER_ID = "batch-test-client"
DEFAULT_PATTERN = "rainbow"
DEFAULT_FRAME_COUNT = 120
DEFAULT_GRID_WIDTH = 25
DEFAULT_GRID_HEIGHT = 24
DEFAULT_BATCH_SIZE = 120  # Number of frames to batch together


# Animation pattern generators
class PatternGenerators:
    @staticmethod
    def rainbow(width, height, frame_idx, params=None):
        """Generate a rainbow pattern frame"""
        frame = bytearray()
        speed = params.get("speed", 10) if params else 10
        saturation = params.get("saturation", 255) if params else 255

        for y in range(height):
            for x in range(width):
                # Create a rainbow pattern that moves over time
                hue = (x + y + frame_idx * speed) % 360
                r, g, b = PatternGenerators.hsv_to_rgb(hue, saturation, 255)
                frame.extend([r, g, b])

        return frame

    @staticmethod
    def pulse(width, height, frame_idx, params=None):
        """Generate a pulsing pattern frame"""
        frame = bytearray()
        speed = params.get("speed", 5) if params else 5
        color = params.get("color", (255, 0, 0)) if params else (255, 0, 0)

        # Calculate pulse intensity (0-255)
        pulse = int(127.5 * (math.sin(frame_idx * speed / 30) + 1))

        # Apply pulse to color
        r = int(color[0] * pulse / 255)
        g = int(color[1] * pulse / 255)
        b = int(color[2] * pulse / 255)

        # Fill entire frame with this color
        for _ in range(width * height):
            frame.extend([r, g, b])

        return frame

    @staticmethod
    def matrix(width, height, frame_idx, params=None):
        """Generate a Matrix-like rain effect"""
        frame = bytearray()

        # Get or initialize drop positions
        drops = params.get("drops", [])
        if not drops:
            # Initialize drops at random positions (x, y, intensity, speed)
            drops = []
            for _ in range(width // 2):
                drops.append(
                    [
                        random.randint(0, width - 1),  # x
                        random.randint(0, height - 1),  # y
                        random.randint(150, 255),  # intensity
                        random.randint(1, 3),  # speed
                    ]
                )
            params["drops"] = drops

        # Initialize black frame
        frame = bytearray([0, 0, 0] * width * height)

        # Update each drop
        for i, drop in enumerate(drops):
            x, y, intensity, speed = drop

            # Draw the drop and its tail
            for tail in range(5):  # 5 pixel tail
                tail_y = (y - tail) % height
                tail_intensity = max(0, intensity - tail * 50)  # Fade the tail

                # Calculate pixel index
                idx = (tail_y * width + x) * 3

                # Set pixel color (green with fading intensity)
                frame[idx] = 0  # R
                frame[idx + 1] = tail_intensity  # G
                frame[idx + 2] = 0  # B

            # Move drop down
            drops[i][1] = (y + speed) % height

            # Randomly reset some drops
            if random.random() < 0.01:
                drops[i] = [
                    random.randint(0, width - 1),
                    0,
                    random.randint(150, 255),
                    random.randint(1, 3),
                ]

        return frame

    @staticmethod
    def hsv_to_rgb(h, s, v):
        """Convert HSV color to RGB"""
        h = h % 360
        s = max(0, min(255, s)) / 255
        v = max(0, min(255, v)) / 255

        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


class BatchFrameSender:
    def __init__(self, args):
        self.args = args
        self.server_url = args.server_url
        self.controller_id = args.controller_id
        self.pattern = args.pattern
        self.frame_count = args.frames
        self.grid_width = args.width
        self.grid_height = args.height

        # WebSocket connection
        self.ws = None
        self.connected = False

        # Pattern parameters
        self.pattern_params = {
            "rainbow": {"speed": 5, "saturation": 255},
            "pulse": {"speed": 8, "color": (255, 0, 127)},
            "matrix": {"drops": []},
        }

        # Pattern generator mapping
        self.pattern_generators = {
            "rainbow": PatternGenerators.rainbow,
            "pulse": PatternGenerators.pulse,
            "matrix": PatternGenerators.matrix,
        }

        # Stats
        self.frame_id = 1
        self.batches_sent = 0
        self.frames_sent = 0

    def connect(self):
        """Connect to the WebSocket server"""
        logger.info(f"Connecting to {self.server_url}...")

        try:
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.server_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )

            # Run the connection in a separate thread
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()

            # Wait for connection to establish
            timeout = 30
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.5)

            if not self.connected:
                logger.error("Failed to connect, timed out")
                return False

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")

        # Join the Phoenix channel
        join_message = {
            "topic": "controller:lobby",
            "event": "phx_join",
            "payload": {"controller_id": self.controller_id},
            "ref": "1",
        }

        ws.send(json.dumps(join_message))

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Parse Phoenix Channel message
            if isinstance(message, str):
                data = json.loads(message)
                event = data.get("event")

                if (
                    event == "phx_reply"
                    and data.get("payload", {}).get("status") == "ok"
                ):
                    logger.info("Successfully joined Phoenix channel")
                    self.connected = True

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"Connection closed: {close_status_code} - {close_msg}")
        self.connected = False

    def create_frame(self, frame_idx, pattern):
        """Create a single frame with the specified pattern"""
        # Get the generator for the pattern
        generator = self.pattern_generators.get(pattern)
        if not generator:
            logger.warning(f"Unknown pattern: {pattern}, using rainbow")
            generator = PatternGenerators.rainbow

        # Generate pixel data
        pixel_data = generator(
            self.grid_width,
            self.grid_height,
            frame_idx,
            self.pattern_params.get(pattern, {}),
        )

        # Create frame header
        header = bytearray()
        header.append(1)  # Protocol version
        header.append(1)  # Message type (1 = full frame)
        header.extend(struct.pack("<I", self.frame_id))  # Frame ID (4 bytes)
        header.extend(struct.pack("<H", self.grid_width))  # Width (2 bytes)
        header.extend(struct.pack("<H", self.grid_height))  # Height (2 bytes)

        # Combine header and pixel data
        frame = header + pixel_data

        # Increment frame ID for next frame
        self.frame_id += 1

        return frame

    def create_batch(self, frame_count, pattern, is_priority=False):
        """Create a batch of frames with the given pattern"""
        # Create batch header
        batch = bytearray()
        batch.append(0xB)  # Batch identifier
        batch.extend(struct.pack("<I", frame_count))  # Frame count (4 bytes)
        batch.append(1 if is_priority else 0)  # Priority flag (1 byte)

        # Generate frames
        for i in range(frame_count):
            frame = self.create_frame(i, pattern)

            # Add frame length and frame data to batch
            batch.extend(struct.pack("<I", len(frame)))  # Frame length (4 bytes)
            batch.extend(frame)  # Frame data

        logger.info(f"Created batch with {frame_count} frames, size={len(batch)} bytes")
        return batch

    def send_batch(self, batch, is_priority=False):
        """Send a batch of frames to the controller"""
        if not self.connected or not self.ws:
            logger.error("Cannot send batch, not connected")
            return False

        try:
            # Send the batch
            self.ws.send(batch, websocket.ABNF.OPCODE_BINARY)
            self.batches_sent += 1

            # Get frame count from batch
            frame_count = struct.unpack("<I", batch[1:5])[0]
            self.frames_sent += frame_count

            logger.info(
                f"Sent batch #{self.batches_sent} with {frame_count} frames "
                f"(total frames: {self.frames_sent})"
            )
            return True

        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            return False

    def run(self):
        """Run the batch frame sender"""
        if not self.connect():
            logger.error("Failed to connect, exiting")
            return

        try:
            while True:
                # Create and send a batch
                logger.info(f"Creating batch with pattern '{self.pattern}'")
                batch = self.create_batch(self.frame_count, self.pattern)

                # Send the batch
                if not self.send_batch(batch):
                    logger.error("Failed to send batch, reconnecting...")
                    self.connect()
                    continue

                # Wait for user input
                choice = input(
                    "\nOptions:\n"
                    "1) Send another batch with same pattern\n"
                    "2) Change pattern\n"
                    "3) Send priority batch\n"
                    "4) Exit\n"
                    "Enter choice (1-4): "
                )

                if choice == "1":
                    # Send another batch with same pattern
                    continue
                elif choice == "2":
                    # Change pattern
                    print("\nAvailable patterns:")
                    for i, pattern in enumerate(self.pattern_generators.keys(), 1):
                        print(f"{i}) {pattern}")

                    pattern_choice = input("Select pattern: ")
                    try:
                        pattern_idx = int(pattern_choice) - 1
                        patterns = list(self.pattern_generators.keys())
                        if 0 <= pattern_idx < len(patterns):
                            self.pattern = patterns[pattern_idx]
                            logger.info(f"Changed pattern to '{self.pattern}'")
                        else:
                            logger.warning("Invalid pattern selection")
                    except ValueError:
                        logger.warning("Invalid input")
                elif choice == "3":
                    # Send priority batch
                    logger.info("Creating priority batch")
                    batch = self.create_batch(
                        min(30, self.frame_count), self.pattern, is_priority=True
                    )
                    self.send_batch(batch, is_priority=True)
                elif choice == "4":
                    # Exit
                    logger.info("Exiting...")
                    break
                else:
                    logger.warning("Invalid choice")

        except KeyboardInterrupt:
            logger.info("Interrupted by user, exiting...")
        finally:
            # Close connection
            if self.ws:
                self.ws.close()

        # Print statistics
        logger.info(f"Batch Frame Sender Statistics:")
        logger.info(f"  Batches sent: {self.batches_sent}")
        logger.info(f"  Frames sent: {self.frames_sent}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Batch Frame Sender for LeGrid Controller"
    )

    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=f"WebSocket server URL (default: {DEFAULT_SERVER_URL})",
    )

    parser.add_argument(
        "--controller-id",
        default=DEFAULT_CONTROLLER_ID,
        help=f"Controller ID (default: {DEFAULT_CONTROLLER_ID})",
    )

    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        choices=["rainbow", "pulse", "matrix"],
        help=f"Animation pattern (default: {DEFAULT_PATTERN})",
    )

    parser.add_argument(
        "--frames",
        type=int,
        default=DEFAULT_FRAME_COUNT,
        help=f"Number of frames per batch (default: {DEFAULT_FRAME_COUNT})",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_GRID_WIDTH,
        help=f"Grid width (default: {DEFAULT_GRID_WIDTH})",
    )

    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_GRID_HEIGHT,
        help=f"Grid height (default: {DEFAULT_GRID_HEIGHT})",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sender = BatchFrameSender(args)
    sender.run()
