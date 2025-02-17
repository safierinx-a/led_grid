#!/usr/bin/env python3

import time
import json
import paho.mqtt.client as mqtt
import zmq  # Add ZMQ import
from rpi_ws281x import PixelStrip, Color
import argparse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LED strip configuration
LED_COUNT = 600  # Total number of LEDs (24 strips * 25 LEDs)
LED_PIN = 18  # GPIO pin connected to the pixels
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal
LED_CHANNEL = 0  # PWM channel to use

# Target frame rate
TARGET_FPS = 60
FRAME_TIME = 1.0 / TARGET_FPS


class LEDController:
    def __init__(self, mqtt_host=None, zmq_host=None):
        # Create NeoPixel object with appropriate configuration
        self.init_strip()

        # MQTT setup for commands
        self.mqtt_host = mqtt_host or os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_user = os.getenv("MQTT_USER")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")

        # ZMQ setup for frame data
        self.zmq_context = zmq.Context()
        self.frame_sub_socket = self.zmq_context.socket(zmq.SUB)
        self.zmq_host = zmq_host or os.getenv("ZMQ_HOST", self.mqtt_host)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set ZMQ socket options
        self.frame_sub_socket.setsockopt(zmq.LINGER, 0)
        self.frame_sub_socket.setsockopt(zmq.RCVHWM, 2)  # Only keep last 2 frames
        self.frame_sub_socket.setsockopt_string(
            zmq.SUBSCRIBE, "frame"
        )  # Subscribe to frame topic

        print(f"MQTT Configuration:")
        print(f"Host: {self.mqtt_host}")
        print(f"Port: {self.mqtt_port}")
        print(f"User: {self.mqtt_user}")
        print(
            f"Password: {'*' * len(self.mqtt_password) if self.mqtt_password else 'None'}"
        )

        print(f"\nZMQ Configuration:")
        print(f"Host: {self.zmq_host}")
        print(f"Port: {self.zmq_port}")

        # Initialize MQTT client
        self.mqtt_client = None
        self.is_connected = False

        # Frame buffer to store current state
        self.frame_buffer = [(0, 0, 0)] * LED_COUNT
        self.needs_update = False
        self.last_update_time = time.time()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_reset_interval = 60

        # Performance tracking
        self.frame_count = 0
        self.frame_times = []
        self.last_frame_time = time.time()
        self.last_fps_print = time.time()

    def init_strip(self):
        """Initialize the LED strip with error handling"""
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
        except Exception as e:
            print(f"Error initializing LED strip: {e}")
            # Wait and retry
            time.sleep(1)
            self.init_strip()

    def on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection with error checking"""
        connection_codes = {
            0: "Connected successfully",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized",
        }
        print(
            f"MQTT connection result: {connection_codes.get(rc, f'Unknown error ({rc})')}"
        )

        if rc == 0:
            self.is_connected = True
            print("Subscribing to led/pixels")
            client.subscribe("led/pixels")
        else:
            self.is_connected = False
            print("Connection failed")

    def on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        self.is_connected = False
        if rc != 0:
            print(f"Unexpected MQTT disconnection (code {rc}). Reconnecting...")
        else:
            print("MQTT disconnected cleanly")

    def connect_mqtt(self):
        """Attempt to connect to MQTT broker with retry logic"""
        while not self.is_connected:
            try:
                # Create a fresh client for each attempt
                client_id = f"led_controller_{int(time.time())}"
                print(f"Creating new client with ID: {client_id}")

                self.mqtt_client = mqtt.Client(client_id=client_id)
                self.mqtt_client.on_connect = self.on_connect
                self.mqtt_client.on_message = self.on_message
                self.mqtt_client.on_disconnect = self.on_disconnect

                if self.mqtt_user and self.mqtt_password:
                    print(f"Setting up authentication for user: {self.mqtt_user}")
                    self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

                # Start the network loop
                self.mqtt_client.loop_start()

                # Attempt connection
                print(f"Connecting to {self.mqtt_host}:{self.mqtt_port}...")
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)

                # Wait for callback
                timeout = 5
                while timeout > 0 and not self.is_connected:
                    time.sleep(0.1)
                    timeout -= 0.1

                if self.is_connected:
                    print("Successfully connected to MQTT broker")
                    return True
                else:
                    print("Connection timeout - cleaning up")
                    self.mqtt_client.loop_stop()
                    self.mqtt_client = None

            except Exception as e:
                print(f"Connection error: {str(e)}")
                if self.mqtt_client:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client = None

            print("Retrying in 5 seconds...")
            time.sleep(5)
        return False

    def connect_zmq(self):
        """Connect to ZMQ server for frame data"""
        try:
            zmq_address = f"tcp://{self.zmq_host}:{self.zmq_port}"
            print(f"Connecting to ZMQ server at {zmq_address}")
            self.frame_sub_socket.connect(zmq_address)
            return True
        except Exception as e:
            print(f"Error connecting to ZMQ server: {e}")
            return False

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages with error checking"""
        try:
            data = json.loads(msg.payload.decode())

            # Handle command messages
            if isinstance(data, dict) and "command" in data:
                if data["command"] == "set_pixels":
                    pixels = data.get("pixels", [])
                    for pixel in pixels:
                        index = pixel.get("index", 0)
                        if 0 <= index < LED_COUNT:
                            r = max(0, min(255, pixel.get("r", 0)))
                            g = max(0, min(255, pixel.get("g", 0)))
                            b = max(0, min(255, pixel.get("b", 0)))
                            self.frame_buffer[index] = (r, g, b)
                    self.needs_update = True
                elif data["command"] == "clear":
                    self.frame_buffer = [(0, 0, 0)] * LED_COUNT
                    self.needs_update = True
            # Handle direct pixel data (legacy format)
            elif isinstance(data, list):
                for pixel in data:
                    index = pixel.get("index", 0)
                    if 0 <= index < LED_COUNT:
                        r = max(0, min(255, pixel.get("r", 0)))
                        g = max(0, min(255, pixel.get("g", 0)))
                        b = max(0, min(255, pixel.get("b", 0)))
                        self.frame_buffer[index] = (r, g, b)
                self.needs_update = True

        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
            print(f"Message payload: {msg.payload}")

    def update_strip(self):
        """Update LED strip with error handling and recovery"""
        if not self.needs_update:
            return

        try:
            for i, (r, g, b) in enumerate(self.frame_buffer):
                self.strip.setPixelColor(i, Color(r, g, b))
            self.strip.show()
            self.needs_update = False
            self.consecutive_errors = 0
            self.last_update_time = time.time()
        except Exception as e:
            print(f"Error updating LED strip: {e}")
            self.consecutive_errors += 1

            # If too many errors, try to reinitialize
            if self.consecutive_errors >= self.max_consecutive_errors:
                print("Too many consecutive errors, reinitializing strip...")
                self.init_strip()
                self.consecutive_errors = 0

            # If it's been a while since the last error, reset the count
            if time.time() - self.last_update_time > self.error_reset_interval:
                self.consecutive_errors = 0

    def clear_strip(self):
        """Turn off all LEDs"""
        for i in range(LED_COUNT):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()

    def handle_connection_error(self):
        """Handle ZMQ connection error with reconnection attempts"""
        self.consecutive_errors += 1
        if self.consecutive_errors <= self.max_consecutive_errors:
            print(
                f"Connection lost. Attempt {self.consecutive_errors}/{self.max_consecutive_errors}"
            )

            # Clear LEDs while disconnected
            self.clear_strip()

            # Close existing socket
            self.frame_sub_socket.close(linger=0)
            time.sleep(0.1)  # Give socket time to close

            # Create new socket
            self.frame_sub_socket = self.zmq_context.socket(zmq.SUB)
            self.frame_sub_socket.setsockopt(zmq.LINGER, 0)
            self.frame_sub_socket.setsockopt(zmq.RCVHWM, 2)
            self.frame_sub_socket.setsockopt_string(zmq.SUBSCRIBE, "frame")

            # Try to reconnect
            try:
                zmq_address = f"tcp://{self.zmq_host}:{self.zmq_port}"
                print(f"Attempting to reconnect to {zmq_address}")
                self.frame_sub_socket.connect(zmq_address)
                self.consecutive_errors = 0  # Reset on successful connection
                time.sleep(0.1)  # Give connection time to establish
                return True
            except Exception as e:
                print(f"Reconnection failed: {e}")
                time.sleep(5)  # Wait before retry
                return False
        else:
            print("Max reconnection attempts reached")
            return False

    def run(self):
        """Main run loop with frame display"""
        try:
            # Initial connections
            if not self.connect_mqtt():
                print("Failed to establish initial MQTT connection")
                return

            if not self.connect_zmq():
                print("Failed to establish ZMQ connection")
                return

            # Update Home Assistant status
            self.mqtt_client.publish("led/status/led_controller", "online", retain=True)

            # Performance tracking
            last_fps_print = time.time()
            frame_count = 0
            frame_times = []
            last_frame_time = time.time()

            # Main loop
            while True:
                try:
                    # Check for new frame
                    try:
                        if self.frame_sub_socket.poll(timeout=100):  # 100ms timeout
                            topic, frame_data = self.frame_sub_socket.recv_multipart(
                                flags=zmq.NOBLOCK
                            )

                            # Update LED strip
                            frame_start = time.time()
                            for i in range(LED_COUNT):
                                idx = i * 3
                                if idx + 2 < len(frame_data):
                                    r = frame_data[idx]
                                    g = frame_data[idx + 1]
                                    b = frame_data[idx + 2]
                                    self.strip.setPixelColor(i, Color(r, g, b))

                            self.strip.show()
                            last_frame_time = time.time()

                            # Performance tracking
                            frame_time = last_frame_time - frame_start
                            frame_times.append(frame_time)
                            if len(frame_times) > 100:
                                frame_times.pop(0)
                            frame_count += 1

                            # Print FPS every second
                            current_time = time.time()
                            if current_time - last_fps_print >= 1.0:
                                if frame_count > 0 and len(frame_times) > 0:
                                    avg_frame_time = sum(frame_times) / len(frame_times)
                                    fps = frame_count / (current_time - last_fps_print)
                                    print(
                                        f"LED FPS: {fps:.1f}, Update time: {avg_frame_time * 1000:.1f}ms"
                                    )
                                frame_count = 0
                                last_fps_print = current_time

                            # Reset error counter on successful frame
                            self.consecutive_errors = 0

                    except zmq.Again:
                        continue

                    # Check for timeout
                    if time.time() - last_frame_time > 5.0:  # 5 second timeout
                        print("Frame timeout - server may be down")
                        if not self.handle_connection_error():
                            break
                        last_frame_time = (
                            time.time()
                        )  # Reset timer after reconnect attempt

                except Exception as e:
                    print(f"Error updating frame: {e}")
                    if not self.handle_connection_error():
                        break

                time.sleep(0.001)  # Small sleep to prevent tight loop

        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
        finally:
            # Clean shutdown
            print("Cleaning up...")

            try:
                self.mqtt_client.publish(
                    "led/status/led_controller", "offline", retain=True
                )
                time.sleep(0.1)
            except:
                pass

            # Stop MQTT
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

            # Clean up ZMQ
            try:
                self.frame_sub_socket.close(linger=0)
                self.zmq_context.term()
            except:
                pass

            # Turn off LEDs
            print("Turning off LEDs...")
            self.clear_strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LED Controller")
    parser.add_argument(
        "--mqtt-host",
        default=os.getenv("MQTT_BROKER"),
        help="MQTT broker hostname or IP",
    )
    parser.add_argument(
        "--zmq-host",
        default=os.getenv("ZMQ_HOST"),
        help="ZMQ broker hostname or IP",
    )
    args = parser.parse_args()

    controller = LEDController(mqtt_host=args.mqtt_host, zmq_host=args.zmq_host)
    controller.run()
