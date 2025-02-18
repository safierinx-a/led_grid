#!/usr/bin/env python3

import time
import json
import paho.mqtt.client as mqtt
import zmq
from rpi_ws281x import PixelStrip, Color
import argparse
import os
from dotenv import load_dotenv
import traceback

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
    def __init__(self, mqtt_host=None, zmq_host=None):
        # Hardware setup
        self.strip = None
        self.init_strip()

        # MQTT setup for control plane
        self.mqtt_host = mqtt_host or os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_user = os.getenv("MQTT_USER")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_client = None
        self.is_mqtt_connected = False

        # ZMQ setup for frame data
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.DEALER)
        self.zmq_host = zmq_host or os.getenv("ZMQ_HOST", self.mqtt_host)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set socket options
        self.frame_socket.setsockopt(zmq.LINGER, 0)
        self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
        self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)  # 100ms timeout

        # Performance tracking
        self.frame_count = 0
        self.frame_times = []
        self.last_fps_print = time.time()
        self.last_frame_time = time.time()
        self.frame_timeout = 5.0  # seconds

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

    def connect_mqtt(self):
        """Connect to MQTT broker for control plane"""
        try:
            # Create client with unique ID
            client_id = f"led_controller_{int(time.time())}"
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Set up callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message

            # Set up authentication if provided
            if self.mqtt_user and self.mqtt_password:
                self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

            # Connect to broker
            print(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()

            # Wait for connection
            timeout = 10
            while timeout > 0 and not self.is_mqtt_connected:
                time.sleep(0.1)
                timeout -= 0.1

            if not self.is_mqtt_connected:
                raise Exception("MQTT connection timeout")

            # Subscribe to control topics
            self.mqtt_client.subscribe("led/command/#")
            return True

        except Exception as e:
            print(f"Error connecting to MQTT: {e}")
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client = None
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

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            print("Connected to MQTT broker successfully")
            self.is_mqtt_connected = True
            self.mqtt_client.publish("led/status/led_controller", "online", retain=True)
        else:
            print(f"Failed to connect to MQTT broker with code {rc}")
            self.is_mqtt_connected = False

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        print(f"Disconnected from MQTT broker with code {rc}")
        self.is_mqtt_connected = False

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT control messages"""
        try:
            print(f"Received message on topic: {msg.topic}")
            data = json.loads(msg.payload.decode())

            if msg.topic == "led/command/clear":
                self.clear_strip()
            elif msg.topic == "led/command/brightness":
                if "value" in data:
                    self.strip.setBrightness(int(data["value"]))
                    self.strip.show()

        except Exception as e:
            print(f"Error handling MQTT message: {e}")

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
            # Initial connections
            if not self.connect_mqtt():
                print("Failed to connect to MQTT broker")
                return

            if not self.connect_zmq():
                print("Failed to connect to ZMQ server")
                return

            print("Starting frame reception loop...")
            while True:
                try:
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

                    # Performance reporting
                    current_time = time.time()
                    if current_time - self.last_fps_print >= 1.0:
                        if self.frame_count > 0 and self.frame_times:
                            avg_frame_time = sum(self.frame_times) / len(
                                self.frame_times
                            )
                            fps = self.frame_count / (
                                current_time - self.last_fps_print
                            )
                            print(
                                f"FPS: {fps:.1f}, Frame time: {avg_frame_time * 1000:.1f}ms"
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

        # Clean up MQTT
        if self.mqtt_client:
            try:
                self.mqtt_client.publish(
                    "led/status/led_controller", "offline", retain=True
                )
                time.sleep(0.1)
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
    parser.add_argument("--mqtt-host", help="MQTT broker hostname or IP")
    parser.add_argument("--zmq-host", help="ZMQ server hostname or IP")
    args = parser.parse_args()

    controller = LEDController(mqtt_host=args.mqtt_host, zmq_host=args.zmq_host)
    controller.run()
