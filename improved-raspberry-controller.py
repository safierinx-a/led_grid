#!/usr/bin/env python3
"""
Legrid LED Matrix Controller - Improved Raspberry Pi Client

This script connects to a Phoenix server via WebSocket and controls
WS2812B/NeoPixel LED strips/matrices according to the frames received.

Improvements over original controller:
- Better connection management (prevents multiple connections)
- Proper batch request coordination
- Improved buffer management
- Smoother pattern transitions
- Failure recovery without buffer overruns
- Comprehensive status reporting to server
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
import queue

# Try to import the rpi_ws281x library for hardware control
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
DEFAULT_SERVER_URL = "ws://localhost:4000/controller/websocket"
DEFAULT_LOG_LEVEL = "INFO"

# Grid layout and orientation options
DEFAULT_LAYOUT = "serpentine"  # Could be "linear" or "serpentine"
DEFAULT_FLIP_X = False
DEFAULT_FLIP_Y = False
DEFAULT_TRANSPOSE = False

# Frame buffer configuration
DEFAULT_BUFFER_SIZE = 20  # Number of frames to buffer
DEFAULT_BUFFER_PLAYBACK_RATE = 30  # Target FPS for buffered playback
ENABLE_FRAME_BUFFER = True
PRIORITY_FRAME_BYPASS = True

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


class ConnectionManager:
    """
    Manages the WebSocket connection to the server with better error handling
    and prevents multiple connections from being created simultaneously.
    """

    def __init__(self, url, controller):
        self.url = url
        self.controller = controller
        self.ws = None
        self.connected = False
        self.connecting = False
        self.last_pong_time = 0
        self.connection_start_time = 0
        self.missing_pong_count = 0
        self.connection_timeout = 30  # Seconds
        self.state = "disconnected"
        self.reconnect_timer = None
        self.reconnect_delay = 1.0
        self.connection_attempts = 0
        self.connection_lock = threading.Lock()  # Prevent multiple connection attempts

    def connect(self):
        """Establish connection to the server if not already connected"""
        with self.connection_lock:
            if self.connecting or self.connected:
                logger.debug(
                    "Already connecting or connected, ignoring connect request"
                )
                return False

            self.connecting = True
            self.state = "connecting"

        logger.info(f"Connecting to {self.url}...")

        try:
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_ping=lambda ws, message: logger.debug("Received ping"),
                on_pong=self.on_pong,
            )

            # Start monitoring thread
            self.monitoring_thread = threading.Thread(target=self.monitor_connection)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()

            # Start connection thread
            self.connection_thread = threading.Thread(target=self._run_connection)
            self.connection_thread.daemon = True
            self.connection_thread.start()

            return True
        except Exception as e:
            logger.error(f"Error setting up connection: {e}")
            self.connecting = False
            self.state = "error"
            return False

    def _run_connection(self):
        """Run the WebSocket connection in a separate thread"""
        try:
            # Configure WebSocket to handle binary data properly
            websocket.enableTrace(False)

            # Reset connection status
            self.connection_start_time = time.time()
            self.last_pong_time = time.time()
            self.connection_attempts += 1

            # Start the WebSocket connection
            try:
                self.ws.run_forever(ping_interval=5, ping_timeout=3)
            except Exception as e:
                logger.error(f"WebSocket run_forever error: {e}")

            # If we get here, connection has closed
            logger.info("WebSocket connection ended")
            self.connected = False
            self.connecting = False
            self.state = "disconnected"

            # Schedule reconnection after delay if still running
            if running:
                delay = min(
                    self.reconnect_delay * (1 + (self.connection_attempts / 10)), 30
                )
                logger.info(f"Scheduling reconnection in {delay:.1f} seconds")
                self.reconnect_timer = threading.Timer(delay, self.connect)
                self.reconnect_timer.daemon = True
                self.reconnect_timer.start()
        except Exception as e:
            logger.error(f"Error in connection thread: {e}")
            self.connected = False
            self.connecting = False
            self.state = "error"

    def monitor_connection(self):
        """Monitor connection health and send heartbeats"""
        while running and (self.connecting or self.connected):
            try:
                now = time.time()

                # Check connection health if we're supposedly connected
                if (
                    self.connected
                    and now - self.last_pong_time > self.connection_timeout
                ):
                    self.missing_pong_count += 1
                    logger.warning(
                        f"No pong received in {self.connection_timeout} seconds. Count: {self.missing_pong_count}"
                    )

                    # If we've missed too many pongs, force reconnection
                    if self.missing_pong_count >= 3:
                        logger.error(
                            "Connection appears to be dead. Forcing reconnection..."
                        )
                        self.close(reconnect=True)
                        break

                    # Try sending a ping to check connection
                    if self.ws and self.ws.sock and self.ws.sock.connected:
                        self.ws.ping("ping")

                # If we're connected, send Phoenix heartbeat
                if (
                    self.connected
                    and self.ws
                    and self.ws.sock
                    and self.ws.sock.connected
                ):
                    try:
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
                logger.error(f"Error in monitor thread: {e}")

            # Check again after 10 seconds
            time.sleep(10)

    def close(self, reconnect=False):
        """Close the WebSocket connection"""
        if self.ws:
            try:
                # Send a clean disconnect message if possible
                if self.connected and self.ws.sock and self.ws.sock.connected:
                    try:
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

                # Close the WebSocket
                self.ws.close()
                logger.info("Closed WebSocket connection")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")

        # Reset status
        self.connected = False
        self.connecting = False
        self.state = "disconnected"

        # Schedule reconnection if requested
        if reconnect and running:
            delay = min(
                self.reconnect_delay * (1 + (self.connection_attempts / 10)), 30
            )
            logger.info(f"Scheduling reconnection in {delay:.1f} seconds")
            self.reconnect_timer = threading.Timer(delay, self.connect)
            self.reconnect_timer.daemon = True
            self.reconnect_timer.start()

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")
        self.connected = True
        self.connecting = False
        self.state = "connected"
        self.missing_pong_count = 0
        self.last_pong_time = time.time()

        # Forward to controller
        self.controller.handle_connection_open()

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        # Update connection health
        self.last_pong_time = time.time()

        # Forward to controller for processing
        self.controller.handle_message(message)

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        self.state = "error"

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.connected = False
        self.connecting = False
        self.state = "disconnected"

        # Forward to controller
        self.controller.handle_connection_close()

    def on_pong(self, ws, message):
        """Handle pong responses from the server"""
        logger.debug("Received pong from server")
        self.last_pong_time = time.time()
        self.missing_pong_count = 0

    def send(self, message):
        """Send a message to the server"""
        if (
            not self.connected
            or not self.ws
            or not self.ws.sock
            or not self.ws.sock.connected
        ):
            logger.warning("Cannot send message - not connected")
            return False

        try:
            if isinstance(message, dict):
                # Send as JSON
                self.ws.send(json.dumps(message))
            elif isinstance(message, bytes):
                # Send as binary
                self.ws.send(message, opcode=websocket.ABNF.OPCODE_BINARY)
            else:
                # Send as text
                self.ws.send(str(message))
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def is_connected(self):
        """Check if we're connected to the server"""
        return self.connected and self.ws and self.ws.sock and self.ws.sock.connected


