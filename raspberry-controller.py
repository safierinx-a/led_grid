#!/usr/bin/env python3
import os
import time
import json
import signal
import argparse
import uuid
import struct
import logging
import sys
from datetime import datetime
import base64

# Try to import the rpi_ws281x library for hardware control
# If it's not available, we'll use a mock implementation for development
try:
    import board
    import neopixel

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: Hardware libraries not available, using mock implementation")

# Try to import websocket-client
try:
    import websocket
    from websocket import ABNF  # Import ABNF for opcode constants
except ImportError:
    print("Error: websocket-client library not found.")
    print("Please install it with: pip install websocket-client")
    sys.exit(1)

# Configuration defaults
DEFAULT_WIDTH = 25
DEFAULT_HEIGHT = 24
DEFAULT_LED_COUNT = 600  # DEFAULT_WIDTH * DEFAULT_HEIGHT
DEFAULT_LED_PIN = 18
DEFAULT_BRIGHTNESS = 255
DEFAULT_SERVER_URL = (
    "ws://192.168.1.11:4000/controller/websocket"  # Ensure correct path
)
DEFAULT_LOG_LEVEL = "INFO"

# Grid layout and orientation options
DEFAULT_LAYOUT = "serpentine"  # Could be "linear" or "serpentine"
DEFAULT_FLIP_X = False  # Flip horizontally
DEFAULT_FLIP_Y = False  # Flip vertically
DEFAULT_TRANSPOSE = False  # Swap X and Y axes (rotation by 90 degrees)

# Global variables
running = True
reconnect_delay = 1.0  # Start with 1 second delay, will increase on failures

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("legrid-controller")


# Mock implementation for development without hardware
class MockWs:
    def __init__(self, count, brightness=255):
        self.count = count
        self.brightness = brightness
        self.leds = [(0, 0, 0) for _ in range(count)]
        logger.info(f"Initialized mock LED strip with {count} LEDs")

    def begin(self):
        pass

    def show(self):
        # We could render a visual representation of the LED state here
        # For now, we just log the update
        logger.debug(f"Updated mock LED strip with {len(self.leds)} values")

    def setPixelColor(self, index, color):
        if 0 <= index < self.count:
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self.leds[index] = (r, g, b)

    def setBrightness(self, brightness):
        self.brightness = brightness
        logger.debug(f"Set mock LED brightness to {brightness}")

    def numPixels(self):
        return self.count


