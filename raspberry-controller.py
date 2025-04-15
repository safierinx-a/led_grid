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
    "ws://192.168.1.11:4000/controller/websocket"  # Updated with correct websocket path
)
DEFAULT_LOG_LEVEL = "INFO"

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
                # Modified to use the correct neopixel interface
                # The original code was:
                # self.strip = neopixel.NeoPixel(
                #     pin=board.D18,  # Pin 18 (BCM numbering)
                #     n=self.led_count,
                #     brightness=self.brightness / 255.0,
                #     auto_write=False,
                #     pixel_order=neopixel.GRB,
                # )

                # Try with Adafruit CircuitPython library format
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

    def update_leds_from_binary(self, data):
        """Update LEDs from binary frame data"""
        # Check if we have enough data for the header
        if len(data) < 10:
            logger.warning(f"Received incomplete binary frame: {len(data)} bytes")
            return

        # Parse the header - FIXED to use little-endian to match server encoding
        version = data[0]
        msg_type = data[1]
        frame_id = struct.unpack("<I", data[2:6])[
            0
        ]  # Changed from ">" to "<" for little-endian
        width = struct.unpack("<H", data[6:8])[
            0
        ]  # Changed from ">" to "<" for little-endian
        height = struct.unpack("<H", data[8:10])[
            0
        ]  # Changed from ">" to "<" for little-endian

        # Log header info for debugging
        logger.debug(
            f"Frame header: version={version}, type={msg_type}, id={frame_id}, dims={width}x{height}"
        )

        # Validate header
        if version != 1:
            logger.warning(f"Unsupported protocol version: {version}")
            return

        if msg_type not in (1, 2):
            logger.warning(f"Unknown message type: {msg_type}")
            return

        if width != self.width or height != self.height:
            logger.warning(
                f"Frame dimensions mismatch: {width}x{height} (expected {self.width}x{self.height})"
            )
            # Continue anyway, as this might just be a configuration issue

        # Extract pixel data based on message type
        pixel_data = data[10:]
        if msg_type == 1:  # Full frame
            self.update_leds_from_pixels(pixel_data)
        elif msg_type == 2:  # Delta frame
            self.apply_delta_frame(pixel_data)

        # Update stats
        self.stats["frames_received"] += 1
        current_time = time.time()
        if self.stats["last_frame_time"] > 0:
            time_diff = current_time - self.stats["last_frame_time"]
            if time_diff > 0:
                self.stats["fps"] = 1.0 / time_diff
        self.stats["last_frame_time"] = current_time
        self.stats["frames_displayed"] += 1

    def update_leds_from_pixels(self, pixel_data):
        """Update all LEDs from pixel data (full frame)"""
        if len(pixel_data) < self.led_count * 3:
            logger.warning(
                f"Not enough pixel data: got {len(pixel_data)} bytes, expected {self.led_count * 3}"
            )
            # Still try to update as many pixels as we can

        pixel_count = min(self.led_count, len(pixel_data) // 3)
        for i in range(pixel_count):
            index = i * 3
            if index + 2 < len(pixel_data):
                r = pixel_data[index]
                g = pixel_data[index + 1]
                b = pixel_data[index + 2]

                if HARDWARE_AVAILABLE:
                    self.strip[i] = (r, g, b)
                else:
                    color = (r << 16) | (g << 8) | b
                    self.strip.setPixelColor(i, color)

        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

        logger.debug(f"Updated {pixel_count} LEDs from full frame")

    def apply_delta_frame(self, delta_data):
        """Apply a delta frame (only changed pixels)"""
        if len(delta_data) < 2:
            logger.warning("Delta frame too small")
            return

        # First 2 bytes are the number of deltas - also fixed to little-endian
        num_deltas = struct.unpack("<H", delta_data[0:2])[0]  # Changed from ">" to "<"
        delta_data = delta_data[2:]

        if len(delta_data) < num_deltas * 5:
            logger.warning(
                f"Not enough delta data: got {len(delta_data)} bytes, expected {num_deltas * 5}"
            )
            return

        for i in range(num_deltas):
            index = i * 5
            if index + 4 < len(delta_data):
                # 2 bytes for pixel index, 3 bytes for RGB - fixed to little-endian
                pixel_index = struct.unpack("<H", delta_data[index : index + 2])[
                    0
                ]  # Changed from ">" to "<"
                r = delta_data[index + 2]
                g = delta_data[index + 3]
                b = delta_data[index + 4]

                if pixel_index < self.led_count:
                    if HARDWARE_AVAILABLE:
                        self.strip[pixel_index] = (r, g, b)
                    else:
                        color = (r << 16) | (g << 8) | b
                        self.strip.setPixelColor(pixel_index, color)

        if HARDWARE_AVAILABLE:
            self.strip.show()
        else:
            self.strip.show()

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
                # Process binary frame
                self.update_leds_from_binary(message)
            else:
                # Process Phoenix Channel message (JSON)
                data = json.loads(message)

                # Extract event and payload from Phoenix message format
                event = data.get("event")
                payload = data.get("payload", {})

                logger.debug(f"Received event: {event}")

                if event == "phx_reply" and payload.get("status") == "ok":
                    # Join confirmation
                    logger.info("Successfully joined channel")

                elif event == "frame":
                    # Handle frame message - contains binary data in payload["binary"]
                    if "binary" in payload:
                        # The binary data is base64 encoded in JSON
                        binary_data = base64.b64decode(payload["binary"])
                        logger.debug(
                            f"Received frame binary data of length {len(binary_data)}"
                        )
                        self.update_leds_from_binary(binary_data)

                elif event == "request_stats":
                    # Send stats in response to request
                    self.send_stats()

                elif event == "request_detailed_stats":
                    # Send detailed stats
                    self.send_detailed_stats()

                elif event == "simulation_config":
                    # Apply simulation config
                    logger.info(f"Received simulation config: {payload}")
                    # Apply simulation settings here if needed

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
            import traceback

            logger.error(traceback.format_exc())

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
                "fps": self.stats["fps"],
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
                "fps": self.stats["fps"],
                "connection_uptime": self.stats["connection_uptime"],
                "hardware_info": {
                    "type": "Raspberry Pi" if HARDWARE_AVAILABLE else "Mock",
                    "led_count": self.led_count,
                    "width": self.width,
                    "height": self.height,
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
                # Create WebSocket connection
                # Use the proper Phoenix Channel WebSocket path
                self.ws = websocket.WebSocketApp(
                    self.server_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )

                # Set connection start time
                self.stats["connection_start_time"] = time.time()

                # Start a thread to send stats periodically
                def stats_sender():
                    while running and self.ws.sock and self.ws.sock.connected:
                        self.send_stats()
                        time.sleep(5)  # Send stats every 5 seconds

                # Start the WebSocket connection
                from threading import Thread

                stats_thread = Thread(target=stats_sender)
                stats_thread.daemon = True

                # Connect to the server
                logger.info(f"Connecting to {self.server_url}...")
                self.ws.run_forever()

                # If we get here, the connection was closed
                if running:
                    logger.info(
                        f"Connection lost. Reconnecting in {reconnect_delay} seconds..."
                    )
                    time.sleep(reconnect_delay)

                    # Increase reconnect delay up to a maximum of 30 seconds
                    reconnect_delay = min(reconnect_delay * 1.5, 30.0)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                if running:
                    logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 30.0)

    def signal_handler(self, sig, frame):
        """Handle termination signals"""
        global running
        logger.info("Received termination signal. Shutting down...")
        running = False

        # Cleanup
        self.clear_leds()

        if self.ws:
            self.ws.close()


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

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Set log level
    logger.setLevel(getattr(logging, args.log_level))

    # Initialize and run the controller
    controller = LegridController(args)
    controller.run()
