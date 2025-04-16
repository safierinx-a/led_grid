#!/usr/bin/env python3
"""
Test script for Phoenix Channel WebSocket connection
"""

import websocket
import json
import time
import base64
import logging
import sys
import struct

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("phoenix-test")

# Connection parameters
SERVER_URL = "ws://192.168.1.11:4000/controller/websocket"
CONTROLLER_ID = "test-client-debugging"
CHANNEL_TOPIC = "controller:lobby"


def decode_frame(binary_data):
    """Decode a binary frame and print its contents"""
    try:
        if len(binary_data) < 10:
            logger.error(f"Frame too short: {len(binary_data)} bytes")
            return

        # Print the first 30 bytes in hex for debugging
        logger.info(f"First 30 bytes (hex): {binary_data[:30].hex()}")

        # Parse header
        version = binary_data[0]
        msg_type = binary_data[1]
        frame_id = struct.unpack("<I", binary_data[2:6])[0]
        width = struct.unpack("<H", binary_data[6:8])[0]
        height = struct.unpack("<H", binary_data[8:10])[0]

        logger.info(
            f"Frame: version={version}, type={msg_type}, id={frame_id}, dims={width}x{height}"
        )

        if msg_type == 1:  # Full frame
            pixel_count = width * height
            expected_bytes = 10 + (pixel_count * 3)  # Header + RGB for each pixel
            logger.info(
                f"Full frame: {pixel_count} pixels, expecting {expected_bytes} bytes"
            )

            if len(binary_data) < expected_bytes:
                logger.warning(
                    f"Frame truncated: {len(binary_data)} bytes (expected {expected_bytes})"
                )

            # Sample a few pixels
            for i in range(min(5, pixel_count)):
                idx = 10 + (i * 3)  # Skip header, then 3 bytes per pixel
                if idx + 2 < len(binary_data):
                    r = binary_data[idx]
                    g = binary_data[idx + 1]
                    b = binary_data[idx + 2]
                    logger.info(f"Pixel {i}: RGB({r}, {g}, {b})")

        elif msg_type == 2:  # Delta frame
            if len(binary_data) < 12:  # Header + delta count (2 bytes)
                logger.warning(f"Delta frame too short: {len(binary_data)} bytes")
                return

            num_deltas = struct.unpack("<H", binary_data[10:12])[0]
            logger.info(f"Delta frame: {num_deltas} pixel changes")

            if len(binary_data) < 12 + (num_deltas * 5):
                logger.warning("Delta frame truncated")

            # Sample a few delta changes
            delta_data = binary_data[12:]
            for i in range(min(5, num_deltas)):
                idx = i * 5
                if idx + 4 < len(delta_data):
                    pixel_idx = struct.unpack("<H", delta_data[idx : idx + 2])[0]
                    r = delta_data[idx + 2]
                    g = delta_data[idx + 3]
                    b = delta_data[idx + 4]
                    logger.info(f"Delta {i}: Pixel {pixel_idx} -> RGB({r}, {g}, {b})")
        else:
            logger.warning(f"Unknown message type: {msg_type}")

    except Exception as e:
        logger.error(f"Error decoding frame: {e}")
        import traceback

        logger.error(traceback.format_exc())


def on_message(ws, message):
    """Handle incoming WebSocket messages"""
    if isinstance(message, bytes):
        logger.info(f"Received binary message ({len(message)} bytes)")
        try:
            decode_frame(message)
        except Exception as e:
            logger.error(f"Failed to decode binary message: {e}")
    else:
        try:
            data = json.loads(message)
            event = data.get("event")
            topic = data.get("topic", "")
            ref = data.get("ref")

            logger.info(f"Received: topic={topic}, event={event}, ref={ref}")

            if event == "phx_reply" and data.get("payload", {}).get("status") == "ok":
                logger.info("Successfully joined channel!")

            elif event == "frame" and "payload" in data and "binary" in data["payload"]:
                logger.info("Received frame with binary data")
                try:
                    # Decode base64 binary data
                    binary_data = base64.b64decode(data["payload"]["binary"])
                    logger.info(f"Decoded binary data ({len(binary_data)} bytes)")

                    # Analyze the frame
                    decode_frame(binary_data)
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")

            # Print full JSON for any other message
            if event != "frame":  # Skip frame events as they're large
                logger.debug(f"Full message: {message}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Print first 100 chars of message
            if isinstance(message, str):
                logger.error(f"Message start: {message[:100]}")


def on_error(ws, error):
    """Handle WebSocket errors"""
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close"""
    logger.info(f"Connection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Handle WebSocket connection open"""
    logger.info("Connection established")

    # Join the Phoenix channel
    join_message = {
        "topic": CHANNEL_TOPIC,
        "event": "phx_join",
        "payload": {"controller_id": CONTROLLER_ID, "version": "1.0.0"},
        "ref": "1",
    }

    logger.info(f"Joining channel: {join_message}")
    ws.send(json.dumps(join_message))


def main():
    """Main entry point"""
    # Enable trace for detailed WebSocket debugging
    websocket.enableTrace(True)

    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        SERVER_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    # Connect with ping enabled
    logger.info(f"Connecting to {SERVER_URL}...")
    ws.run_forever(ping_interval=10, ping_timeout=5, skip_utf8_validation=True)


if __name__ == "__main__":
    main()