# Main controller class
class LegridController:
    def __init__(self, args):
        self.args = args
        self.width = args.width
        self.height = args.height
        self.led_count = args.led_count
        self.brightness = args.led_brightness
        self.server_url = args.server_url
        self.controller_id = str(uuid.uuid4())

        # Pattern tracking
        self.last_pattern_id = None
        self.last_parameters = None

        # Grid layout options
        self.layout = args.layout
        self.flip_x = args.flip_x
        self.flip_y = args.flip_y
        self.transpose = args.transpose

        # Log grid configuration
        logger.info(
            f"Grid configuration: {self.width}x{self.height}, layout={self.layout}"
        )
        logger.info(
            f"Grid orientation: flip_x={self.flip_x}, flip_y={self.flip_y}, transpose={self.transpose}"
        )

        # Statistics
        self.stats = {
            "frames_received": 0,
            "frames_displayed": 0,
            "connection_drops": 0,
            "last_frame_time": 0,
            "fps": 0,
            "connection_uptime": 0,
            "connection_start_time": 0,
        }

        # Connection health tracking
        self.last_pong_time = 0
        self.missing_pong_count = 0
        self.connection_timeout = (
            30  # Consider connection dead after 30 seconds without pong
        )

        self.ws = None  # WebSocket connection
        self.strip = None  # LED strip

        # Initialize the LED strip
        self.initialize_leds()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def initialize_leds(self):
        if HARDWARE_AVAILABLE:
            # Initialize the real hardware
            try:
                self.strip = neopixel.NeoPixel(
                    board.D18,  # Pin 18 (BCM numbering)
                    self.led_count,
                    brightness=self.brightness / 255.0,
                    auto_write=False,
                    pixel_order=neopixel.GRB,
                )
                logger.info(
                    f"Initialized hardware LED strip with {self.led_count} LEDs"
                )
            except Exception as e:
                logger.error(f"Failed to initialize hardware: {e}")
                logger.info("Falling back to mock implementation")
                self.strip = MockWs(self.led_count, self.brightness)
        else:
            # Use the mock implementation
            self.strip = MockWs(self.led_count, self.brightness)

        # Clear the LEDs on startup
        self.clear_leds()

    def clear_leds(self):
        """Clear all LEDs (set to black/off)"""
        for i in range(self.led_count):
            if HARDWARE_AVAILABLE:
                self.strip[i] = (0, 0, 0)
            else:
                self.strip.setPixelColor(i, 0)

        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        logger.info("Cleared all LEDs")

    def map_pixel_index(self, x, y):
        """
        Map x,y grid coordinates to the physical LED index.
        Accounts for serpentine layout and orientation options.

        Args:
            x: x-coordinate (0 to width-1)
            y: y-coordinate (0 to height-1)

        Returns:
            int: The physical LED index
        """
        # Apply transformations based on orientation options
        if self.transpose:
            x, y = y, x

        # Apply flips
        if self.flip_x:
            x = self.width - 1 - x

        if self.flip_y:
            y = self.height - 1 - y

        # Apply layout pattern
        if self.layout == "serpentine":
            # In serpentine layout, even rows go left to right, odd rows go right to left
            if y % 2 == 1:  # Odd row (0-indexed)
                x = self.width - 1 - x

        # Convert to linear index
        return y * self.width + x

    def update_leds_from_binary(self, data, priority=False):
        """Update LEDs from binary frame data"""
        # Check if we have enough data for the header
        if len(data) < 10:
            logger.warning(f"Received incomplete binary frame: {len(data)} bytes")
            if len(data) > 0:
                logger.debug(f"First bytes (hex): {data[: min(10, len(data))].hex()}")
            return

        try:
            # Check for WebSocket control frames - common patterns
            if len(data) >= 2:
                # WebSocket close frame (opcode 8)
                if data[0] == 0x88 or data[0] == 0x8:
                    logger.info("Ignoring WebSocket close frame")
                    return

                # WebSocket ping frame (opcode 9)
                if data[0] == 0x89 or data[0] == 0x9:
                    logger.info("Ignoring WebSocket ping frame")
                    return

                # WebSocket pong frame (opcode 10)
                if data[0] == 0x8A or data[0] == 0xA:
                    logger.info("Ignoring WebSocket pong frame")
                    return

            # Dump the first 20 bytes for debugging (only for priority frames to avoid log spam)
            if priority:
                logger.debug(f"Binary frame first 20 bytes (hex): {data[:20].hex()}")

            # Parse the header - using little-endian to match server encoding
            version = data[
                0
            ]  # This will be 1 from the server or possibly 123 if something is wrong

            # Special handling for protocol version 123
            if version == 123:
                logger.info("Detected protocol version 123, treating as version 1")
                # Adjust the version for processing
                version = 1

            msg_type = data[1]
            frame_id = struct.unpack("<I", data[2:6])[0]
            width = struct.unpack("<H", data[6:8])[0]
            height = struct.unpack("<H", data[8:10])[0]

            # Do basic sanity checks on the frame data
            if width == 0 or height == 0 or width > 1000 or height > 1000:
                logger.warning(
                    f"Suspicious frame dimensions: {width}x{height}, ignoring frame"
                )
                return

            # Skip detailed logging in high frame rate scenarios to reduce latency
            if (
                priority or self.stats["fps"] < 20
            ):  # Only log details at lower frame rates or for priority updates
                logger.debug(
                    f"Frame header: version={version} (original: {data[0]}), type={msg_type}, id={frame_id}, dims={width}x{height}"
                )

            # Validate message type - but be lenient
            if msg_type not in (1, 2):
                logger.warning(
                    f"Unknown message type: {msg_type}, defaulting to full frame"
                )
                msg_type = 1  # Default to full frame processing for unknown types

            # We can handle frame data with different dimensions, but log a warning
            if width != self.width or height != self.height:
                logger.warning(
                    f"Frame dimensions mismatch: {width}x{height} (expected {self.width}x{self.height})"
                )
                # We'll use the smaller dimensions
                width = min(width, self.width)
                height = min(height, self.height)

            # Extract pixel data based on message type
            pixel_data = data[10:]
            if msg_type == 1:  # Full frame
                self.update_leds_from_pixels(
                    pixel_data, width, height, priority=priority
                )
            elif msg_type == 2:  # Delta frame
                self.apply_delta_frame(pixel_data, priority=priority)

            # Update stats
            self.stats["frames_received"] += 1
            current_time = time.time()
            if self.stats["last_frame_time"] > 0:
                time_diff = current_time - self.stats["last_frame_time"]
                if time_diff > 0:
                    # Apply smoothing to FPS calculation
                    self.stats["fps"] = 0.8 * self.stats["fps"] + 0.2 * (
                        1.0 / time_diff
                    )
            self.stats["last_frame_time"] = current_time
            self.stats["frames_displayed"] += 1

        except Exception as e:
            logger.error(f"Error processing binary frame: {e}")
            if len(data) > 0:
                logger.error(
                    f"First 20 bytes (hex): {data[: min(20, len(data))].hex()}"
                )
            import traceback

            logger.error(traceback.format_exc())

    def update_leds_from_pixels(self, pixel_data, width, height, priority=False):
        """Update all LEDs from pixel data (full frame), applying layout transformation"""
        if len(pixel_data) < width * height * 3:
            logger.warning(
                f"Not enough pixel data: got {len(pixel_data)} bytes, expected {width * height * 3}"
            )
            # Still try to update as many pixels as we can

        # Clear all LEDs first if this is a priority update (redundant if already cleared by pattern change)
        if priority:
            for i in range(self.led_count):
                if HARDWARE_AVAILABLE:
                    self.strip[i] = (0, 0, 0)
                else:
                    self.strip.setPixelColor(i, 0)

        # Update LEDs using the mapping function
        updated_leds = set()
        for y in range(height):
            for x in range(width):
                # Calculate source index in the pixel data
                src_idx = (y * width + x) * 3

                if src_idx + 2 < len(pixel_data):
                    # Read RGB values
                    r = pixel_data[src_idx]
                    g = pixel_data[src_idx + 1]
                    b = pixel_data[src_idx + 2]

                    # Map to physical LED position
                    dest_idx = self.map_pixel_index(x, y)

                    if 0 <= dest_idx < self.led_count:
                        updated_leds.add(dest_idx)
                        if HARDWARE_AVAILABLE:
                            self.strip[dest_idx] = (r, g, b)
                        else:
                            color = (r << 16) | (g << 8) | b
                            self.strip.setPixelColor(dest_idx, color)

        # Show the strip
        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        # Only log detailed info at lower fps or for priority updates
        if priority or self.stats["fps"] < 20:
            logger.debug(f"Updated {len(updated_leds)} LEDs from full frame")

    def apply_delta_frame(self, delta_data, priority=False):
        """Apply a delta frame (only changed pixels)"""
        if len(delta_data) < 2:
            logger.warning("Delta frame too small")
            return

        # First 2 bytes are the number of deltas - using little-endian
        num_deltas = struct.unpack("<H", delta_data[0:2])[0]
        delta_data = delta_data[2:]

        if len(delta_data) < num_deltas * 5:
            logger.warning(
                f"Not enough delta data: got {len(delta_data)} bytes, expected {num_deltas * 5}"
            )
            return

        # Track updated LEDs for logging
        updated_leds = set()

        # For priority updates, process immediately without any optimizations
        for i in range(num_deltas):
            index = i * 5
            if index + 4 < len(delta_data):
                # 2 bytes for pixel index, 3 bytes for RGB - little-endian
                pixel_index = struct.unpack("<H", delta_data[index : index + 2])[0]
                r = delta_data[index + 2]
                g = delta_data[index + 3]
                b = delta_data[index + 4]

                # Map to physical LED position
                dest_idx = self.map_pixel_index(
                    pixel_index % self.width, pixel_index // self.width
                )

                if 0 <= dest_idx < self.led_count:
                    updated_leds.add(dest_idx)
                    if HARDWARE_AVAILABLE:
                        self.strip[dest_idx] = (r, g, b)
                    else:
                        color = (r << 16) | (g << 8) | b
                        self.strip.setPixelColor(dest_idx, color)

        # Show the strip
        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        # Only log detailed info at lower fps or for priority updates
        if priority or self.stats["fps"] < 20:
            logger.debug(f"Updated {len(updated_leds)} LEDs from delta frame")

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

        # Send join message
        ws.send(json.dumps(join_message))

        # Send controller info after successful connection
        self.send_controller_info()

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Check if the message is binary or text
            if isinstance(message, bytes):
                # Check for WebSocket control frames first
                if len(message) >= 1:
                    opcode = message[0] & 0xF if len(message) > 0 else None
                    if opcode in [0x8, 0x9, 0xA]:  # Close, Ping, Pong frames
                        logger.debug(
                            f"Received WebSocket control frame (opcode: {opcode})"
                        )
                        return

                    # Check if this might be a frame with protocol version 123
                    if message[0] == 123 and len(message) >= 10:
                        logger.info(
                            "Received binary message with protocol version 123, processing it"
                        )
                        self.update_leds_from_binary(message, priority=True)
                        return

                    # Phoenix heartbeat messages often have specific patterns
                    if len(message) >= 4 and message[0] == 0x1 and message[1] == 0x1:
                        logger.debug("Received Phoenix heartbeat message")
                        # Update last_pong_time since we received something from the server
                        self.last_pong_time = time.time()
                        return

                # Only process likely frame data - check for valid protocol versions
                if len(message) >= 10 and (message[0] <= 10 or message[0] == 123):
                    logger.debug(
                        f"Processing binary WebSocket message ({len(message)} bytes)"
                    )
                    self.update_leds_from_binary(message, priority=False)
                else:
                    logger.info(
                        f"Ignoring binary WebSocket message: first byte = {message[0] if len(message) > 0 else 'unknown'}"
                    )
                    # Still update last_pong_time since we received data from the server
                    self.last_pong_time = time.time()
            else:
                # Process Phoenix Channel message (JSON)
                data = json.loads(message)

                # Extract event and payload from Phoenix message format
                event = data.get("event")
                payload = data.get("payload", {})

                # Any message received is a sign the connection is alive
                self.last_pong_time = time.time()

                # Only log non-frame events to reduce spam
                if event != "frame":
                    logger.debug(f"Received event: {event}")

                if event == "phx_reply" and payload.get("status") == "ok":
                    # Join confirmation
                    logger.info("Successfully joined channel")
                    # Reset missing pong counter on confirmed join
                    self.missing_pong_count = 0

                elif event == "frame":
                    # Handle frame message - contains binary data in payload["binary"]
                    if "binary" in payload:
                        # Check if this is a new pattern or parameters changed
                        clear_needed = False
                        priority_update = False  # Flag for high-priority updates

                        # Check for pattern ID changes
                        if "pattern_id" in payload:
                            if (
                                not hasattr(self, "last_pattern_id")
                                or self.last_pattern_id != payload["pattern_id"]
                            ):
                                self.last_pattern_id = payload["pattern_id"]
                                clear_needed = True
                                priority_update = (
                                    True  # Pattern changes are highest priority
                                )
                                logger.info(
                                    f"New pattern detected (ID: {self.last_pattern_id}). Clearing LEDs."
                                )

                        # Check for parameter changes
                        if "parameters" in payload:
                            if (
                                not hasattr(self, "last_parameters")
                                or self.last_parameters != payload["parameters"]
                            ):
                                param_diff = ""
                                if hasattr(self, "last_parameters"):
                                    # Only log changes in non-high-fps scenarios
                                    if self.stats["fps"] < 20:
                                        old_params = set(self.last_parameters.items())
                                        new_params = set(payload["parameters"].items())
                                        changes = new_params - old_params
                                        if changes:
                                            param_diff = f" Changes: {changes}"
                                            priority_update = (
                                                True  # Parameter changes get priority
                                            )

                            self.last_parameters = payload["parameters"].copy()
                            clear_needed = True
                            logger.info(
                                f"Pattern parameters changed.{param_diff} Clearing LEDs."
                            )

                        # Clear LEDs if needed before applying new frame
                        if clear_needed:
                            self.clear_leds()

                        # Record time of frame receipt for latency measurements
                        receipt_time = time.time()

                        # The binary data is base64 encoded in JSON
                        try:
                            binary_data = base64.b64decode(payload["binary"])

                            # Only log at lower frame rates
                            if self.stats["fps"] < 20:
                                logger.debug(
                                    f"Received frame binary data of length {len(binary_data)}"
                                )

                            # Process frame data immediately to reduce latency
                            # For high-priority updates (pattern/parameter changes), use immediate mode
                            self.update_leds_from_binary(
                                binary_data, priority=priority_update
                            )

                            # Calculate and log latency only at lower frame rates
                            if self.stats["fps"] < 20:
                                display_time = time.time()
                                latency_ms = (display_time - receipt_time) * 1000
                                logger.debug(
                                    f"Frame processing latency: {latency_ms:.2f}ms"
                                )
                        except Exception as bin_error:
                            logger.error(
                                f"Failed to decode or process binary frame: {bin_error}"
                            )
                            # Log the first part of the binary string to help with debugging
                            if (
                                isinstance(payload["binary"], str)
                                and len(payload["binary"]) > 0
                            ):
                                logger.debug(
                                    f"Binary data starts with: {payload['binary'][:20]}"
                                )
                            elif (
                                isinstance(payload["binary"], bytes)
                                and len(payload["binary"]) > 0
                            ):
                                logger.debug(
                                    f"Binary data starts with (hex): {payload['binary'][:20].hex()}"
                                )

                elif event == "request_stats":
                    # Send stats in response to request
                    self.send_stats()

                elif event == "request_detailed_stats":
                    # Send detailed stats
                    self.send_detailed_stats()

                elif event == "simulation_config":
                    # Apply simulation config
                    logger.info(f"Received simulation config: {payload}")
                    # Process any configuration options
                    if "orientation" in payload:
                        self.process_orientation_config(payload["orientation"])

                elif event == "ping":
                    # Respond to ping
                    self.ws.send(
                        json.dumps(
                            {
                                "topic": "controller:lobby",
                                "event": "pong",
                                "payload": {},
                                "ref": None,
                            }
                        )
                    )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # For debugging, log message type and first few bytes
            if isinstance(message, bytes):
                logger.error(
                    f"Error on binary message, first 20 bytes: {message[:20].hex()}"
                )
            elif isinstance(message, str):
                logger.error(f"Error on text message, first 40 chars: {message[:40]}")
            import traceback

            logger.error(traceback.format_exc())

    def process_orientation_config(self, orientation):
        """Process orientation configuration from server"""
        if not isinstance(orientation, dict):
            logger.warning(f"Invalid orientation config: {orientation}")
            return

        # Update orientation options if provided
        if "flip_x" in orientation:
            self.flip_x = bool(orientation["flip_x"])
        if "flip_y" in orientation:
            self.flip_y = bool(orientation["flip_y"])
        if "transpose" in orientation:
            self.transpose = bool(orientation["transpose"])
        if "layout" in orientation:
            self.layout = orientation["layout"]

        logger.info(
            f"Updated grid orientation: flip_x={self.flip_x}, flip_y={self.flip_y}, transpose={self.transpose}, layout={self.layout}"
        )

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")

        # Update connection statistics
        if self.stats["connection_start_time"] > 0:
            self.stats["connection_uptime"] += (
                time.time() - self.stats["connection_start_time"]
            )

        self.stats["connection_drops"] += 1

    def send_stats(self):
        """Send controller statistics"""
        current_time = time.time()
        uptime = (
            current_time - self.stats["connection_start_time"]
            if self.stats["connection_start_time"] > 0
            else 0
        )

        # Create stats message in Phoenix Channel format
        stats_data = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "frames_received": self.stats["frames_received"],
                "frames_displayed": self.stats["frames_displayed"],
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "connection_uptime": uptime,
                "timestamp": datetime.now().isoformat(),
            },
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(stats_data))
            logger.debug("Sent controller stats")
        except Exception as e:
            logger.error(f"Error sending stats: {e}")

    def send_controller_info(self):
        """Send controller information after connection"""
        info = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "type": "controller_info",
                "id": self.controller_id,
                "width": self.width,
                "height": self.height,
                "led_count": self.led_count,
                "version": "1.0.0",
                "hardware": "Raspberry Pi" if HARDWARE_AVAILABLE else "Mock",
                "layout": self.layout,
                "orientation": {
                    "flip_x": self.flip_x,
                    "flip_y": self.flip_y,
                    "transpose": self.transpose,
                },
            },
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(info))
            logger.info("Sent controller info")
        except Exception as e:
            logger.error(f"Error sending controller info: {e}")

    def send_detailed_stats(self):
        """Send detailed statistics (in response to a request)"""
        # Create detailed stats in Phoenix Channel format
        detailed_stats = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "type": "detailed_stats",
                "frames_received": self.stats["frames_received"],
                "frames_displayed": self.stats["frames_displayed"],
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "connection_uptime": self.stats["connection_uptime"],
                "hardware_info": {
                    "type": "Raspberry Pi" if HARDWARE_AVAILABLE else "Mock",
                    "led_count": self.led_count,
                    "width": self.width,
                    "height": self.height,
                    "layout": self.layout,
                    "orientation": {
                        "flip_x": self.flip_x,
                        "flip_y": self.flip_y,
                        "transpose": self.transpose,
                    },
                },
            },
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(detailed_stats))
            logger.info("Sent detailed stats")
        except Exception as e:
            logger.error(f"Error sending detailed stats: {e}")

    def run(self):
        """Run the controller, connecting to the WebSocket server"""
        global reconnect_delay

        while running:
            try:
                # Create WebSocket connection with optimized settings
                # Note: For Phoenix channels, use a URL like:
                # ws://192.168.1.11:4000/controller/websocket
                self.ws = websocket.WebSocketApp(
                    self.server_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_ping=lambda ws, message: logger.debug("Received ping"),
                    on_pong=lambda ws, message: self.handle_pong(),
                )

                # Configure WebSocket to handle binary data properly
                # This is critical - without this, binary frames can be misinterpreted
                websocket.enableTrace(False)

                # Set connection start time
                self.stats["connection_start_time"] = time.time()
                self.last_pong_time = time.time()  # Initialize pong timer

                # Start a thread to send stats periodically
                def stats_sender():
                    while running and self.ws.sock and self.ws.sock.connected:
                        try:
                            # Check connection health
                            if (
                                time.time() - self.last_pong_time
                                > self.connection_timeout
                            ):
                                self.missing_pong_count += 1
                                logger.warning(
                                    f"No pong received in {self.connection_timeout} seconds. Count: {self.missing_pong_count}"
                                )

                                # If we've missed too many pongs, force a reconnection
                                if self.missing_pong_count >= 3:
                                    logger.error(
                                        "Connection appears to be dead. Forcing reconnection..."
                                    )
                                    if self.ws and self.ws.sock:
                                        self.ws.close()
                                    return

                                # Send a ping to check if connection is alive
                                if self.ws and self.ws.sock and self.ws.sock.connected:
                                    self.ws.ping("ping")

                            # Send regular stats if connection is healthy
                            self.send_stats()

                            # Send a Phoenix-specific heartbeat to keep the connection alive
                            try:
                                if self.ws and self.ws.sock and self.ws.sock.connected:
                                    heartbeat = {
                                        "topic": "phoenix",
                                        "event": "heartbeat",
                                        "payload": {},
                                        "ref": str(int(time.time())),
                                    }
                                    self.ws.send(json.dumps(heartbeat))
                                    logger.debug("Sent Phoenix heartbeat")
                            except Exception as e:
                                logger.error(f"Error sending Phoenix heartbeat: {e}")

                        except Exception as e:
                            logger.error(f"Error in stats thread: {e}")

                        time.sleep(5)  # Send stats every 5 seconds

                # Start the WebSocket connection
                from threading import Thread

                stats_thread = Thread(target=stats_sender)
                stats_thread.daemon = True
                stats_thread.start()  # Start the stats thread immediately

                # Connect to the server with optimized settings
                logger.info(f"Connecting to {self.server_url}...")

                # More robust connection parameters:
                # - Increased ping_interval for better connection monitoring
                # - Implement ping/pong for connection health monitoring
                # - Increased ping_timeout for better network tolerance
                try:
                    # Try using the run_forever method with the basic parameters first
                    self.ws.run_forever(
                        ping_interval=5,
                        ping_timeout=3,
                    )
                except TypeError as e:
                    # Handle the case where binary_type parameter is causing issues
                    if "unexpected keyword argument 'binary_type'" in str(e):
                        logger.warning(
                            "WebSocket client does not support binary_type parameter, using fallback"
                        )
                        # Fall back to a more basic configuration
                        self.ws.run_forever()
                    else:
                        # Re-raise if it's a different TypeError
                        raise

                # If we get here, the connection was closed
                if running:
                    logger.info(
                        f"Connection lost. Reconnecting in {reconnect_delay} seconds..."
                    )
                    time.sleep(reconnect_delay)

                    # Reset missing pong counter on reconnection
                    self.missing_pong_count = 0

                    # Increase reconnect delay up to a maximum of 30 seconds
                    reconnect_delay = min(reconnect_delay * 1.5, 30.0)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                import traceback

                logger.error(traceback.format_exc())

                if running:
                    logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 30.0)

    def handle_pong(self):
        """Handle pong responses from the server"""
        logger.debug("Received pong from server")
        # Update last pong time to track connection health
        self.last_pong_time = time.time()

    def signal_handler(self, sig, frame):
        """Handle termination signals"""
        global running
        logger.info("Received termination signal. Shutting down...")
        running = False

        # Cleanup
        self.clear_leds()

        # Send a clean disconnect message if possible
        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                # Send a leave message
                leave_message = {
                    "topic": "controller:lobby",
                    "event": "phx_leave",
                    "payload": {},
                    "ref": None,
                }
                self.ws.send(json.dumps(leave_message))
                logger.info("Sent leave message")
            except Exception as e:
                logger.warning(f"Failed to send leave message: {e}")

        # Close the websocket
        if self.ws:
            self.ws.close()

        # Force exit if still running after 2 seconds
        import threading

        threading.Timer(2, lambda: os._exit(0)).start()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Legrid Controller for Raspberry Pi")

    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"Grid width (default: {DEFAULT_WIDTH})",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help=f"Grid height (default: {DEFAULT_HEIGHT})",
    )
    parser.add_argument(
        "--led-count",
        type=int,
        default=DEFAULT_LED_COUNT,
        help=f"Number of LEDs (default: {DEFAULT_LED_COUNT})",
    )
    parser.add_argument(
        "--led-pin",
        type=int,
        default=DEFAULT_LED_PIN,
        help=f"GPIO pin for LED data (default: {DEFAULT_LED_PIN})",
    )
    parser.add_argument(
        "--led-brightness",
        type=int,
        default=DEFAULT_BRIGHTNESS,
        help=f"LED brightness (0-255, default: {DEFAULT_BRIGHTNESS})",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default=DEFAULT_SERVER_URL,
        help=f"WebSocket server URL (default: {DEFAULT_SERVER_URL})",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=DEFAULT_LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Logging level (default: {DEFAULT_LOG_LEVEL})",
    )

    # Grid layout and orientation options
    parser.add_argument(
        "--layout",
        type=str,
        default=DEFAULT_LAYOUT,
        choices=["linear", "serpentine"],
        help=f"LED strip layout pattern (default: {DEFAULT_LAYOUT})",
    )
    parser.add_argument(
        "--flip-x",
        action="store_true",
        default=DEFAULT_FLIP_X,
        help="Flip grid horizontally",
    )
    parser.add_argument(
        "--flip-y",
        action="store_true",
        default=DEFAULT_FLIP_Y,
        help="Flip grid vertically",
    )
    parser.add_argument(
        "--transpose",
        action="store_true",
        default=DEFAULT_TRANSPOSE,
        help="Transpose grid (swap X and Y axes)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Set log level
    logger.setLevel(getattr(logging, args.log_level))

    # Initialize and run the controller
    controller = LegridController(args)
    controller.run()
