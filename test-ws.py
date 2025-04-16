#!/usr/bin/env python3
import websocket
import json
import time
import logging
import base64
import threading

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# Connection URL - replace with your server IP
url = "ws://192.168.1.11:4000/controller/websocket"

# Global variables
reconnect_delay = 1.0
running = True
last_pong_time = 0
connection_timeout = 30  # Consider connection dead after 30 seconds without pong
missing_pong_count = 0


def on_message(ws, message):
    logger.info(f"Received: {message}")

    try:
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
                logger.debug(f"Received frame binary data of length {len(binary_data)}")
                # Log first 20 bytes of the binary data for debugging
                logger.debug(f"Binary data start: {binary_data[:20].hex()}")

        elif event == "ping":
            # Respond to ping
            ws.send(
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


def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.info(f"Connection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    logger.info("Connection established")

    # Join the Phoenix channel
    join_message = {
        "topic": "controller:lobby",
        "event": "phx_join",
        "payload": {"controller_id": "test-client"},
        "ref": "1",
    }

    logger.info(f"Sending join message: {json.dumps(join_message)}")
    ws.send(json.dumps(join_message))


def on_ping(ws, message):
    logger.debug(f"Received ping: {message}")


def on_pong(ws, message):
    global last_pong_time
    logger.debug(f"Received pong: {message}")
    last_pong_time = time.time()


def monitor_connection(ws):
    """Monitor connection health and handle reconnection if needed"""
    global running, last_pong_time, missing_pong_count

    while running and ws.sock and ws.sock.connected:
        try:
            # Check if we've missed pongs
            if time.time() - last_pong_time > connection_timeout:
                missing_pong_count += 1
                logger.warning(
                    f"No pong received in {connection_timeout} seconds. Count: {missing_pong_count}"
                )

                # If we've missed too many pongs, force a reconnection
                if missing_pong_count >= 3:
                    logger.error(
                        "Connection appears to be dead. Forcing reconnection..."
                    )
                    if ws and ws.sock:
                        ws.close()
                    return

                # Send a ping to check if connection is alive
                if ws and ws.sock and ws.sock.connected:
                    ws.ping("ping")

            # Send a regular heartbeat
            if ws and ws.sock and ws.sock.connected:
                heartbeat = {
                    "topic": "phoenix",
                    "event": "heartbeat",
                    "payload": {},
                    "ref": "1",
                }
                ws.send(json.dumps(heartbeat))

        except Exception as e:
            logger.error(f"Error in monitor thread: {e}")

        time.sleep(10)  # Check connection every 10 seconds


def run():
    """Run the controller, connecting to the WebSocket server"""
    global reconnect_delay, running, last_pong_time, missing_pong_count

    while running:
        try:
            # Create WebSocket connection with robust settings
            ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_ping=on_ping,
                on_pong=on_pong,
            )

            # Initialize connection monitoring
            last_pong_time = time.time()
            missing_pong_count = 0

            # Start connection monitoring thread
            monitor_thread = threading.Thread(target=monitor_connection, args=(ws,))
            monitor_thread.daemon = True
            monitor_thread.start()

            # Connect to the server with optimized settings
            logger.info(f"Connecting to {url}...")
            try:
                # Try with all parameters first
                ws.run_forever(
                    ping_interval=5,  # Send ping every 5 seconds
                    ping_timeout=3,  # Wait 3 seconds for pong response
                    ping_payload="ping",  # Custom ping payload for debugging
                )
            except TypeError as e:
                # Handle the case where binary_type parameter is causing issues
                if "unexpected keyword argument 'binary_type'" in str(e):
                    logger.warning(
                        "WebSocket client does not support binary_type parameter, using fallback"
                    )
                    # Fall back to basic connection
                    ws.run_forever()
                else:
                    # Re-raise if it's a different TypeError
                    raise

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


if __name__ == "__main__":
    run()
