#!/usr/bin/env python3
"""
Legrid LED Matrix Controller - Raspberry Pi Client

This script connects to a Phoenix server via WebSocket and controls
WS2812B/NeoPixel LED strips/matrices according to the frames received.

Features:
- Real-time control of WS2812B/NeoPixel LED matrices
- WebSocket communication with Phoenix server
- Support for both hardware control and mock implementation
- Automatic reconnection and error handling
- Frame buffering for robust playback during network instability
- Priority handling for pattern/parameter changes
- Performance monitoring and statistics reporting

Frame Buffer Mode:
When enabled (default), frames are stored in a buffer and played back at a
consistent frame rate. This improves playback smoothness during network
jitter and provides resilience against brief connection issues.

Buffer features:
- Configurable buffer size (default: 20 frames)
- Adjustable playback rate (default: 30 FPS)
- Priority frame bypass (pattern changes skip the buffer)
- Dashboard synchronization for monitoring
- Automatic buffer management during connection issues

To disable the buffer and use direct mode:
    python raspberry-controller.py --no-buffer

For fine-tuning buffer behavior:
    python raspberry-controller.py --buffer-size 30 --buffer-rate 60
"""

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
import threading

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

# Debug options
DEBUG_FRAMES = False  # Set to True to debug frame processing
DEBUG_BLACK_PIXELS = False  # Set to True to analyze black pixels specifically
DEBUG_DELTA_FRAMES = False  # Set to True to debug delta frame details
FORCE_FULL_UPDATES = False  # Set to True to force updating all pixels on every frame

