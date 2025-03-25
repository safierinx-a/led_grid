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

        # Frame rate limiting
        self.target_fps = 60.0
        self.target_frame_time = 1.0 / self.target_fps
        self.next_frame_time = time.time()

        # Error handling
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_reset_interval = 60.0  # seconds

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

    def handle_frame(self, frame_data: bytes, metadata: dict):
        """Process and display a frame of LED data"""
        try:
            frame_start = time.time()

            # Update LED strip
            for i in range(LED_COUNT):
                idx = i * 3
                if idx + 2 < len(frame_data):
                    r = frame_data[idx]
                    g = frame_data[idx + 1]
                    b = frame_data[idx + 2]
                    self.strip.setPixelColor(i, Color(r, g, b))

            self.strip.show()

            # Performance tracking
            self.last_frame_time = time.time()
            frame_time = self.last_frame_time - frame_start
            self.frame_times.append(frame_time)
            if len(self.frame_times) > 100:
                self.frame_times.pop(0)
            self.frame_count += 1

            # Reset error counter on successful frame
            self.consecutive_errors = 0

            return True

        except Exception as e:
            print(f"Error handling frame: {e}")
            self.consecutive_errors += 1
            return False

    def run(self):
        """Main run loop"""
        try:
            # Initial connection
            if not self.connect_zmq():
                print("Failed to connect to ZMQ server")
                return

            print("Starting frame reception loop...")
            while True:
                try:
                    # Wait until it's time for the next frame
                    current_time = time.time()
                    if current_time < self.next_frame_time:
                        time.sleep(0.001)  # Small sleep to prevent busy waiting
                        continue

                    # Request new frame
                    self.frame_socket.send(b"READY")

                    # Receive frame
                    topic, metadata_bytes, frame_data = (
                        self.frame_socket.recv_multipart()
                    )
                    metadata = json.loads(metadata_bytes.decode())

                    # Handle frame
                    if not self.handle_frame(frame_data, metadata):
                        if self.consecutive_errors >= self.max_consecutive_errors:
                            print("Too many consecutive errors, reinitializing...")
                            if not self.init_strip():
                                print("Failed to reinitialize strip")
                                break
                            self.consecutive_errors = 0

                    # Update next frame time
                    self.next_frame_time = current_time + self.target_frame_time

                    # Performance reporting
                    if current_time - self.last_fps_print >= 1.0:
                        if self.frame_count > 0 and self.frame_times:
                            avg_frame_time = sum(self.frame_times) / len(
                                self.frame_times
                            )
                            fps = self.frame_count / (
                                current_time - self.last_fps_print
                            )
                            print(
                                f"Display FPS: {fps:.1f}, Frame time: {avg_frame_time * 1000:.1f}ms"
                            )
                        self.frame_count = 0
                        self.last_fps_print = current_time

                except zmq.Again:
                    # Handle timeout
                    if time.time() - self.last_frame_time > self.frame_timeout:
                        print("Frame timeout - server may be down")
                        self.clear_strip()
                        time.sleep(1)
                    continue

                except Exception as e:
                    print(f"Error in main loop: {e}")
                    traceback.print_exc()
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutdown requested...")
        finally:
            self.shutdown()

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
