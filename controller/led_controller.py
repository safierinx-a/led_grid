#!/usr/bin/env python3

import time
import json
import zmq
from rpi_ws281x import PixelStrip, Color
import argparse
import os
from dotenv import load_dotenv
import traceback
import paho.mqtt.client as mqtt
from typing import Dict, Any

# Load environment variables
load_dotenv()

# LED strip configuration
LED_COUNT = 600  # Total number of LEDs (24 strips * 25 LEDs)
LED_PIN = 18  # GPIO pin connected to the pixels
LED_FREQ_HZ = 800000  # LED signal frequency in hertz
LED_DMA = 10  # DMA channel to use
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal
LED_CHANNEL = 0  # PWM channel


class LEDController:
    def __init__(self, zmq_host=None):
        # Hardware setup
        self.strip = None
        self.init_strip()

        # ZMQ setup for frame data
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.DEALER)
        self.zmq_host = zmq_host or os.getenv("ZMQ_HOST", "localhost")
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # MQTT setup for status updates
        self.mqtt_client = mqtt.Client(f"led_controller_{int(time.time())}")
        self.mqtt_client.username_pw_set(
            os.getenv("MQTT_USER"), os.getenv("MQTT_PASSWORD")
        )
        self.mqtt_client.connect(
            os.getenv("MQTT_BROKER", "localhost"),
            int(os.getenv("MQTT_PORT", "1883")),
            60,
        )
        self.mqtt_client.loop_start()

        # Publish initial status
        self.mqtt_client.publish("led/status/led_controller", "online", retain=True)

        # Performance tracking
        self.frame_count = 0
        self.frame_times = []
        self.last_fps_print = time.time()
        self.last_frame_time = time.time()
        self.frame_timeout = 5.0  # seconds
        self.performance_log_interval = (
            5.0  # Log every 5 seconds instead of every second
        )

        # Frame rate limiting
        self.target_fps = (
            24.0  # Reduced from 60 to 24 for better LED animation performance
        )
        self.target_frame_time = 1.0 / self.target_fps
        self.next_frame_time = time.time()

        # Error handling
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_reset_interval = 60.0  # seconds

        # Pattern tracking
        self.last_pattern_id = None

    def init_strip(self):
        """Initialize LED strip with error handling"""
        try:
            self.strip = PixelStrip(
                LED_COUNT,
                LED_PIN,
                LED_FREQ_HZ,
                LED_DMA,
                LED_INVERT,
                LED_BRIGHTNESS,
                LED_CHANNEL,
            )
            self.strip.begin()
            print("LED strip initialized successfully")
            return True
        except Exception as e:
            print(f"Error initializing LED strip: {e}")
            traceback.print_exc()
            return False

    def connect_zmq(self):
        """Connect to ZMQ server for frame data"""
        try:
            # Set socket options for reliability
            self.frame_socket.setsockopt(
                zmq.LINGER, 0
            )  # Don't wait for pending messages
            self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
            self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)  # 100ms timeout
            self.frame_socket.setsockopt(
                zmq.RCVHWM, 10
            )  # High water mark for receiving
            self.frame_socket.setsockopt(zmq.SNDHWM, 10)  # High water mark for sending
            self.frame_socket.setsockopt(zmq.RECONNECT_IVL, 100)  # Reconnect interval
            self.frame_socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, 5000
            )  # Max reconnect interval

            zmq_address = f"tcp://{self.zmq_host}:{self.zmq_port}"
            print(f"Connecting to ZMQ server at {zmq_address}")
            self.frame_socket.connect(zmq_address)
            return True
        except Exception as e:
            print(f"Error connecting to ZMQ server: {e}")
            return False

    def clear_strip(self):
        """Turn off all LEDs"""
        try:
            for i in range(LED_COUNT):
                self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()
        except Exception as e:
            print(f"Error clearing strip: {e}")

    def handle_frame(self, frame_data: bytearray, metadata: Dict[str, Any]) -> bool:
        """Handle incoming frame data"""
        try:
            # Clear strip on pattern change
            if metadata.get("pattern_id") != self.last_pattern_id:
                self.clear_strip()
                self.last_pattern_id = metadata.get("pattern_id")

            # Update frame data
            if len(frame_data) > 0:
                # Ensure we have enough data for all pixels
                if len(frame_data) >= LED_COUNT * 3:
                    # Get brightness from display state
                    display_state = metadata.get("display_state", {})
                    brightness = display_state.get("brightness", 1.0)
                    brightness = max(0.0, min(1.0, brightness))

                    print(f"LED Controller received brightness: {brightness}")
                    print(f"Display state: {display_state}")

                    # Update each pixel with brightness adjustment
                    for i in range(LED_COUNT):
                        r = int(frame_data[i * 3] * brightness)
                        g = int(frame_data[i * 3 + 1] * brightness)
                        b = int(frame_data[i * 3 + 2] * brightness)
                        self.strip.setPixelColor(i, Color(r, g, b))
                    self.strip.show()
                    return True
                else:
                    print(f"Invalid frame data length: {len(frame_data)}")
                    return False
            return True
        except Exception as e:
            print(f"Error handling frame: {e}")
            traceback.print_exc()
            return False

    def run(self):
        """Main controller loop"""
        print("Starting LED controller...")
        self.is_running = True
        last_performance_report = time.time()
        frame_count = 0
        frame_times = []
        last_frame_requested = 0
        self.last_pattern_id = None  # Track last pattern ID

        # Connect to ZMQ server
        if not self.connect_zmq():
            print("Failed to connect to ZMQ server. Exiting...")
            self.is_running = False
            return

        print(f"Connected to ZMQ server at tcp://{self.zmq_host}:{self.zmq_port}")

        # Clear the strip initially to prevent stale data
        self.clear_strip()

        while self.is_running:
            try:
                current_time = time.time()

                # Request frame if enough time has passed since last frame
                # This avoids frame rate limiting issues by requesting as soon as we're done processing
                if current_time - last_frame_requested >= (1.0 / self.target_fps):
                    try:
                        # Simple READY message - DEALER socket handles the rest
                        self.frame_socket.send(b"READY")
                        last_frame_requested = current_time
                    except zmq.error.Again:
                        # If send fails, wait a bit before retrying
                        time.sleep(0.001)
                        continue
                    except zmq.error.ZMQError as e:
                        print(f"ZMQ send error: {e}")
                        # Try to reconnect
                        if not self.connect_zmq():
                            print("Failed to reconnect to ZMQ server")
                            time.sleep(1)
                        continue

                # Handle incoming frame - use a minimal blocking timeout
                try:
                    # Use poll with a short timeout to avoid busy-waiting
                    if self.frame_socket.poll(10):  # 10ms timeout
                        # Receive message parts
                        msg_type = self.frame_socket.recv()
                        metadata_json = self.frame_socket.recv()
                        frame_data = self.frame_socket.recv()

                        if msg_type == b"frame":
                            frame_start = time.time()
                            try:
                                metadata = json.loads(metadata_json.decode())

                                # Only process the frame if it has data
                                if len(frame_data) > 0:
                                    success = self.handle_frame(frame_data, metadata)
                                    if not success:
                                        # On frame handling error, clear the strip to prevent partial updates
                                        self.clear_strip()
                                else:
                                    # Empty frame is a heartbeat, not an error
                                    pass

                                frame_time = time.time() - frame_start
                                frame_times.append(frame_time)
                                frame_count += 1
                            except json.JSONDecodeError as e:
                                print(f"Error decoding metadata: {e}")
                    else:
                        # No data available, short sleep to prevent CPU hogging
                        time.sleep(0.001)
                        continue

                except zmq.error.ZMQError as e:
                    if e.errno == zmq.EAGAIN:
                        # No message available, not an error
                        time.sleep(0.001)
                        continue
                    else:
                        print(f"ZMQ receive error: {e}")
                        # Try to reconnect
                        if not self.connect_zmq():
                            print("Failed to reconnect to ZMQ server")
                            time.sleep(1)
                        continue

                # Performance reporting
                if (
                    current_time - last_performance_report >= 5.0
                ):  # Report every 5 seconds
                    if frame_times:
                        avg_frame_time = sum(frame_times) / len(frame_times)
                        fps = frame_count / (current_time - last_performance_report)
                        print(
                            f"Performance: FPS={fps:.1f}, Frame={avg_frame_time * 1000:.1f}ms"
                        )
                        frame_times.clear()
                        frame_count = 0
                        last_performance_report = current_time

            except Exception as e:
                print(f"Error in main loop: {e}")
                traceback.print_exc()
                # Clear strip on errors to prevent hanging LEDs
                self.clear_strip()
                time.sleep(0.1)  # Prevent tight error loop

    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down...")

        # Clear LEDs
        self.clear_strip()

        # Publish offline status
        self.mqtt_client.publish("led/status/led_controller", "offline", retain=True)

        # Clean up MQTT
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except:
            pass

        # Clean up ZMQ
        try:
            self.frame_socket.close()
            self.zmq_context.term()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LED Controller")
    parser.add_argument("--zmq-host", help="ZMQ server hostname or IP")
    args = parser.parse_args()

    controller = LEDController(zmq_host=args.zmq_host)
    controller.run()