# Frame buffer configuration
DEFAULT_BUFFER_SIZE = 20  # Number of frames to buffer
DEFAULT_BUFFER_PLAYBACK_RATE = 30  # Target FPS for buffered playback
ENABLE_FRAME_BUFFER = True  # Enable frame buffering
PRIORITY_FRAME_BYPASS = True  # Allow high-priority frames to bypass buffer

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

        # Debug options
        self.debug_frames = args.debug_frames
        self.debug_black_pixels = args.debug_black_pixels
        self.debug_delta_frames = args.debug_delta_frames
        self.force_full_updates = args.force_full_updates

        # LED state tracking for correct delta frame handling
        # This represents the current state of the LED display
        self.current_led_state = [(0, 0, 0) for _ in range(self.led_count)]
        self.led_state_initialized = False

        # Frame counter for debugging
        self.frame_counter = 0

        # Pattern tracking
        self.last_pattern_id = None
        self.last_parameters = None

        # Grid layout options
        self.layout = args.layout
        self.flip_x = args.flip_x
        self.flip_y = args.flip_y
        self.transpose = args.transpose

        # Frame buffer settings
        self.enable_buffer = args.enable_buffer
        self.buffer_size = args.buffer_size
        self.buffer_playback_rate = args.buffer_rate
        self.frame_buffer = []  # Queue of frames to be displayed
        self.buffer_lock = threading.Lock()  # Thread safety for buffer access
        self.buffer_running = False  # Flag to control buffer playback thread
        self.last_displayed_frame_id = None  # Track the last displayed frame ID
        self.priority_pattern_change = False  # Flag for high-priority pattern changes

        # Log grid configuration
        logger.info(
            f"Grid configuration: {self.width}x{self.height}, layout={self.layout}"
        )
        logger.info(
            f"Grid orientation: flip_x={self.flip_x}, flip_y={self.flip_y}, transpose={self.transpose}"
        )
        if self.enable_buffer:
            logger.info(
                f"Frame buffer enabled: size={self.buffer_size}, target rate={self.buffer_playback_rate}fps"
            )
        else:
            logger.info("Frame buffer disabled - using direct mode")

        # Statistics
        self.stats = {
            "frames_received": 0,
            "frames_displayed": 0,
            "frames_dropped": 0,
            "frames_buffered": 0,
            "batch_frames_received": 0,  # Counter for frames received in batch mode
            "fps": 0,
            "last_frame_time": 0,
            "buffer_fullness": 0,
            "buffer_underruns": 0,
            "buffer_overruns": 0,
            "connection_drops": 0,
            "target_fps": self.buffer_playback_rate,
            "connection_uptime": 0,
            "connection_start_time": 0,
            "last_dashboard_sync": 0,
            "last_stats_time": time.time(),
            "last_pong_time": time.time(),
            "last_ping_time": 0,
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
            # Also update state tracking
            self.current_led_state[i] = (0, 0, 0)

        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        # We've now initialized the LED state
        self.led_state_initialized = True

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

            # Increment frame counter
            self.frame_counter += 1

            # Force a full clear every X frames if full updates are enabled
            if self.force_full_updates:
                priority = True
                if self.frame_counter % 10 == 0:  # Every 10 frames
                    logger.debug(f"Forcing full update on frame {self.frame_counter}")
                    self.clear_leds()
                    self.led_state_initialized = True

            # Extract pixel data based on message type
            pixel_data = data[10:]

            # For full frames, ensure we update the state properly
            if msg_type == 1:  # Full frame
                self.update_leds_from_pixels(
                    pixel_data, width, height, priority=priority
                )
                # A full frame should always initialize the LED state
                self.led_state_initialized = True
            elif msg_type == 2:  # Delta frame
                if self.force_full_updates:
                    # Convert delta frame to full frame update
                    logger.debug(
                        f"Converting delta frame to full update on frame {self.frame_counter}"
                    )
                    self.update_leds_from_pixels(
                        pixel_data, width, height, priority=True
                    )
                    self.led_state_initialized = True
                else:
                    # If LED state isn't initialized yet, we should initialize with a full black frame
                    if not self.led_state_initialized:
                        logger.info("Initializing LED state before first delta frame")
                        self.clear_leds()
                        self.led_state_initialized = True

                    # Now apply the delta frame
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

        # For debugging, keep track of which pixels should be black
        if self.debug_black_pixels:
            black_pixels_sent = set()
            black_pixels_updated = set()
            non_black_pixels = set()

        # Clear all LEDs first if this is a priority update (redundant if already cleared by pattern change)
        if priority:
            for i in range(self.led_count):
                if HARDWARE_AVAILABLE:
                    self.strip[i] = (0, 0, 0)
                else:
                    self.strip.setPixelColor(i, 0)
                self.current_led_state[i] = (0, 0, 0)  # Update state tracking
            self.led_state_initialized = True

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

                    # For black pixel debugging
                    if self.debug_black_pixels and r == 0 and g == 0 and b == 0:
                        black_pixels_sent.add((x, y))

                    # Map to physical LED position
                    dest_idx = self.map_pixel_index(x, y)

                    if 0 <= dest_idx < self.led_count:
                        updated_leds.add(dest_idx)

                        # For black pixel debugging - check if we're turning a pixel off
                        if self.debug_black_pixels:
                            if r == 0 and g == 0 and b == 0:
                                black_pixels_updated.add(dest_idx)
                            else:
                                non_black_pixels.add(dest_idx)

                        # Keep track of current state for delta frame handling
                        old_value = self.current_led_state[dest_idx]
                        new_value = (r, g, b)
                        self.current_led_state[dest_idx] = new_value

                        # Debug significant changes
                        if self.debug_frames and old_value != new_value:
                            if self.debug_black_pixels and (
                                old_value == (0, 0, 0) or new_value == (0, 0, 0)
                            ):
                                logger.debug(
                                    f"Pixel at {x},{y} (idx {dest_idx}) changed: {old_value} -> {new_value}"
                                )

                        if HARDWARE_AVAILABLE:
                            self.strip[dest_idx] = (r, g, b)
                        else:
                            color = (r << 16) | (g << 8) | b
                            self.strip.setPixelColor(dest_idx, color)

        # We've now initialized the LED state
        self.led_state_initialized = True

        # Show the strip
        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        # Debug black pixel handling
        if self.debug_black_pixels:
            if black_pixels_sent:
                logger.debug(
                    f"Frame sent {len(black_pixels_sent)} black pixels, updated {len(black_pixels_updated)} LEDs"
                )
                if len(black_pixels_sent) > 10:
                    logger.debug(
                        f"First 10 black pixels sent (x,y): {list(black_pixels_sent)[:10]}"
                    )
            if len(non_black_pixels) > 0:
                logger.debug(f"Updated {len(non_black_pixels)} non-black pixels")

        # Only log detailed info at lower fps or for priority updates
        if priority or self.stats["fps"] < 20:
            logger.debug(f"Updated {len(updated_leds)} LEDs from full frame")

    def apply_delta_frame(self, delta_data, priority=False):
        """Apply a delta frame (only changed pixels)"""
        if len(delta_data) < 2:
            logger.warning("Delta frame too small")
            return

        # If LED state hasn't been initialized yet, treat this as a full frame priority update
        if not self.led_state_initialized:
            logger.warning(
                "LED state not initialized, treating delta frame as priority full frame"
            )
            if delta_data and len(delta_data) >= 2:
                # First render a full black frame to initialize all LEDs
                self.clear_leds()
                # Then apply the deltas as a priority update
                self.apply_delta_frame(delta_data, priority=True)
            return

        # First 2 bytes are the number of deltas - using little-endian
        num_deltas = struct.unpack("<H", delta_data[0:2])[0]
        delta_data = delta_data[2:]

        # Log delta frame details if debug is enabled
        if self.debug_delta_frames:
            logger.debug(f"Processing delta frame with {num_deltas} changes")

        if len(delta_data) < num_deltas * 5:
            logger.warning(
                f"Not enough delta data: got {len(delta_data)} bytes, expected {num_deltas * 5}"
            )
            return

        # For debugging
        if self.debug_black_pixels:
            black_pixels_sent = set()
            black_pixels_updated = set()
            non_black_pixels = set()

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

                # Convert linear index to x,y for mapping and debugging
                x = pixel_index % self.width
                y = pixel_index // self.width

                # Debug delta frame details
                if self.debug_delta_frames:
                    if i < 10 or i > num_deltas - 10:  # First/last 10 pixels
                        logger.debug(f"Delta#{i}: Pixel({x},{y}) = RGB({r},{g},{b})")

                # For black pixel debugging
                if self.debug_black_pixels and r == 0 and g == 0 and b == 0:
                    black_pixels_sent.add((x, y))

                # Map to physical LED position
                dest_idx = self.map_pixel_index(x, y)

                if 0 <= dest_idx < self.led_count:
                    updated_leds.add(dest_idx)

                    # For black pixel debugging
                    if self.debug_black_pixels:
                        if r == 0 and g == 0 and b == 0:
                            black_pixels_updated.add(dest_idx)
                        else:
                            non_black_pixels.add(dest_idx)

                    # Keep track of current state for delta frame handling
                    old_value = self.current_led_state[dest_idx]
                    new_value = (r, g, b)

                    # Debug delta frame changes
                    if self.debug_delta_frames and old_value != new_value:
                        logger.debug(
                            f"Updating LED {dest_idx} from {old_value} to {new_value}"
                        )

                    self.current_led_state[dest_idx] = new_value

                    # Debug significant changes
                    if self.debug_frames and old_value != new_value:
                        if self.debug_black_pixels and (
                            old_value == (0, 0, 0) or new_value == (0, 0, 0)
                        ):
                            logger.debug(
                                f"Delta pixel at {x},{y} (idx {dest_idx}) changed: {old_value} -> {new_value}"
                            )

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

        # Debug black pixel handling for delta frames
        if self.debug_black_pixels:
            if black_pixels_sent:
                logger.debug(
                    f"Delta frame sent {len(black_pixels_sent)} black pixels, updated {len(black_pixels_updated)} LEDs"
                )
                if len(black_pixels_sent) > 10:
                    logger.debug(
                        f"First 10 black pixels in delta (x,y): {list(black_pixels_sent)[:10]}"
                    )
            if len(non_black_pixels) > 0:
                logger.debug(
                    f"Delta frame updated {len(non_black_pixels)} non-black pixels"
                )

        # Additional debugging for how much of the frame actually changed
        if self.debug_delta_frames:
            percent_changed = 100 * num_deltas / (self.width * self.height)
            logger.debug(
                f"Delta frame updated {num_deltas}/{self.width * self.height} pixels ({percent_changed:.1f}%)"
            )

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

        # Set up batch request timer after connected
        # Initialize with a sensible default if not already done
        if not hasattr(self, "last_processed_batch"):
            self.last_processed_batch = 0

        # Request first batch after a short delay to allow connection to stabilize
        time.sleep(0.5)
        self.request_next_batch(urgent=True)

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

                    # Check if this is a batch frame message (starts with byte 0xB)
                    if message[0] == 0xB and len(message) >= 9:
                        logger.info(
                            f"Received batch frame message ({len(message)} bytes)"
                        )
                        self.process_batch_frames(message)
                        return

                    # Check if this might be a frame with protocol version 123
                    if message[0] == 123 and len(message[1:]) >= 10:
                        logger.info(
                            "Received binary message with protocol version 123, processing it"
                        )
                        # Process directly - priority frame
                        if self.enable_buffer:
                            self.buffer_frame(message, priority=True)
                        else:
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

                    # Use frame buffer if enabled
                    if self.enable_buffer:
                        self.buffer_frame(message)
                    else:
                        self.update_leds_from_binary(message)
                else:
                    logger.warning(
                        f"Received unknown binary message format ({len(message)} bytes)"
                    )
                    # Log the first few bytes for debugging
                    if len(message) > 0:
                        logger.debug(f"First 10 bytes: {message[:10].hex()}")

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
                        is_priority = False
                        clear_needed = False

                        # Check for pattern ID changes
                        if "pattern_id" in payload:
                            if (
                                not hasattr(self, "last_pattern_id")
                                or self.last_pattern_id != payload["pattern_id"]
                            ):
                                self.last_pattern_id = payload["pattern_id"]
                                clear_needed = True
                                is_priority = (
                                    True  # Pattern changes are highest priority
                                )
                                logger.info(
                                    f"New pattern detected (ID: {self.last_pattern_id}). Clearing LEDs."
                                )
                                # Force reinitialization of LED state when pattern changes
                                self.led_state_initialized = False

                                # If using buffer, clear it on pattern change
                                if self.enable_buffer:
                                    self.clear_frame_buffer()

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
                                            is_priority = (
                                                True  # Parameter changes get priority
                                            )

                            self.last_parameters = payload["parameters"].copy()
                            clear_needed = True
                            logger.info(
                                f"Pattern parameters changed.{param_diff} Clearing LEDs."
                            )
                            # Also reinitialize LED state on parameter changes
                            self.led_state_initialized = False

                            # If using buffer, clear it on parameter change
                            if self.enable_buffer:
                                self.clear_frame_buffer()

                        # Increment frame counter
                        self.frame_counter += 1

                        # Handle frame clearing logic
                        # Force a full clear periodically if full updates are enabled
                        if self.force_full_updates:
                            # Always treat as priority update which ensures full clearing
                            is_priority = True
                            force_clear = (
                                self.frame_counter % 10 == 0
                            )  # Every 10 frames
                            if force_clear:
                                logger.debug(
                                    f"Forcing full clear on frame {self.frame_counter}"
                                )
                                self.clear_leds()
                                self.led_state_initialized = True
                        # If not already cleared by force_full_updates, check if clear is needed from pattern/params
                        elif clear_needed:
                            logger.debug(
                                "Clearing LEDs due to pattern/parameter change"
                            )
                            self.clear_leds()
                            self.led_state_initialized = True

                        # Record time of frame receipt for latency measurements
                        receipt_time = time.time()

                        # The binary data is base64 encoded in JSON
                        try:
                            binary_data = base64.b64decode(payload["binary"])

                            # Record frame ID if available for dashboard sync
                            if "id" in payload:
                                self.last_displayed_frame_id = payload["id"]

                            # Only log at lower frame rates
                            if self.stats["fps"] < 20:
                                logger.debug(
                                    f"Received frame binary data of length {len(binary_data)}"
                                )

                            # Process frame - either buffer it or display immediately
                            if self.enable_buffer:
                                # Add to buffer (with priority flag if needed)
                                self.buffer_frame(binary_data, priority=is_priority)
                            else:
                                # Direct mode - process immediately
                                self.update_leds_from_binary(
                                    binary_data, priority=is_priority
                                )

                        except Exception as e:
                            logger.error(f"Error processing binary frame data: {e}")

                elif event == "request_stats":
                    # Send stats back to the server
                    self.send_stats()

                elif event == "request_detailed_stats":
                    # Send detailed stats
                    self.send_detailed_stats()

                elif event == "simulation_config":
                    # Handle simulation configuration changes
                    if "buffer_size" in payload:
                        new_size = int(payload["buffer_size"])
                        if new_size >= 1:
                            old_size = self.buffer_size
                            self.buffer_size = new_size
                            logger.info(
                                f"Changed buffer size from {old_size} to {new_size}"
                            )

                    if "buffer_rate" in payload:
                        new_rate = float(payload["buffer_rate"])
                        if new_rate > 0:
                            old_rate = self.buffer_playback_rate
                            self.buffer_playback_rate = new_rate
                            self.stats["target_fps"] = new_rate
                            logger.info(
                                f"Changed buffer playback rate from {old_rate} to {new_rate}"
                            )

                    if "enable_buffer" in payload:
                        enable = bool(payload["enable_buffer"])
                        if enable != self.enable_buffer:
                            self.enable_buffer = enable
                            if enable:
                                logger.info("Enabled frame buffer")
                            else:
                                logger.info("Disabled frame buffer")
                                self.clear_frame_buffer()

                elif event == "clear_display":
                    # Clear the display and buffer
                    logger.info("Received clear display command")
                    self.clear_leds()
                    if self.enable_buffer:
                        self.clear_frame_buffer()

                elif event == "display_batch":
                    # Handle batch display message
                    if "frames" in payload:
                        try:
                            # Decode the base64 batch data
                            batch_data = base64.b64decode(payload["frames"])
                            logger.info(
                                f"Received display_batch with {len(batch_data)} bytes of batch data"
                            )

                            # Process the batch frames
                            self.process_batch_frames(batch_data)
                        except Exception as e:
                            logger.error(f"Error processing display_batch: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
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
                "frames_buffered": self.stats["frames_buffered"],
                "frames_dropped": self.stats["frames_dropped"],
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "target_fps": self.stats["target_fps"],
                "buffer_enabled": self.enable_buffer,
                "buffer_fullness": round(self.stats["buffer_fullness"] * 100, 1),
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
                "frames_buffered": self.stats["frames_buffered"],
                "frames_dropped": self.stats["frames_dropped"],
                "buffer_underruns": self.stats["buffer_underruns"],
                "buffer_overruns": self.stats["buffer_overruns"],
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "target_fps": self.stats["target_fps"],
                "connection_uptime": self.stats["connection_uptime"],
                "buffer": {
                    "enabled": self.enable_buffer,
                    "size": self.buffer_size,
                    "current_size": len(self.frame_buffer),
                    "fullness": round(self.stats["buffer_fullness"] * 100, 1),
                    "playback_rate": self.buffer_playback_rate,
                },
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
                "last_displayed_frame": self.last_displayed_frame_id,
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
                    buffer_status_counter = 0
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

                            # Display buffer status periodically (every 5 cycles = 25 seconds)
                            buffer_status_counter += 1
                            if buffer_status_counter % 5 == 0 and self.enable_buffer:
                                self.display_buffer_status()

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

    def buffer_frame(self, frame_data, priority=False):
        """Add a frame to the buffer for playback
        Returns True if frame was added, False if it was dropped"""
        if not self.enable_buffer or not frame_data:
            return False

        # For priority frames (pattern changes, etc.), we might want to flush the buffer
        if priority and PRIORITY_FRAME_BYPASS:
            logger.debug(
                "Priority frame detected - bypassing buffer and displaying immediately"
            )
            # Display immediately
            self.update_leds_from_binary(frame_data, priority=True)
            # Clear buffer
            with self.buffer_lock:
                old_size = len(self.frame_buffer)
                self.frame_buffer.clear()
                self.stats["frames_dropped"] += old_size
                self.stats["buffer_fullness"] = 0
            # Still add to buffer as first frame
            with self.buffer_lock:
                self.frame_buffer.append((time.time(), frame_data))
                self.stats["frames_buffered"] += 1
                self.stats["buffer_fullness"] = (
                    len(self.frame_buffer) / self.buffer_size
                )
            return True

        # Normal frame handling - add to buffer if space available
        with self.buffer_lock:
            # Check if we're approaching buffer capacity
            buffer_fullness = len(self.frame_buffer) / self.buffer_size

            if buffer_fullness > 0.9 and not priority:
                # Buffer nearly full (90% or more) - implement adaptive dropping strategy
                # Drop every other frame to prevent overflow
                if self.stats["frames_buffered"] % 2 == 0:
                    logger.warning(
                        f"Buffer at {buffer_fullness:.1%} - dropping frame to prevent overflow"
                    )
                    self.stats["frames_dropped"] += 1
                    return False

            if len(self.frame_buffer) < self.buffer_size:
                # Add frame with timestamp
                self.frame_buffer.append((time.time(), frame_data))
                self.stats["frames_buffered"] += 1
                self.stats["buffer_fullness"] = (
                    len(self.frame_buffer) / self.buffer_size
                )

                # Start buffer playback thread if not already running
                if (
                    not self.buffer_running
                    and len(self.frame_buffer) >= self.buffer_size / 4
                ):
                    self.start_buffer_playback()
                return True
            else:
                # Buffer full - drop the frame
                self.stats["frames_dropped"] += 1
                self.stats["buffer_overruns"] += 1
                return False

    def start_buffer_playback(self):
        """Start the buffer playback thread"""
        if self.buffer_running:
            return  # Already running

        self.buffer_running = True

        # Start a thread to play back the buffered frames
        playback_thread = threading.Thread(target=self.buffer_playback_loop)
        playback_thread.daemon = True
        playback_thread.start()
        logger.info("Started frame buffer playback thread")

    def buffer_playback_loop(self):
        """Main loop for playing back buffered frames"""
        frame_interval = (
            1.0 / self.buffer_playback_rate
        )  # Time between frames in seconds
        last_frame_time = 0

        try:
            while self.buffer_running and running:
                current_time = time.time()

                # Calculate frame display time based on transition state
                current_interval = frame_interval
                if (
                    hasattr(self, "transition_speed_multiplier")
                    and self.transition_speed_multiplier > 1.0
                ):
                    # During transition, play frames faster
                    current_interval = frame_interval / self.transition_speed_multiplier

                    # Gradually reduce the multiplier back to 1.0
                    self.transition_speed_multiplier = max(
                        1.0, self.transition_speed_multiplier - 0.1
                    )

                    if self.transition_speed_multiplier == 1.0:
                        logger.info(
                            "Transition complete, resuming normal playback speed"
                        )

                # Check if it's time to display the next frame
                if current_time - last_frame_time >= current_interval:
                    # Get next frame from buffer
                    frame_data = None
                    with self.buffer_lock:
                        if self.frame_buffer:
                            # Get and remove the oldest frame
                            _, frame_data = self.frame_buffer.pop(0)
                            self.stats["buffer_fullness"] = (
                                len(self.frame_buffer) / self.buffer_size
                            )

                    if frame_data:
                        # Display the frame
                        self.update_leds_from_binary(frame_data, priority=False)
                        self.stats["frames_displayed"] += 1

                        # Calculate actual FPS with smoothing
                        current_time = time.time()
                        if last_frame_time > 0:
                            time_diff = current_time - last_frame_time
                            if time_diff > 0:
                                # 80% previous value, 20% new value for smoothing
                                self.stats["fps"] = 0.8 * self.stats["fps"] + 0.2 * (
                                    1.0 / time_diff
                                )

                        last_frame_time = current_time

                        # Synchronize dashboard with current state
                        self.sync_dashboard_state()
                    else:
                        # Buffer underrun - no frames available
                        self.stats["buffer_underruns"] += 1
                        logger.debug("Buffer underrun - no frames available")

                        # Request more frames immediately on underrun
                        self.request_next_batch(urgent=True)

                # Check if buffer is getting low, request more frames
                with self.buffer_lock:
                    if self.frame_buffer:
                        buffer_fullness = len(self.frame_buffer) / self.buffer_size
                        # Request more frames if buffer is less than 50% full
                        if buffer_fullness < 0.5:
                            # Only request if we haven't requested recently
                            if (
                                not hasattr(self, "last_batch_request_time")
                                or current_time - self.last_batch_request_time > 0.2
                            ):  # 200ms minimum between requests
                                self.request_next_batch()
                                self.last_batch_request_time = current_time
                    else:
                        # Empty buffer case - check if it's been empty for a while
                        if current_time - last_frame_time > 1.0:
                            logger.debug(
                                "Buffer empty for 1 second, attempting to refill"
                            )
                            self.request_next_batch(urgent=True)
                            # But don't stop playback thread, keep checking

                # Sleep for a small amount to avoid CPU spinning
                # Use 1/4 of frame interval to have good timing precision
                time.sleep(frame_interval / 4)

        except Exception as e:
            logger.error(f"Error in buffer playback thread: {e}")
            import traceback

            logger.error(traceback.format_exc())
            self.buffer_running = False

    def sync_dashboard_state(self):
        """Send synchronization data to the dashboard to keep it in sync with the display"""
        # Only sync periodically to avoid too much network traffic
        current_time = time.time()
        if (
            current_time - self.stats["last_dashboard_sync"] < 0.5
        ):  # Sync every 500ms max
            return

        # Create sync message with current display state
        try:
            sync_data = {
                "topic": "controller:lobby",
                "event": "display_sync",
                "payload": {
                    "controller_id": self.controller_id,
                    "timestamp": current_time,
                    "frame_id": self.last_displayed_frame_id,
                    "buffer_stats": {
                        "fullness": self.stats["buffer_fullness"],
                        "fps": self.stats["fps"],
                        "queue_length": len(self.frame_buffer),
                    },
                },
                "ref": None,
            }

            if self.ws and self.ws.sock and self.ws.sock.connected:
                self.ws.send(json.dumps(sync_data))
                self.stats["last_dashboard_sync"] = current_time
                logger.debug("Sent dashboard sync data")
        except Exception as e:
            logger.error(f"Error sending dashboard sync: {e}")

    def clear_frame_buffer(self):
        """Clear the frame buffer (used on pattern changes, errors, etc.)"""
        with self.buffer_lock:
            buffer_size = len(self.frame_buffer)
            self.frame_buffer.clear()
            self.stats["frames_dropped"] += buffer_size
            self.stats["buffer_fullness"] = 0
            logger.debug(f"Cleared frame buffer, dropped {buffer_size} frames")

    def display_buffer_status(self):
        """Display a simple visualization of buffer status in the logs"""
        if not self.enable_buffer:
            return

        with self.buffer_lock:
            buffer_size = len(self.frame_buffer)
            fullness = buffer_size / self.buffer_size

            # Create a simple text-based visualization
            blocks = 20
            filled = int(fullness * blocks)
            bar = "[" + "█" * filled + "·" * (blocks - filled) + "]"

            # Log the buffer status
            logger.info(
                f"Buffer status: {bar} {buffer_size}/{self.buffer_size} frames "
                f"({fullness * 100:.1f}%) - FPS: {self.stats['fps']:.1f}/{self.buffer_playback_rate}"
            )

            # Also include info about performance
            if self.stats["buffer_underruns"] > 0 or self.stats["buffer_overruns"] > 0:
                logger.info(
                    f"Performance: {self.stats['buffer_underruns']} underruns, "
                    f"{self.stats['buffer_overruns']} overruns, "
                    f"{self.stats['frames_dropped']} frames dropped"
                )

    def process_batch_frames(self, message):
        """Process a batch of frames sent in a single message

        Batch format:
        - Byte 0: 0xB (batch identifier)
        - Bytes 1-4: Frame count (uint32, little-endian)
        - Byte 5: Priority flag (1 = priority, 0 = normal)
        - Bytes 6-9: Sequence number (uint32, little-endian)
        - Bytes 10-17: Timestamp (uint64, little-endian)
        - For each frame:
          - 4 bytes: Frame length (uint32, little-endian)
          - N bytes: Frame data
        """
        try:
            # Parse batch header
            frame_count = struct.unpack("<I", message[1:5])[0]
            is_priority = message[5] == 1

            # Extract batch sequence and timestamp if available (bytes 6-17)
            batch_sequence = 0
            batch_timestamp = 0

            if len(message) >= 18:  # We have sequence and timestamp info
                batch_sequence = struct.unpack("<I", message[6:10])[0]
                batch_timestamp = struct.unpack("<Q", message[10:18])[0]
                logger.info(
                    f"Received batch sequence #{batch_sequence} with timestamp {batch_timestamp}, contains {frame_count} frames"
                )
                offset = 18  # Start of frame data
            else:
                # Backward compatibility with old format
                logger.info(f"Received legacy batch without sequence info")
                offset = 6  # Start of frame data in old format

            # Check if this batch should be processed or discarded based on sequence
            if hasattr(self, "last_processed_batch") and batch_sequence > 0:
                # If we receive an older batch than what we've already processed, discard it
                if batch_sequence < self.last_processed_batch and not is_priority:
                    logger.warning(
                        f"Discarding out-of-sequence batch #{batch_sequence} (already processed #{self.last_processed_batch})"
                    )
                    return

                # If we receive a batch that's more than one ahead of what we expect, log a warning
                if batch_sequence > self.last_processed_batch + 1 and not is_priority:
                    logger.warning(
                        f"Received batch #{batch_sequence} but expected #{self.last_processed_batch + 1} - possible missing batch"
                    )

            if is_priority:
                logger.info(
                    f"Priority batch #{batch_sequence} received with {frame_count} frames"
                )

                # Implement transitional approach for priority batches
                with self.buffer_lock:
                    # Keep track of how many frames we've played from previous pattern
                    previous_pattern_frames = len(self.frame_buffer)

                    # We don't completely clear the buffer, but we mark all existing frames
                    # to be played quickly in a shortened timeframe
                    if previous_pattern_frames > 0:
                        logger.info(
                            f"Transitioning from previous pattern with {previous_pattern_frames} frames remaining"
                        )
                        # Adjust play speed for existing frames to complete faster
                        self.transition_speed_multiplier = 3.0  # Play 3x faster
                    else:
                        # No transition needed
                        self.transition_speed_multiplier = 1.0
            else:
                logger.debug(
                    f"Processing regular batch #{batch_sequence} with {frame_count} frames"
                )
                # Regular frame batch - no transition needed
                if not hasattr(self, "transition_speed_multiplier"):
                    self.transition_speed_multiplier = 1.0

            frames_processed = 0

            while offset < len(message) and frames_processed < frame_count:
                # Check if we have enough data for the frame length
                if offset + 4 > len(message):
                    logger.warning(
                        f"Batch truncated at frame {frames_processed + 1}/{frame_count}"
                    )
                    break

                # Get frame length
                frame_length = struct.unpack("<I", message[offset : offset + 4])[0]
                offset += 4

                # Check if we have enough data for the frame
                if offset + frame_length > len(message):
                    logger.warning(
                        f"Batch truncated, frame {frames_processed + 1} incomplete"
                    )
                    break

                # Extract frame data
                frame_data = message[offset : offset + frame_length]
                offset += frame_length

                # Process the frame (buffer or display directly)
                if self.enable_buffer:
                    # For priority frames or when the buffer is empty, process immediately
                    if is_priority or len(self.frame_buffer) == 0:
                        self.buffer_frame(frame_data, priority=is_priority)
                    else:
                        # Add to buffer with a small delay to avoid flooding
                        self.buffer_frame(frame_data, priority=False)
                else:
                    # Direct mode - process immediately
                    self.update_leds_from_binary(frame_data, priority=is_priority)

                frames_processed += 1

            # Update stats
            self.stats["batch_frames_received"] += frames_processed

            # If we processed all frames, log success
            if frames_processed == frame_count:
                logger.info(
                    f"Successfully processed all {frame_count} frames in batch #{batch_sequence}"
                )
            else:
                logger.warning(
                    f"Processed {frames_processed}/{frame_count} frames in batch #{batch_sequence}"
                )

            # Update the last processed batch sequence
            if batch_sequence > 0:
                self.last_processed_batch = batch_sequence

            # Schedule next batch request soon after processing, especially for priority
            if is_priority:
                self.request_next_batch_soon(100)  # Request more in 100ms
            else:
                # Regular request timing based on buffer fullness
                buffer_fullness = (
                    len(self.frame_buffer) / self.buffer_size
                    if self.enable_buffer
                    else 0
                )
                # The emptier the buffer, the sooner we request
                delay = int(
                    1000 * (0.2 + buffer_fullness * 0.3)
                )  # 200-500ms based on fullness
                self.request_next_batch_soon(delay)

        except Exception as e:
            logger.error(f"Error processing batch frames: {e}")
            import traceback

            logger.error(traceback.format_exc())

            # Log the batch header for debugging
            if len(message) >= 10:
                logger.error(f"Batch header: {message[:10].hex()}")

    def request_next_batch_soon(self, delay_ms=100):
        """Schedule a batch request soon after a priority change"""

        def request_batch():
            self.request_next_batch(urgent=True)

        threading.Timer(delay_ms / 1000.0, request_batch).start()

    def request_next_batch(self, urgent=False):
        """Request the next batch of frames from the server"""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            # Calculate how many frames we can safely accept
            if self.enable_buffer:
                space_available = max(0, self.buffer_size - len(self.frame_buffer))
                # Don't request if buffer is too full (>75%) unless urgent
                if len(self.frame_buffer) / self.buffer_size > 0.75 and not urgent:
                    logger.debug(
                        f"Buffer at {len(self.frame_buffer) / self.buffer_size:.1%} - deferring batch request"
                    )
                    return
            else:
                space_available = 30  # Default for non-buffered mode

            request = {
                "topic": "controller:lobby",
                "event": "request_batch",
                "payload": {
                    "controller_id": self.controller_id,
                    "last_sequence": getattr(self, "last_processed_batch", 0),
                    "space_available": space_available,
                    "urgent": urgent,
                    "timestamp": int(time.time() * 1000),
                },
                "ref": None,
            }

            self.ws.send(json.dumps(request))
            logger.debug(
                f"Requested next batch after sequence #{getattr(self, 'last_processed_batch', 0)}, space: {space_available}, urgent: {urgent}"
            )


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
        help=f"LED brightness (0-255) (default: {DEFAULT_BRIGHTNESS})",
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

    # Grid layout options
    parser.add_argument(
        "--layout",
        type=str,
        default=DEFAULT_LAYOUT,
        choices=["linear", "serpentine"],
        help=f"Grid layout (default: {DEFAULT_LAYOUT})",
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
        help="Transpose grid (rotate 90 degrees)",
    )

    # Debug options
    parser.add_argument(
        "--debug-frames",
        action="store_true",
        default=DEBUG_FRAMES,
        help="Debug frame processing",
    )
    parser.add_argument(
        "--debug-black-pixels",
        action="store_true",
        default=DEBUG_BLACK_PIXELS,
        help="Debug black pixel handling",
    )
    parser.add_argument(
        "--debug-delta-frames",
        action="store_true",
        default=DEBUG_DELTA_FRAMES,
        help="Debug delta frame processing",
    )
    parser.add_argument(
        "--force-full-updates",
        action="store_true",
        default=FORCE_FULL_UPDATES,
        help="Force full frame updates",
    )

    # Buffer options
    parser.add_argument(
        "--enable-buffer",
        action="store_true",
        default=ENABLE_FRAME_BUFFER,
        help="Enable frame buffering for smoother playback",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=DEFAULT_BUFFER_SIZE,
        help=f"Size of frame buffer (default: {DEFAULT_BUFFER_SIZE})",
    )
    parser.add_argument(
        "--buffer-rate",
        type=float,
        default=DEFAULT_BUFFER_PLAYBACK_RATE,
        help=f"Target FPS for buffer playback (default: {DEFAULT_BUFFER_PLAYBACK_RATE})",
    )
    parser.add_argument(
        "--no-priority-bypass",
        action="store_false",
        dest="priority_bypass",
        default=PRIORITY_FRAME_BYPASS,
        help="Disable priority frame bypass (all frames go through buffer)",
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
