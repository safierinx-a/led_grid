import json
import base64
import time
import uuid
import logging
import threading
import websocket

logger = logging.getLogger("legrid-controller")


class ConnectionManager:
    """Manages WebSocket connection to the Phoenix server"""

    def __init__(self, server_url, on_frame_callback, controller_id=None):
        self.server_url = server_url
        self.on_frame_callback = on_frame_callback
        self.controller_id = controller_id or str(uuid.uuid4())

        # WebSocket connection
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.reconnect_timer = None
        self.heartbeat_timer = None
        self.stats_timer = None  # Initialize stats_timer attribute

        # Phoenix channel state
        self.channel_joined = False

        # Stats and monitoring
        self.stats = {
            "frames_received": 0,
            "connection_drops": 0,
            "connection_start_time": 0,
            "connection_uptime": 0,
            "last_frame_time": 0,
            "fps": 0,
        }

        # Last received data for potential reconnection recovery
        self.last_pattern_id = None
        self.last_parameters = None

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
        """Send controller information"""
        if not self.connected or not self.channel_joined:
            return

        info = {
            "topic": "controller:lobby",
            "event": "stats",
            "payload": {
                "type": "controller_info",
                "id": self.controller_id,
                "width": getattr(self, "width", 25),
                "height": getattr(self, "height", 24),
                "version": "1.0.0",
                "hardware": "Raspberry Pi"
                if hasattr(self, "is_hardware_available") and self.is_hardware_available
                else "Mock",
                "layout": getattr(self, "layout", "serpentine"),
                "orientation": {
                    "flip_x": getattr(self, "flip_x", False),
                    "flip_y": getattr(self, "flip_y", False),
                    "transpose": getattr(self, "transpose", False),
                },
            },
            "ref": None,
        }

        try:
            self.ws.send(json.dumps(info))
            logger.info("Sent controller info")
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
        self._send_join_message()

        # Set up heartbeat
        self._setup_heartbeat()

        # Set up stats reporting
        self._setup_stats_reporting()

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Check if message is binary
            if isinstance(message, bytes):
                # Process binary frame directly
                logger.debug(f"Received binary message ({len(message)} bytes)")
                self.on_frame_callback(message)
                self._update_frame_stats()
                return

            # Handle text (JSON) messages
            data = json.loads(message)

            # Extract Phoenix message components
            event = data.get("event")
            payload = data.get("payload", {})

            logger.debug(f"Received event: {event}")

            if event == "phx_reply" and payload.get("status") == "ok":
                # Join confirmation
                if (
                    "response" in payload
                    and payload["response"].get("status") == "connected"
                ):
                    logger.info("Successfully joined controller channel")
                    self.channel_joined = True

                    # Send controller info
                    self.send_controller_info()

                    # Request initial batch of frames
                    logger.info("Requesting initial batch of frames")
                    self._request_batch(0)

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

                    if "binary" in payload:
                        # Extract and decode binary data
                        binary_data = base64.b64decode(payload["binary"])
                        logger.info(
                            f"Processing batch: {len(binary_data)} bytes, seq={seq}, pattern={pattern}"
                        )

                        # Process the binary batch
                        self.on_frame_callback(binary_data)
                        self._update_frame_stats()
                    else:
                        # Fallback for non-binary payloads (less common)
                        logger.debug("Processing batch data from payload (non-binary)")
                        self.on_frame_callback(message)
                        self._update_frame_stats()

                    # Request the next batch of frames
                    self._request_batch(seq + 1)
                except Exception as e:
                    logger.error(f"Error processing display_batch: {e}")
                    # Attempt to request next batch anyway
                    try:
                        seq = payload.get("sequence", 0)
                        self._request_batch(seq + 1)
                    except:
                        pass

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

    def _send_join_message(self):
        """Send Phoenix channel join message"""
        join_message = {
            "topic": "controller:lobby",
            "event": "phx_join",
            "payload": {"controller_id": self.controller_id},
            "ref": "1",
        }

        try:
            self.ws.send(json.dumps(join_message))
            logger.info("Sent join message")
        except Exception as e:
            logger.error(f"Error sending join message: {e}")

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

        # Calculate FPS
        if self.stats["last_frame_time"] > 0:
            time_diff = current_time - self.stats["last_frame_time"]
            if time_diff > 0:
                # Apply smoothing to FPS calculation
                new_fps = 1.0 / time_diff
                self.stats["fps"] = 0.8 * self.stats["fps"] + 0.2 * new_fps

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
        if not self.connected or not self.channel_joined:
            logger.warning("Cannot request batch: not connected or not joined")
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
                    "urgent": sequence == 0,  # First request is urgent
                },
                "ref": None,
            }

            # Send the request
            self.ws.send(json.dumps(request_message))
            logger.debug(f"Sent batch request: seq={sequence}, space={space}")
            return True
        except Exception as e:
            logger.error(f"Error requesting batch: {e}")
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
