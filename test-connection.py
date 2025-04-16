#!/usr/bin/env python3
"""
Simple script to test WebSocket connection to the legrid server
"""

import websocket
import json
import time
import logging
import argparse
import base64

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test-connection")


def on_open(ws):
    """Handle WebSocket connection open"""
    logger.info("WebSocket connection established")

    # Join the Phoenix channel
    join_message = {
        "topic": "controller:lobby",
        "event": "phx_join",
        "payload": {"controller_id": "test-client"},
        "ref": "1",
    }

    logger.info(f"Sending join message: {join_message}")
    ws.send(json.dumps(join_message))

    # Send controller info
    info_message = {
        "topic": "controller:lobby",
        "event": "stats",
        "payload": {
            "type": "controller_info",
            "id": "test-client",
            "width": 25,
            "height": 24,
            "led_count": 600,
            "version": "1.0.0",
            "hardware": "Test Client",
            "layout": "serpentine",
            "orientation": {
                "flip_x": False,
                "flip_y": False,
                "transpose": False,
            },
        },
        "ref": None,
    }

    logger.info("Sending controller info")
    ws.send(json.dumps(info_message))


def on_message(ws, message):
    """Handle received messages"""
    logger.info(f"Received message of type: {type(message)}")

    if isinstance(message, bytes):
        logger.info(f"Received binary message of {len(message)} bytes")
        logger.debug(f"First 20 bytes: {message[:20].hex()}")
        return

    try:
        data = json.loads(message)
        event = data.get("event")
        topic = data.get("topic", "")
        ref = data.get("ref")

        logger.info(f"Received event: {event} on topic: {topic}")

        if event == "phx_reply" and data.get("payload", {}).get("status") == "ok":
            logger.info("Successfully joined channel!")

        elif event == "frame" and "payload" in data and "binary" in data["payload"]:
            logger.info("Received frame with binary data")
            try:
                # Decode base64 binary data
                binary_data = base64.b64decode(data["payload"]["binary"])
                logger.info(f"Decoded binary frame: {len(binary_data)} bytes")

                # Print first few bytes for debugging
                if len(binary_data) > 0:
                    logger.info(f"First 10 bytes: {binary_data[:10].hex()}")
            except Exception as e:
                logger.error(f"Error decoding binary data: {e}")

        # For non-binary/non-frame messages, print the whole thing
        if event != "frame":
            logger.info(f"Full message: {message}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        if isinstance(message, str):
            logger.error(f"Message preview: {message[:100]}")


def on_error(ws, error):
    """Handle WebSocket errors"""
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close"""
    logger.info(f"Connection closed: {close_status_code} - {close_msg}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test WebSocket connection to legrid server"
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:4000/controller/websocket",
        help="WebSocket server URL (default: ws://localhost:4000/controller/websocket)",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Enable trace for detailed WebSocket debugging
    websocket.enableTrace(True)

    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        args.url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    logger.info(f"Connecting to {args.url}...")

    # Run the WebSocket connection with a timeout
    ws.run_forever(ping_interval=5, ping_timeout=3, ping_payload="ping")


if __name__ == "__main__":
    main()
