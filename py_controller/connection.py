import json
import base64
import time
import uuid
import logging
import threading
import websocket
import struct

logger = logging.getLogger("legrid-controller")


class ConnectionManager:
    """Manages WebSocket connection to the Phoenix server"""

    def __init__(self, server_url, on_frame_callback, config):
        """Initialize WebSocket connection manager"""
        self.server_url = server_url
        self.on_frame_callback = on_frame_callback
        self.config = config
        self.ws = None
        self.connected = False
        self.channel_joined = False
        self.reconnect_timer = None
        self.heartbeat_timer = None
        self.reconnect_attempts = 0

        # Handle both object and dict-style configs
        if isinstance(config, dict):
            self.enable_stats = config.get("enable_stats", True)
            self.controller_id = config.get("controller_id", str(uuid.uuid4()))
        else:
            self.enable_stats = getattr(config, "enable_stats", True)
            self.controller_id = getattr(config, "controller_id", str(uuid.uuid4()))

        self.stats_timer = None

        # Added for _next_ref method
        self.ref_counter = 0

        # Stats and monitoring
        self.stats = {
            "frames_received": 0,
            "connection_drops": 0,
            "connection_start_time": 0,
            "connection_uptime": 0,
            "last_frame_time": 0,
            "fps": 0,
        }

        self.frames_received = 0
        self.frames_per_second = 0
        self.last_fps_time = time.time()
        self.last_parameters = None

        # Last received data for potential reconnection recovery
        self.last_pattern_id = None

    def connect(self):
        """Connect to the Phoenix WebSocket server"""
        logger.info(f"Connecting to server: {self.server_url}")

        # Create WebSocket connection
        try:
            self.ws = websocket.WebSocketApp(
                self.server_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_ping=self._on_ping,
                on_pong=self._on_pong,
            )

            # Start WebSocket in a background thread
            websocket_thread = threading.Thread(target=self._run_websocket)
            websocket_thread.daemon = True
            websocket_thread.start()

            # Record connection attempt time
            self.stats["connection_start_time"] = time.time()

            return True
        except Exception as e:
            logger.error(f"Failed to create WebSocket connection: {e}")
            self._schedule_reconnect()
            return False

    def disconnect(self):
        """Disconnect from the server"""
        if self.ws:
            # Leave channel before closing
            if self.channel_joined:
                self._send_leave_message()
                self.channel_joined = False

            # Close WebSocket
            self.ws.close()

        # Cancel timers
        self._cancel_timers()

        self.connected = False
        logger.info("Disconnected from server")

    def send_stats(self):
        """Send controller statistics to the server"""
        if not self.connected or not self.channel_joined:
            return

        # Calculate uptime
        uptime = time.time() - self.stats["connection_start_time"]

        # Create stats payload
        stats_payload = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "frames_received": self.stats["frames_received"],
                "frames_displayed": self.stats[
                    "frames_received"
                ],  # Assuming all received frames are displayed
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "connection_uptime": uptime,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(stats_payload))
            logger.debug("Sent controller stats")
        except Exception as e:
            logger.error(f"Error sending stats: {e}")

    def send_detailed_stats(self):
        """Send detailed controller stats"""
        if not self.connected or not self.channel_joined:
            return

        # Create detailed stats payload
        detailed_stats = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "type": "detailed_stats",
                "frames_received": self.stats["frames_received"],
                "frames_displayed": self.stats["frames_received"],
                "connection_drops": self.stats["connection_drops"],
                "fps": round(self.stats["fps"], 1),
                "connection_uptime": self.stats["connection_uptime"],
                "hardware_info": {
                    "type": "Raspberry Pi"
                    if hasattr(self, "is_hardware_available")
                    and self.is_hardware_available
                    else "Mock",
                    "width": getattr(self, "width", 25),
                    "height": getattr(self, "height", 24),
                    "layout": getattr(self, "layout", "serpentine"),
                    "orientation": {
                        "flip_x": getattr(self, "flip_x", False),
                        "flip_y": getattr(self, "flip_y", False),
                        "transpose": getattr(self, "transpose", False),
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

    def send_controller_info(self):
        """Send controller info to the server"""
        if not self.connected or not self.channel_joined:
            logger.warning("Cannot send controller info: not connected or not joined")
            return

        # Get current parameters to check if we need to resend
        current_params = self._get_controller_params()
        if self.last_parameters == current_params:
            logger.debug("Parameters unchanged, skipping controller_info")
            return

        # Create controller info message
        info_message = {
            "topic": "controller:lobby",
            "event": "controller_info",
            "payload": {
                "type": "controller_info",
                "id": self.controller_id,
                "width": getattr(self, "width", 25),
                "height": getattr(self, "height", 24),
                "pattern": getattr(self, "pattern", "none"),
                "parameters": current_params,
            },
            "ref": str(self._next_ref()),
        }

        # Store parameters for comparison
        self.last_parameters = current_params

        try:
            # Send the info message
            logger.debug("Sending controller info")
            self.ws.send(json.dumps(info_message))
        except Exception as e:
            logger.error(f"Error sending controller info: {e}")

    def _run_websocket(self):
        """Run the WebSocket connection in a thread"""
        try:
            # Print connection details for debugging
            print(f"Starting WebSocket connection to {self.server_url}")
            # Set longer timeouts for better debugging
            self.ws.run_forever(ping_interval=20, ping_timeout=10, dispatcher=None)
            print("WebSocket run_forever ended")
        except Exception as e:
            logger.error(f"WebSocket thread error: {e}")
            import traceback

            traceback.print_exc()
            self._schedule_reconnect()

    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")
        self.connected = True
        self.reconnect_attempts = 0

        # Join the Phoenix channel
        self._join_channel()

        # Set up heartbeat
        self._setup_heartbeat()

        # Set up stats reporting
        self._setup_stats_reporting()

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Check if message is binary
            if isinstance(message, bytes):
                # Check the message type by looking at the first byte
                if len(message) > 0 and message[0] == 0xB:
                    # This is a batch message (0xB is the batch identifier)
                    logger.debug(
                        f"Received binary batch message ({len(message)} bytes)"
                    )
                    self._process_batch_data(message)
                else:
                    # This is a single frame, process directly
                    logger.debug(
                        f"Received binary frame message ({len(message)} bytes)"
                    )
                    self.on_frame_callback(message)
                    self._update_frame_stats()
                return

            # Handle text (JSON) messages
            data = json.loads(message)

            # Extract Phoenix message components
            event = data.get("event")
            topic = data.get("topic", "")
            ref = data.get("ref")
            payload = data.get("payload", {})

            logger.debug(f"Received event: {event}, topic: {topic}")

            # Check for successful channel join
            if event == "phx_reply" and topic == "controller:lobby":
                if payload.get("status") == "ok":
                    # This is a successful reply to one of our requests
                    logger.debug(f"Received successful reply with ref: {ref}")

                    # Check if this is a response to our join request
                    if not self.channel_joined:
                        logger.info("Successfully joined controller channel!")
                        self.channel_joined = True

                        # Send controller info
                        self.send_controller_info()

                        # Request initial batch of frames
                        logger.info("Requesting initial batch of frames")
                        if self._request_batch(0):
                            logger.info("Initial batch request sent")
                        else:
                            logger.error("Failed to request initial batch")

                    # Also handle batch request confirmations
                    response = payload.get("response", {})
                    if response.get("status") == "request_received":
                        logger.debug(f"Server confirmed batch request: {response}")

            # Handle other Phoenix message types
            elif event == "frame":
                # Handle frame message
                if "binary" in payload:
                    # The binary data is base64 encoded in JSON
                    binary_data = base64.b64decode(payload["binary"])

                    # Track pattern/parameters
                    if "pattern_id" in payload:
                        self.last_pattern_id = payload["pattern_id"]
                    if "parameters" in payload:
                        self.last_parameters = payload["parameters"]

                    # Process frame
                    self.on_frame_callback(binary_data)
                    self._update_frame_stats()

            elif event == "request_stats":
                # Send stats in response to request
                self.send_stats()

            elif event == "request_detailed_stats":
                # Send detailed stats
                self.send_detailed_stats()

            elif event == "simulation_config":
                # Apply simulation config
                logger.info(f"Received simulation config: {payload}")
                # This would be handled by the main controller

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

            elif event == "display_batch":
                # Process batch of frames
                logger.debug(
                    f"Received display_batch event with {len(str(payload))} bytes of data"
                )
                try:
                    seq = payload.get("sequence", 0)
                    pattern = payload.get("pattern", "unknown")
                    priority = payload.get("priority", 0)

                    # Check if we have binary data in the payload
                    if "binary" in payload:
                        # The binary data is base64 encoded in JSON
                        binary_data = base64.b64decode(payload["binary"])
                        logger.info(
                            f"Processing batch: {len(binary_data)} bytes, seq={seq}, pattern={pattern}"
                        )
                        self._process_batch_data(binary_data)
                    else:
                        # Log message format issue
                        logger.warning(
                            "No binary field found in payload, checking message format"
                        )
                        logger.warning(
                            "JSON frame format not supported, server should use binary"
                        )

                        # Try to be graceful - request next batch with incremented sequence
                        self._request_batch(seq + 1)
                except Exception as e:
                    logger.error(f"Error processing display_batch event: {e}")
                    # Just try to keep going with sequential batch
                    self._request_batch(seq + 1 if "seq" in locals() else 0)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if isinstance(message, bytes):
                logger.debug(f"Binary message first bytes: {message[:10].hex()}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        # Error handling will continue in on_close

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")

        # Update connection statistics
        if self.stats["connection_start_time"] > 0:
            self.stats["connection_uptime"] += (
                time.time() - self.stats["connection_start_time"]
            )

        self.stats["connection_drops"] += 1
        self.connected = False
        self.channel_joined = False

        # Cancel timers
        self._cancel_timers()

        # Schedule reconnection
        self._schedule_reconnect()

    def _on_ping(self, ws, message):
        """Handle ping from server"""
        logger.debug("Received ping from server")

    def _on_pong(self, ws, message):
        """Handle pong from server"""
        logger.debug("Received pong from server")

    def _join_channel(self):
        """Join the controller channel"""
        if not self.ws or not self.connected:
            logger.error("Cannot join channel: WebSocket not connected")
            return

        # Create join message
        join_message = {
            "topic": "controller:lobby",
            "event": "phx_join",
            "payload": {"controller_id": self.controller_id},
            "ref": str(self._next_ref()),
        }

        # Send join request
        logger.info("Sent join message")
        self.ws.send(json.dumps(join_message))

        # Note that we'll set channel_joined=True when we receive the join confirmation

    def _send_leave_message(self):
        """Send Phoenix channel leave message"""
        leave_message = {
            "topic": "controller:lobby",
            "event": "phx_leave",
            "payload": {},
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(leave_message))
            logger.info("Sent leave message")
        except Exception as e:
            logger.error(f"Error sending leave message: {e}")

    def _setup_heartbeat(self):
        """Set up Phoenix heartbeat"""

        def send_heartbeat():
            if self.connected:
                try:
                    heartbeat_message = {
                        "topic": "phoenix",
                        "event": "heartbeat",
                        "payload": {},
                        "ref": str(int(time.time())),
                    }
                    self.ws.send(json.dumps(heartbeat_message))
                    logger.debug("Sent Phoenix heartbeat")
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")

                # Schedule next heartbeat
                self.heartbeat_timer = threading.Timer(30.0, send_heartbeat)
                self.heartbeat_timer.daemon = True
                self.heartbeat_timer.start()

        # Start heartbeat timer
        self.heartbeat_timer = threading.Timer(30.0, send_heartbeat)
        self.heartbeat_timer.daemon = True
        self.heartbeat_timer.start()

    def _setup_stats_reporting(self):
        """Set up periodic stats reporting"""

        def send_stats_periodically():
            if self.connected:
                try:
                    self.send_stats()
                except Exception as e:
                    logger.error(f"Error in stats reporting: {e}")

                # Schedule next report
                self.stats_timer = threading.Timer(5.0, send_stats_periodically)
                self.stats_timer.daemon = True
                self.stats_timer.start()

        # Start stats timer
        self.stats_timer = threading.Timer(5.0, send_stats_periodically)
        self.stats_timer.daemon = True
        self.stats_timer.start()

    def _update_frame_stats(self):
        """Update frame-related statistics"""
        current_time = time.time()
        self.stats["frames_received"] += 1
        self.frames_received += 1

        # Calculate FPS
        if self.stats["last_frame_time"] > 0:
            time_diff = current_time - self.stats["last_frame_time"]
            if time_diff > 0:
                # Apply smoothing to FPS calculation
                new_fps = 1.0 / time_diff
                self.stats["fps"] = 0.8 * self.stats["fps"] + 0.2 * new_fps
                self.frames_per_second = self.stats["fps"]

        self.stats["last_frame_time"] = current_time

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt"""
        # Cancel any existing reconnect timer
        if self.reconnect_timer:
            self.reconnect_timer.cancel()

        # Calculate backoff delay
        self.reconnect_attempts += 1
        delay = min(1.0 * (2 ** min(self.reconnect_attempts, 6)), 60.0)  # Max 60s delay

        logger.info(
            f"Scheduling reconnection in {delay:.1f} seconds (attempt {self.reconnect_attempts})"
        )

        # Schedule reconnection
        self.reconnect_timer = threading.Timer(delay, self.connect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()

    def _request_batch(self, sequence=0):
        """Request a new batch of frames from the server"""
        # Check connection state
        if not self.ws:
            logger.error("WebSocket connection is None, cannot request batch")
            return False

        if not self.connected:
            logger.debug("Cannot request batch: not connected")
            return False

        if not self.channel_joined:
            logger.debug("Cannot request batch: channel not joined")
            return False

        try:
            # Default request size
            space = 60  # Request up to 60 frames at a time

            # Create batch request message
            request_message = {
                "topic": "controller:lobby",
                "event": "batch_request",
                "payload": {
                    "sequence": sequence,
                    "space": space,
                    "urgent": sequence == 0,  # First batch is urgent
                },
                "ref": str(self._next_ref()),
            }

            # Send request
            message_json = json.dumps(request_message)
            self.ws.send(message_json)
            logger.debug(f"Sent batch request: seq={sequence}, space={space}")
            return True
        except Exception as e:
            logger.error(f"Error sending batch request: {e}")
            return False

    def _cancel_timers(self):
        """Cancel all timers"""
        if self.reconnect_timer:
            self.reconnect_timer.cancel()
            self.reconnect_timer = None

        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

        # Fix: Initialize stats_timer in __init__ and check if it exists
        if hasattr(self, "stats_timer") and self.stats_timer:
            self.stats_timer.cancel()
            self.stats_timer = None

    def _send_batch_ack(self, sequence, frame_count):
        """Send an acknowledgment to the server after processing a batch"""
        if not self.connected or not self.channel_joined:
            logger.warning("Cannot send batch_ack: not connected or not joined")
            return False

        try:
            # Create batch acknowledgment message
            ack_message = {
                "topic": "controller:lobby",
                "event": "batch_ack",
                "payload": {
                    "sequence": sequence,
                    "frames_processed": frame_count,
                    "timestamp": int(time.time() * 1000),
                },
                "ref": str(self._next_ref()),
            }

            # Send the acknowledgment
            self.ws.send(json.dumps(ack_message))
            logger.debug(
                f"Sent batch_ack for sequence {sequence}, frames: {frame_count}"
            )
            return True
        except Exception as e:
            logger.error(f"Error sending batch acknowledgment: {e}")
            return False

    def _process_batch_data(self, binary_data):
        """Process a batch of frames from binary data"""
        if len(binary_data) < 18:  # Minimum header size
            logger.error(f"Batch too small: {len(binary_data)} bytes")
            return

        # We're not using the stored connection state anymore, as it's unreliable
        # The channel_joined flag might have been updated by incoming messages during processing

        try:
            # Parse batch header
            batch_id = binary_data[0]
            if batch_id != 0xB:  # Verify this is a batch (0xB = 11)
                logger.error(f"Invalid batch identifier: {batch_id:02x}, expected 0x0B")
                return

            # Extract header fields
            frame_count = struct.unpack("<I", binary_data[1:5])[0]
            priority_flag = binary_data[5]
            sequence = struct.unpack("<I", binary_data[6:10])[0]
            timestamp = struct.unpack("<Q", binary_data[10:18])[0]

            logger.info(
                f"Batch header: frames={frame_count}, priority={priority_flag}, seq={sequence}, timestamp={timestamp}"
            )

            # Process each frame in the batch
            offset = 18  # Start after header
            frames_processed = 0

            while offset < len(binary_data) and frames_processed < frame_count:
                # Check if we have enough data for frame length
                if offset + 4 > len(binary_data):
                    logger.warning(
                        f"Incomplete batch: missing frame length at offset {offset}"
                    )
                    break

                # Get frame length
                frame_length = struct.unpack("<I", binary_data[offset : offset + 4])[0]
                offset += 4

                # Check if we have enough data for the frame
                if offset + frame_length > len(binary_data):
                    logger.warning(
                        f"Incomplete batch: truncated frame at offset {offset}, needed {frame_length} bytes"
                    )
                    break

                # Extract this frame's data
                frame_data = binary_data[offset : offset + frame_length]

                # Process this frame
                logger.debug(
                    f"Processing frame {frames_processed + 1}/{frame_count} ({frame_length} bytes)"
                )
                self.on_frame_callback(frame_data)

                # Move to next frame
                offset += frame_length
                frames_processed += 1

                # Update statistics
                self._update_frame_stats()

            logger.info(
                f"Processed {frames_processed}/{frame_count} frames from batch, next batch seq={sequence + 1}"
            )

            # Send batch acknowledgment - check current connection state
            if self.connected and self.channel_joined:
                self._send_batch_ack(sequence, frames_processed)

                # Request next batch
                logger.debug(f"Requesting next batch after seq={sequence}")
                if self._request_batch(sequence + 1):
                    logger.debug(f"Next batch request sent: seq={sequence + 1}")
                else:
                    logger.error(f"Failed to request next batch (seq={sequence + 1})")
            else:
                logger.warning(
                    f"Cannot request next batch: current state is connected={self.connected}, channel_joined={self.channel_joined}"
                )
                # Try one more time with current state
                if self.connected and self.channel_joined:
                    logger.info(
                        "Connection state recovered, attempting to request next batch"
                    )
                    self._request_batch(sequence + 1)

        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            import traceback

            logger.error(traceback.format_exc())
            if len(binary_data) > 30:
                logger.debug(f"First 30 bytes of batch: {binary_data[:30].hex()}")

            # Try to request next batch even if processing failed
            if self.connected and self.channel_joined:
                try:
                    # Extract sequence if possible, or use 0
                    seq = 0
                    if len(binary_data) >= 10:
                        seq = struct.unpack("<I", binary_data[6:10])[0]
                    logger.info(
                        f"Attempting to request next batch after error (seq={seq + 1})"
                    )
                    self._request_batch(seq + 1)
                except Exception as e2:
                    logger.error(f"Failed to request next batch after error: {e2}")

    def _next_ref(self):
        """Generate a new reference ID for Phoenix messages"""
        self.ref_counter += 1
        return self.ref_counter

    def _get_controller_params(self):
        """Get controller parameters for info message"""
        params = {
            "version": "1.0.0",
            "hardware": "Raspberry Pi"
            if (hasattr(self, "is_hardware_available") and self.is_hardware_available)
            else "Mock",
            "layout": getattr(self, "layout", "serpentine"),
            "flip_x": getattr(self, "flip_x", False),
            "flip_y": getattr(self, "flip_y", False),
            "transpose": getattr(self, "transpose", False),
            "led_count": getattr(self, "led_count", 600),
        }
        return params
