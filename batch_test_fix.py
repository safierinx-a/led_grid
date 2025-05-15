#!/usr/bin/env python3
"""
Minimal test case for LED Grid batch request mechanism
"""

import json
import time
import logging
import sys
import websocket
import threading
import base64

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("batch-test")


class BatchTester:
    def __init__(self, server_url, controller_id="test-controller"):
        self.server_url = server_url
        self.controller_id = controller_id
        self.ws = None
        self.connected = False
        self.channel_joined = False
        self.running = True
        self.last_batch_sequence = 0
        self.frames_received = 0

    def connect(self):
        """Connect to WebSocket server"""
        logger.info(f"Connecting to {self.server_url}...")

        # Enable binary frames (important!)
        websocket.enableTrace(True)

        # Setup WebSocket
        self.ws = websocket.WebSocketApp(
            self.server_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        # Start WebSocket connection in separate thread
        self.ws_thread = threading.Thread(
            target=lambda: self.ws.run_forever(
                # These options are crucial for binary frame support
                ping_interval=10,
                ping_timeout=5,
                skip_utf8_validation=True,  # Important for binary data
            )
        )
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")
        self.connected = True

        # Join Phoenix channel
        join_message = {
            "topic": "controller:lobby",
            "event": "phx_join",
            "payload": {"controller_id": self.controller_id},
            "ref": "1",
        }
        logger.info("Sending channel join request...")
        self.ws.send(json.dumps(join_message))

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        # Check if message is binary or text
        if isinstance(message, bytes):
            self.handle_binary_message(message)
        else:
            self.handle_json_message(message)

    def handle_binary_message(self, message):
        """Handle binary message (batch data)"""
        if len(message) < 10:
            logger.warning("Binary message too short")
            return

        # Log the first few bytes
        prefix = " ".join([f"{b:02x}" for b in message[:16]])
        logger.debug(f"Binary message starts with: {prefix}...")

        # Check if this is a batch frame message (starts with byte 0xB)
        if message[0] == 0xB:
            frame_count = int.from_bytes(message[1:5], byteorder="little")
            is_priority = bool(message[5])
            batch_sequence = int.from_bytes(message[6:10], byteorder="little")

            logger.info(f"Received batch #{batch_sequence} with {frame_count} frames")
            self.last_batch_sequence = batch_sequence
            self.frames_received += frame_count

            # After receiving a batch, request the next one
            self.request_batch()
        else:
            logger.warning(
                f"Received unknown binary message, first byte: 0x{message[0]:02x}"
            )

    def handle_json_message(self, message):
        """Handle JSON message"""
        try:
            data = json.loads(message)
            event = data.get("event")
            topic = data.get("topic", "")
            ref = data.get("ref")
            payload = data.get("payload", {})

            logger.debug(f"Received JSON message: event={event}, topic={topic}")

            # Handle Phoenix protocol messages
            if event == "phx_reply" and topic == "controller:lobby":
                if payload.get("status") == "ok":
                    # This could be a join confirmation
                    if not self.channel_joined:
                        logger.info("Channel join confirmed!")
                        self.channel_joined = True
                        # Request first batch
                        self.request_batch()
                else:
                    logger.warning(f"Received error reply: {payload}")

            elif event == "display_batch" and "frames" in payload:
                # Try to decode base64 data if present
                try:
                    logger.info("Received display_batch event with base64 data")
                    batch_data = base64.b64decode(payload["frames"])
                    logger.info(f"Decoded base64 data, got {len(batch_data)} bytes")

                    # Handle the batch data just like a binary message
                    self.handle_binary_message(batch_data)
                except Exception as e:
                    logger.error(f"Error processing base64 batch data: {e}")

        except Exception as e:
            logger.error(f"Error handling JSON message: {e}")

    def on_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
        self.channel_joined = False

    def request_batch(self):
        """Request a frame batch from the server"""
        if not self.connected or not self.channel_joined:
            logger.warning(
                f"Cannot request batch: connected={self.connected}, channel_joined={self.channel_joined}"
            )
            return

        # Create batch request message
        request = {
            "topic": "controller:lobby",
            "event": "request_batch",
            "payload": {
                "controller_id": self.controller_id,
                "last_sequence": self.last_batch_sequence,
                "space_available": 20,  # Request up to 20 frames
                "urgent": True,
                "buffer_fullness": 0,
                "buffer_capacity": 60,
                "timestamp": int(time.time() * 1000),
            },
            "ref": None,
        }

        # Send request
        logger.info(f"Requesting batch after sequence #{self.last_batch_sequence}")
        self.ws.send(json.dumps(request))

    def run(self):
        """Run the test"""
        self.connect()

        # Main loop
        try:
            while self.running:
                time.sleep(1)

                # Every 15 seconds, send a heartbeat to keep connection alive
                if self.connected:
                    heartbeat = {
                        "topic": "phoenix",
                        "event": "heartbeat",
                        "payload": {},
                        "ref": str(int(time.time())),
                    }
                    self.ws.send(json.dumps(heartbeat))
                    logger.debug("Sent heartbeat")

                # If we're joined but haven't received frames, retry request
                if self.connected and self.channel_joined and self.frames_received == 0:
                    logger.info("No frames received yet, requesting batch again")
                    self.request_batch()

        except KeyboardInterrupt:
            logger.info("Test interrupted")
            self.running = False

        finally:
            # Clean up
            if self.ws:
                self.ws.close()

        logger.info(f"Test complete. Received {self.frames_received} frames")


if __name__ == "__main__":
    # Get server URL from command line or use default
    server_url = (
        sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:4000/controller/websocket"
    )

    # Run the test
    tester = BatchTester(server_url)
    tester.run()