class FrameBuffer:
    """
    Manages a buffer of frames to be displayed with proper timing
    and coordination with the server.
    """

    def __init__(self, size, playback_rate):
        self.buffer_size = size
        self.playback_rate = playback_rate
        self.frames = []
        self.buffer_lock = threading.Lock()
        self.playing = False
        self.play_thread = None
        self.last_displayed_frame_id = None
        self.last_batch_sequence = 0
        self.transition_speed_multiplier = 1.0
        self.stats = {
            "frames_received": 0,
            "frames_displayed": 0,
            "frames_dropped": 0,
            "buffer_fullness": 0.0,
            "buffer_underruns": 0,
            "buffer_overruns": 0,
            "fps": 0.0,
            "last_frame_time": 0,
            "target_fps": playback_rate,
        }
        self.last_stats_update = time.time()

    def start(self):
        """Start the frame buffer playback thread"""
        if self.playing:
            logger.debug("Frame buffer already playing, ignoring start request")
            return

        self.playing = True
        self.play_thread = threading.Thread(target=self._playback_loop)
        self.play_thread.daemon = True
        self.play_thread.start()
        logger.info("Frame buffer playback started")

    def stop(self):
        """Stop the frame buffer playback thread"""
        self.playing = False
        logger.info("Frame buffer playback stopped")

    def _playback_loop(self):
        """Main loop for playing back buffered frames at a consistent rate"""
        frame_interval = 1.0 / self.playback_rate  # Time between frames
        last_frame_time = 0

        try:
            while self.playing:
                current_time = time.time()

                # Calculate frame display time based on transition state
                current_interval = frame_interval
                if self.transition_speed_multiplier > 1.0:
                    # During transition, play frames faster
                    current_interval = frame_interval / self.transition_speed_multiplier

                    # Gradually reduce the multiplier back to 1.0
                    self.transition_speed_multiplier = max(
                        1.0, self.transition_speed_multiplier - 0.1
                    )

                # Check if it's time to display the next frame
                if current_time - last_frame_time >= current_interval:
                    # Get next frame from buffer
                    frame_data = None
                    with self.buffer_lock:
                        if self.frames:
                            # Get and remove the oldest frame
                            frame_data, frame_id, _ = self.frames.pop(0)
                            self.last_displayed_frame_id = frame_id
                            # Update buffer fullness stat
                            self.stats["buffer_fullness"] = (
                                len(self.frames) / self.buffer_size
                            )

                    if frame_data:
                        # Signal that we have a frame to display
                        self._display_frame(frame_data)
                        self.stats["frames_displayed"] += 1

                        # Calculate FPS with smoothing
                        if last_frame_time > 0:
                            time_diff = current_time - last_frame_time
                            if time_diff > 0:
                                self.stats["fps"] = 0.8 * self.stats["fps"] + 0.2 * (
                                    1.0 / time_diff
                                )

                        last_frame_time = current_time
                    else:
                        # Buffer underrun - no frames available
                        if (
                            time.time() - self.last_stats_update > 1.0
                        ):  # Log max once per second
                            logger.debug("Buffer underrun - no frames available")
                            self.stats["buffer_underruns"] += 1
                            self.last_stats_update = time.time()

                # Update stats periodically
                if current_time - self.last_stats_update > 5.0:
                    self._update_stats()
                    self.last_stats_update = current_time

                # Sleep for a small amount to avoid CPU spinning
                # Use 1/4 of frame interval to have good timing precision
                time.sleep(frame_interval / 4)

        except Exception as e:
            logger.error(f"Error in frame buffer playback thread: {e}")
            import traceback

            logger.error(traceback.format_exc())
            self.playing = False

    def _display_frame(self, frame_data):
        """Signal that a frame is ready for display - override in subclass"""
        pass

    def _update_stats(self):
        """Update and log buffer statistics"""
        with self.buffer_lock:
            buffer_fullness = (
                len(self.frames) / self.buffer_size if self.buffer_size > 0 else 0
            )

            # Create a simple text-based visualization
            blocks = 20
            filled = int(buffer_fullness * blocks)
            bar = "[" + "█" * filled + "·" * (blocks - filled) + "]"

            # Log the buffer status
            logger.info(
                f"Buffer status: {bar} {len(self.frames)}/{self.buffer_size} frames "
                f"({buffer_fullness * 100:.1f}%) - FPS: {self.stats['fps']:.1f}/{self.playback_rate}"
            )

            # Also include info about performance
            if self.stats["buffer_underruns"] > 0 or self.stats["buffer_overruns"] > 0:
                logger.info(
                    f"Performance: {self.stats['buffer_underruns']} underruns, "
                    f"{self.stats['buffer_overruns']} overruns, "
                    f"{self.stats['frames_dropped']} frames dropped"
                )

    def add_frame(self, frame_data, frame_id=None, priority=False):
        """Add a frame to the buffer"""
        with self.buffer_lock:
            # Update stats
            self.stats["frames_received"] += 1

            # Check if buffer is full
            if len(self.frames) >= self.buffer_size:
                # Buffer overflow - decide what to do
                if priority:
                    # For priority frames, make space by dropping oldest frame
                    self.frames.pop(0)
                    self.stats["frames_dropped"] += 1
                    logger.debug("Dropped oldest frame to make room for priority frame")
                else:
                    # For normal frames, drop the new frame
                    self.stats["frames_dropped"] += 1
                    self.stats["buffer_overruns"] += 1
                    logger.debug("Buffer full, dropping new frame")
                    return False

            # Add to buffer with timestamp and ID
            timestamp = time.time()
            frame_id = frame_id or timestamp

            # Priority frames go to the front of the queue
            if priority:
                self.frames.insert(0, (frame_data, frame_id, timestamp))
                logger.debug(
                    f"Added priority frame (id: {frame_id}) to buffer (now {len(self.frames)}/{self.buffer_size})"
                )
            else:
                self.frames.append((frame_data, frame_id, timestamp))
                logger.debug(
                    f"Added frame (id: {frame_id}) to buffer (now {len(self.frames)}/{self.buffer_size})"
                )

            # Update buffer fullness
            self.stats["buffer_fullness"] = len(self.frames) / self.buffer_size

            # Auto-start playback if this is the first frame
            if len(self.frames) == 1 and not self.playing:
                self.start()

            return True

    def add_frames_from_batch(self, frames, batch_sequence, is_priority=False):
        """Add multiple frames from a batch to the buffer"""
        with self.buffer_lock:
            # If this is a priority batch (e.g., pattern change),
            # mark for faster playback of existing frames
            if is_priority and self.frames:
                # Keep track of how many frames we've played from previous pattern
                previous_pattern_frames = len(self.frames)

                if previous_pattern_frames > 0:
                    logger.info(
                        f"Transitioning from previous pattern with {previous_pattern_frames} frames remaining"
                    )
                    # Adjust play speed for faster transition
                    self.transition_speed_multiplier = 3.0  # Play 3x faster

            # Track batch sequence
            self.last_batch_sequence = batch_sequence

            # Add all frames to buffer
            frames_added = 0
            for frame_data in frames:
                if self.add_frame(
                    frame_data,
                    frame_id=f"{batch_sequence}:{frames_added}",
                    priority=is_priority,
                ):
                    frames_added += 1

            logger.info(
                f"Added {frames_added}/{len(frames)} frames from batch #{batch_sequence} to buffer"
            )
            return frames_added

    def clear(self):
        """Clear the buffer"""
        with self.buffer_lock:
            dropped = len(self.frames)
            self.frames = []
            self.stats["frames_dropped"] += dropped
            self.stats["buffer_fullness"] = 0
            logger.info(f"Cleared frame buffer, dropped {dropped} frames")

    def get_status(self):
        """Get current buffer status"""
        with self.buffer_lock:
            return {
                "buffer_size": self.buffer_size,
                "frames_buffered": len(self.frames),
                "buffer_fullness": self.stats["buffer_fullness"] * 100,  # As percentage
                "fps": self.stats["fps"],
                "target_fps": self.stats["target_fps"],
                "frames_received": self.stats["frames_received"],
                "frames_displayed": self.stats["frames_displayed"],
                "frames_dropped": self.stats["frames_dropped"],
                "buffer_underruns": self.stats["buffer_underruns"],
                "buffer_overruns": self.stats["buffer_overruns"],
                "last_displayed_frame_id": self.last_displayed_frame_id,
                "last_batch_sequence": self.last_batch_sequence,
            }

    def get_space_available(self):
        """Get the number of frames that can be added to the buffer"""
        with self.buffer_lock:
            return max(0, self.buffer_size - len(self.frames))


