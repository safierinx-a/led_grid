#!/usr/bin/env python3

import time
import json
import paho.mqtt.client as mqtt
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


class LEDController:
    def __init__(self, mqtt_host=None):
        # Create NeoPixel object with appropriate configuration
        self.init_strip()

        # MQTT setup
        self.mqtt_host = mqtt_host or os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_user = os.getenv("MQTT_USER")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")

        print(f"MQTT Configuration:")
        print(f"Host: {self.mqtt_host}")
        print(f"Port: {self.mqtt_port}")
        print(f"User: {self.mqtt_user}")
        print(
            f"Password: {'*' * len(self.mqtt_password) if self.mqtt_password else 'None'}"
        )

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

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages with error checking"""
        try:
            data = json.loads(msg.payload.decode())
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

    def run(self):
        """Main run loop with error recovery"""
        try:
            # Initial connection
            if not self.connect_mqtt():
                print("Failed to establish initial MQTT connection")
                return

            # Main loop
            while True:
                if not self.is_connected:
                    print("MQTT connection lost, attempting to reconnect...")
                    if not self.connect_mqtt():
                        continue

                self.update_strip()
                time.sleep(0.001)  # Small delay to prevent CPU overload

        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            # Turn off all LEDs
            for i in range(LED_COUNT):
                self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()
        except Exception as e:
            print(f"Error in main loop: {e}")
            self.mqtt_client.loop_stop()
            time.sleep(1)
            print("Attempting to recover...")
            try:
                self.init_strip()
                self.connect_mqtt()
            except Exception as recovery_error:
                print(f"Recovery failed: {recovery_error}")
                time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LED Controller")
    parser.add_argument(
        "--mqtt-host",
        default=os.getenv("MQTT_BROKER"),
        help="MQTT broker hostname or IP",
    )
    args = parser.parse_args()

    controller = LEDController(mqtt_host=args.mqtt_host)
    controller.run()