class BatchRequestManager:
    """
    Manages batch requests to the server in a coordinated way,
    preventing request flooding and ensuring batch acknowledgment.
    """

    def __init__(self, controller):
        self.controller = controller
        self.last_request_time = 0
        self.min_request_interval = 0.2  # Minimum seconds between requests
        self.last_sequence = 0
        self.pending_request = False
        self.request_queue = queue.Queue()
        self.request_thread = None
        self.running = False
        self.request_lock = threading.Lock()

    def start(self):
        """Start the batch request manager"""
        if self.running:
            return

        self.running = True
        self.request_thread = threading.Thread(target=self._request_loop)
        self.request_thread.daemon = True
        self.request_thread.start()
        logger.info("Batch request manager started")

    def stop(self):
        """Stop the batch request manager"""
        self.running = False
        logger.info("Batch request manager stopped")

    def _request_loop(self):
        """Process batch requests in a controlled way"""
        while self.running:
            try:
                # Get the next request from the queue (blocking)
                # Will wait for a request to be added if queue is empty
                urgent, space_override = self.request_queue.get(timeout=1.0)

                # Check if we can make the request now
                now = time.time()
                time_since_last = now - self.last_request_time

                # Enforce minimum interval between requests
                if time_since_last < self.min_request_interval and not urgent:
                    # Too soon, delay the request
                    delay = self.min_request_interval - time_since_last
                    logger.debug(f"Delaying batch request by {delay:.2f}s")
                    time.sleep(delay)

                # Make the request
                with self.request_lock:
                    self.pending_request = True
                    success = self._send_request(urgent, space_override)

                    if success:
                        self.last_request_time = time.time()
                    else:
                        # Request failed, wait before retrying
                        time.sleep(1.0)

                    self.pending_request = False

                # Mark the request as done
                self.request_queue.task_done()

                # Add a short delay between requests
                time.sleep(0.1)

            except queue.Empty:
                # No requests in queue, just continue
                pass
            except Exception as e:
                logger.error(f"Error in batch request thread: {e}")
                time.sleep(1.0)  # Wait a bit before continuing

    def _send_request(self, urgent=False, space_override=None):
        """Send a batch request to the server"""
        try:
            # Get current buffer status
            frame_buffer = self.controller.frame_buffer
            buffer_status = frame_buffer.get_status()

            # Calculate space available
            if space_override is not None:
                space_available = space_override
            else:
                space_available = frame_buffer.get_space_available()

            # Don't request if buffer is too full
            buffer_fullness = buffer_status["buffer_fullness"]
            if buffer_fullness > 75.0 and not urgent:
                logger.debug(
                    f"Buffer at {buffer_fullness:.1f}% - deferring batch request"
                )
                return False

            # Create request message
            request = {
                "topic": "controller:lobby",
                "event": "request_batch",
                "payload": {
                    "controller_id": self.controller.controller_id,
                    "last_sequence": self.last_sequence,
                    "space_available": space_available,
                    "urgent": urgent,
                    "buffer_fullness": buffer_fullness,
                    "buffer_capacity": frame_buffer.buffer_size,
                    "timestamp": int(time.time() * 1000),
                },
                "ref": None,
            }

            # Send the request
            success = self.controller.connection.send(request)
            if success:
                logger.info(
                    f"Requested batch after sequence #{self.last_sequence}, "
                    f"space: {space_available}, urgent: {urgent}, "
                    f"buffer: {buffer_fullness:.1f}%"
                )
            return success
        except Exception as e:
            logger.error(f"Error sending batch request: {e}")
            return False

    def request_batch(self, urgent=False, space_override=None):
        """Queue a batch request"""
        # Check if there's already a pending request
        if self.pending_request and not urgent:
            logger.debug("Batch request already pending, ignoring duplicate request")
            return False

        try:
            # Add the request to the queue
            self.request_queue.put((urgent, space_override))
            logger.debug(f"Queued batch request (urgent: {urgent})")
            return True
        except Exception as e:
            logger.error(f"Error queuing batch request: {e}")
            return False

    def acknowledge_batch(self, sequence):
        """Acknowledge receipt of a batch"""
        if sequence > self.last_sequence:
            self.last_sequence = sequence
            logger.debug(f"Updated last sequence to {sequence}")
            return True
        return False


class LegridController:
    """
    Main controller class for LEDGrid that coordinates all the components:
    - Connection management
    - Frame buffering
    - Batch requesting
    - LED control
    - Pattern parameter tracking
    """

    def __init__(self, args):
        self.args = args
        self.width = args.width
        self.height = args.height
        self.led_count = args.led_count
        self.brightness = args.led_brightness
        self.server_url = args.server_url
        self.controller_id = args.controller_id or str(uuid.uuid4())

        # Store controller ID to a file for persistence
        if not args.controller_id:
            try:
                id_file = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)), "controller_id.txt"
                )
                if os.path.exists(id_file):
                    with open(id_file, "r") as f:
                        saved_id = f.read().strip()
                        if saved_id:
                            self.controller_id = saved_id
                            logger.info(
                                f"Loaded controller ID from file: {self.controller_id}"
                            )

                # Save the ID to file (whether new or loaded)
                with open(id_file, "w") as f:
                    f.write(self.controller_id)
            except Exception as e:
                logger.warning(f"Error managing controller ID file: {e}")

        # Layout settings
        self.layout = args.layout
        self.flip_x = args.flip_x
        self.flip_y = args.flip_y
        self.transpose = args.transpose

        # Pattern tracking
        self.current_pattern_id = None
        self.pattern_parameters = None

        # LED state tracking
        self.current_led_state = [(0, 0, 0) for _ in range(self.led_count)]
        self.led_state_initialized = False

        # Create components
        self.connection = ConnectionManager(self.server_url, self)
        self.frame_buffer = FrameBuffer(args.buffer_size, args.buffer_rate)
        self.batch_manager = BatchRequestManager(self)

        # Initialize LED strip
        self._initialize_leds()

        # Statistics
        self.stats = {
            "start_time": time.time(),
            "frames_received": 0,
            "frames_displayed": 0,
            "pattern_changes": 0,
            "connection_drops": 0,
            "last_stats_time": time.time(),
        }

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Log configuration
        logger.info(f"Controller initialized with ID: {self.controller_id}")
        logger.info(
            f"Grid configuration: {self.width}x{self.height}, layout={self.layout}"
        )
        logger.info(
            f"Grid orientation: flip_x={self.flip_x}, flip_y={self.flip_y}, transpose={self.transpose}"
        )
        logger.info(
            f"Buffer size: {args.buffer_size}, playback rate: {args.buffer_rate}"
        )

    def _initialize_leds(self):
        """Initialize the LED strip"""
        if HARDWARE_AVAILABLE:
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
            # Use mock implementation
            self.strip = MockWs(self.led_count, self.brightness)

        # Clear LEDs on startup
        self.clear_leds()

    def clear_leds(self):
        """Clear all LEDs (set to black/off)"""
        for i in range(self.led_count):
            if HARDWARE_AVAILABLE:
                self.strip[i] = (0, 0, 0)
            else:
                self.strip.setPixelColor(i, 0)

            # Update state tracking
            self.current_led_state[i] = (0, 0, 0)

        # Show changes
        try:
            if HARDWARE_AVAILABLE:
                self.strip.show()
            else:
                self.strip.show()
        except Exception as e:
            logger.error(f"Error showing LED strip: {e}")

        # We've now initialized the LED state
        self.led_state_initialized = True
        logger.info("Cleared all LEDs")

    def map_pixel_index(self, x, y):
        """
        Map x,y grid coordinates to the physical LED index.
        Accounts for serpentine layout and orientation options.
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

    def run(self):
        """Start the controller and connect to the server"""
        # Initialize and start components
        # Override the frame buffer's display callback
        self.frame_buffer._display_frame = self.display_frame

        # Start the frame buffer
        self.frame_buffer.start()

        # Start the batch manager
        self.batch_manager.start()

        # Connect to the server
        logger.info("Starting controller and connecting to server...")
        self.connection.connect()

        # Main loop - just wait for signals
        try:
            while running:
                time.sleep(1)

                # Periodically send stats if connected
                current_time = time.time()
                if current_time - self.stats["last_stats_time"] > 30:
                    if self.connection.is_connected():
                        self.send_stats()
                    self.stats["last_stats_time"] = current_time

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")

        finally:
            # Clean shutdown
            self.shutdown()

    def shutdown(self):
        """Shutdown the controller gracefully"""
        logger.info("Shutting down controller...")

        # Stop components
        self.batch_manager.stop()
        self.frame_buffer.stop()

        # Close connection
        self.connection.close()

        # Clear LEDs
        self.clear_leds()

        logger.info("Controller shutdown complete")

    def signal_handler(self, sig, frame):
        """Handle termination signals"""
        global running
        logger.info("Received termination signal, shutting down...")
        running = False

    def handle_connection_open(self):
        """Handle WebSocket connection open"""
        # Join the Phoenix channel
        join_message = {
            "topic": "controller:lobby",
            "event": "phx_join",
            "payload": {"controller_id": self.controller_id},
            "ref": "1",
        }

        # Send join message
        self.connection.send(join_message)

        # Send controller info
        self.send_controller_info()

        # Request first batch after a short delay
        time.sleep(0.5)
        self.batch_manager.request_batch(urgent=True)

    def handle_connection_close(self):
        """Handle WebSocket connection close"""
        self.stats["connection_drops"] += 1

    def handle_message(self, message):
        """Handle incoming WebSocket messages"""
        try:
            # Check if the message is binary or text
            if isinstance(message, bytes):
                self.handle_binary_message(message)
            else:
                # JSON message
                self.handle_json_message(message)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def handle_binary_message(self, message):
        """Handle binary WebSocket messages"""
        # Check for WebSocket control frames
        if len(message) >= 1:
            # Check if this is a batch frame message (starts with byte 0xB)
            if message[0] == 0xB and len(message) >= 9:
                logger.info(f"Received batch frame message ({len(message)} bytes)")
                self.process_batch_frames(message)
                return

            # Check if this might be a frame with protocol version 1
            if (message[0] == 1 or message[0] == 123) and len(message) >= 10:
                logger.info(f"Received binary frame ({len(message)} bytes)")
                # Add directly to buffer
                self.frame_buffer.add_frame(message, priority=True)
                return

        # Unknown binary message
        logger.warning(f"Received unknown binary message ({len(message)} bytes)")

    def handle_json_message(self, message):
        """Handle JSON WebSocket messages"""
        data = json.loads(message)

        # Extract event and payload
        event = data.get("event")
        payload = data.get("payload", {})

        # Handle different event types
        if event == "phx_reply" and payload.get("status") == "ok":
            # Join confirmation
            logger.info("Successfully joined channel")

        elif event == "frame":
            # Handle frame message - contains binary data in payload["binary"]
            if "binary" in payload:
                # Check if this is a new pattern or parameters changed
                is_priority = False
                clear_needed = False

                # Check for pattern ID changes
                if "pattern_id" in payload:
                    if self.current_pattern_id != payload["pattern_id"]:
                        # New pattern
                        self.current_pattern_id = payload["pattern_id"]
                        self.stats["pattern_changes"] += 1
                        clear_needed = True
                        is_priority = True
                        logger.info(
                            f"New pattern detected (ID: {self.current_pattern_id})"
                        )

                        # Clear buffer on pattern change
                        self.frame_buffer.clear()

                # Check for parameter changes
                if "parameters" in payload:
                    if self.pattern_parameters != payload["parameters"]:
                        # Log changes
                        if self.pattern_parameters:
                            old_params = set(self.pattern_parameters.items())
                            new_params = set(payload["parameters"].items())
                            changes = new_params - old_params
                            if changes:
                                logger.info(f"Pattern parameters changed: {changes}")
                                is_priority = True

                        # Update parameters
                        self.pattern_parameters = payload["parameters"].copy()

                # Clear LEDs if needed
                if clear_needed:
                    self.clear_leds()

                # The binary data is base64 encoded in JSON
                try:
                    binary_data = base64.b64decode(payload["binary"])

                    # Add to frame buffer
                    self.frame_buffer.add_frame(binary_data, priority=is_priority)

                except Exception as e:
                    logger.error(f"Error processing binary frame data: {e}")

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

        elif event == "initiate_polling":
            # Server is asking us to start polling for frames
            logger.info("Received polling initiation request from server")
            self.batch_manager.request_batch(urgent=True)

        elif event == "request_stats":
            # Send stats back to the server
            self.send_stats()

        elif event == "clear_display":
            # Clear the display and buffer
            logger.info("Received clear display command")
            self.clear_leds()
            self.frame_buffer.clear()

        else:
            # Unknown event
            logger.debug(f"Received unknown event: {event}")

    def process_batch_frames(self, message):
        """Process a batch of frames sent in a single message"""
        try:
            # Parse batch header
            if len(message) < 10:
                logger.warning("Batch message too short to contain header")
                return

            # Byte 0 should be 0xB for batch messages
            if message[0] != 0xB:
                logger.warning(
                    f"Invalid batch identifier: 0x{message[0]:02x}, expected 0x0B"
                )
                return

            # Extract batch metadata
            frame_count = struct.unpack("<I", message[1:5])[0]
            is_priority = message[5] == 1
            batch_sequence = struct.unpack("<I", message[6:10])[0]

            # Extract timestamp if available
            if len(message) >= 18:
                batch_timestamp = struct.unpack("<Q", message[10:18])[0]
                logger.info(
                    f"Received batch sequence #{batch_sequence} with timestamp {batch_timestamp}, contains {frame_count} frames"
                )
                offset = 18  # Start of frame data
            else:
                logger.info(
                    f"Received batch sequence #{batch_sequence} (no timestamp), contains {frame_count} frames"
                )
                offset = 10  # Start of frame data

            # Acknowledge the batch
            self.batch_manager.acknowledge_batch(batch_sequence)

            # Extract frames
            frames = []
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

                # Extract frame data and add to frames list
                frame_data = message[offset : offset + frame_length]
                frames.append(frame_data)
                offset += frame_length
                frames_processed += 1

            # Add frames to buffer
            if frames:
                self.frame_buffer.add_frames_from_batch(
                    frames, batch_sequence, is_priority
                )

                # After successful processing, send acknowledgment
                self.send_batch_ack(batch_sequence, len(frames))

                # Request next batch based on buffer fullness
                buffer_status = self.frame_buffer.get_status()
                buffer_fullness = buffer_status["buffer_fullness"]

                # Schedule next batch request soon if buffer is getting low
                if buffer_fullness < 50:
                    # The emptier the buffer, the sooner we request
                    delay = (
                        0.2 + (buffer_fullness / 100.0) * 0.5
                    )  # 200-700ms based on fullness
                    threading.Timer(
                        delay, lambda: self.batch_manager.request_batch()
                    ).start()

        except Exception as e:
            logger.error(f"Error processing batch frames: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def display_frame(self, frame_data):
        """Display frame data on LEDs - used as callback from frame buffer"""
        if len(frame_data) < 10:
            logger.warning(f"Frame data too short: {len(frame_data)} bytes")
            return

        try:
            # Parse frame header
            version = frame_data[0]
            msg_type = frame_data[1]
            frame_id = struct.unpack("<I", frame_data[2:6])[0]
            width = struct.unpack("<H", frame_data[6:8])[0]
            height = struct.unpack("<H", frame_data[8:10])[0]

            # Basic sanity checks
            if width == 0 or height == 0 or width > 1000 or height > 1000:
                logger.warning(f"Invalid frame dimensions: {width}x{height}")
                return

            # Handle different message types
            if msg_type == 1:  # Full frame
                self.update_leds_from_pixels(frame_data[10:], width, height)
            elif msg_type == 2:  # Delta frame
                self.apply_delta_frame(frame_data[10:], width, height)
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error displaying frame: {e}")

    def update_leds_from_pixels(self, pixel_data, width, height):
        """Update all LEDs from pixel data (full frame)"""
        if len(pixel_data) < width * height * 3:
            logger.warning(
                f"Not enough pixel data: {len(pixel_data)} bytes, expected {width * height * 3}"
            )
            return

        # Update LEDs using the mapping function
        for y in range(min(height, self.height)):
            for x in range(min(width, self.width)):
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
                        # Save old value for delta tracking
                        new_value = (r, g, b)

                        # Update state tracking
                        self.current_led_state[dest_idx] = new_value

                        try:
                            # Update LED
                            if HARDWARE_AVAILABLE:
                                self.strip[dest_idx] = (r, g, b)
                            else:
                                color = (r << 16) | (g << 8) | b
                                self.strip.setPixelColor(dest_idx, color)
                        except IndexError:
                            logger.warning(f"LED index {dest_idx} out of bounds")

        # Show the strip
        try:
            if HARDWARE_AVAILABLE:
                self.strip.show()
            else:
                self.strip.show()
        except Exception as e:
            logger.error(f"Error showing LED strip: {e}")

        # We've now initialized the LED state
        self.led_state_initialized = True

    def apply_delta_frame(self, delta_data, width, height):
        """Apply a delta frame (only changed pixels)"""
        if len(delta_data) < 2:
            logger.warning("Delta frame too small")
            return

        # If LED state isn't initialized yet, use full frame update
        if not self.led_state_initialized:
            logger.warning("LED state not initialized, treating delta as full frame")
            self.clear_leds()
            self.update_leds_from_pixels(delta_data, width, height)
            return

        # First 2 bytes are the number of deltas - using little-endian
        num_deltas = struct.unpack("<H", delta_data[0:2])[0]
        delta_data = delta_data[2:]

        if len(delta_data) < num_deltas * 5:
            logger.warning(
                f"Not enough delta data: {len(delta_data)} bytes, expected {num_deltas * 5}"
            )
            return

        # Process each delta
        for i in range(num_deltas):
            index = i * 5
            if index + 4 < len(delta_data):
                # 2 bytes for pixel index, 3 bytes for RGB
                pixel_index = struct.unpack("<H", delta_data[index : index + 2])[0]
                r = delta_data[index + 2]
                g = delta_data[index + 3]
                b = delta_data[index + 4]

                # Convert linear index to x,y for mapping
                x = pixel_index % width
                y = pixel_index // width

                # Map to physical LED position
                dest_idx = self.map_pixel_index(x, y)

                if 0 <= dest_idx < self.led_count:
                    # Update state tracking
                    self.current_led_state[dest_idx] = (r, g, b)

                    # Update LED
                    try:
                        if HARDWARE_AVAILABLE:
                            self.strip[dest_idx] = (r, g, b)
                        else:
                            color = (r << 16) | (g << 8) | b
                            self.strip.setPixelColor(dest_idx, color)
                    except IndexError:
                        logger.warning(f"LED index {dest_idx} out of bounds")

        # Show the strip
        try:
            if HARDWARE_AVAILABLE:
                self.strip.show()
            else:
                self.strip.show()
        except Exception as e:
            logger.error(f"Error showing LED strip: {e}")

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
                "version": "2.0.0",  # Updated version
                "hardware": "Raspberry Pi" if HARDWARE_AVAILABLE else "Mock",
                "layout": self.layout,
                "orientation": {
                    "flip_x": self.flip_x,
                    "flip_y": self.flip_y,
                    "transpose": self.transpose,
                },
                "buffer": {
                    "enabled": True,
                    "size": self.frame_buffer.buffer_size,
                    "playback_rate": self.frame_buffer.playback_rate,
                },
            },
            "ref": None,
        }

        success = self.connection.send(info)
        if success:
            logger.info("Sent controller info")

    def send_stats(self):
        """Send controller statistics"""
        # Get buffer status
        buffer_status = self.frame_buffer.get_status()

        # Create stats message
        stats_data = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "frames_received": buffer_status["frames_received"],
                "frames_displayed": buffer_status["frames_displayed"],
                "frames_dropped": buffer_status["frames_dropped"],
                "connection_drops": self.stats["connection_drops"],
                "pattern_changes": self.stats["pattern_changes"],
                "fps": round(buffer_status["fps"], 1),
                "target_fps": buffer_status["target_fps"],
                "buffer_fullness": round(buffer_status["buffer_fullness"], 1),
                "timestamp": datetime.now().isoformat(),
                "uptime": int(time.time() - self.stats["start_time"]),
            },
            "ref": None,
        }

        success = self.connection.send(stats_data)
        if success:
            logger.debug("Sent controller stats")

    def send_batch_ack(self, sequence, frame_count):
        """Send acknowledgment for a batch"""
        # Get buffer status
        buffer_status = self.frame_buffer.get_status()

        # Create acknowledgment message
        ack = {
            "topic": "controller:lobby",
            "event": "batch_ack",
            "payload": {
                "sequence": sequence,
                "buffer_fullness": buffer_status["buffer_fullness"],
                "buffer_capacity": buffer_status["buffer_size"],
                "frames_received": frame_count,
                "timestamp": int(time.time() * 1000),
            },
            "ref": None,
        }

        success = self.connection.send(ack)
        if success:
            logger.debug(f"Sent acknowledgment for batch {sequence}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Improved LEDGrid Controller for Raspberry Pi"
    )

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
    parser.add_argument(
        "--controller-id",
        type=str,
        default=None,
        help="Controller ID (default: auto-generated UUID)",
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

    # Buffer options
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

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Set log level
    logger.setLevel(getattr(logging, args.log_level))

    # Print introduction
    logger.info("Starting Improved LEDGrid Controller")
    logger.info(f"Server URL: {args.server_url}")
    logger.info(f"Grid: {args.width}x{args.height}, {args.led_count} LEDs")

    # Initialize and run the controller
    controller = LegridController(args)
    controller.run()
