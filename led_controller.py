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

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        # Frame buffer to store current state
        self.frame_buffer = [(0, 0, 0)] * LED_COUNT
        self.needs_update = False
        self.last_update_time = time.time()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.error_reset_interval = 60  # Reset error count after 60 seconds

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
            print("Subscribing to led/pixels")
            client.subscribe("led/pixels")
        else:
            print("Connection failed, retrying...")
            time.sleep(5)
            self.connect_mqtt()

    def connect_mqtt(self):
        """Attempt to connect to MQTT broker with retry logic"""
        try:
            print(
                f"Attempting to connect to MQTT broker at {self.mqtt_host}:{self.mqtt_port}"
            )
            if self.mqtt_user and self.mqtt_password:
                print(f"Using authentication with username: {self.mqtt_user}")
                self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            print("MQTT connection successful")
        except Exception as e:
            print(f"Error connecting to MQTT: {str(e)}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
            self.connect_mqtt()

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
        while True:
            try:
                self.mqtt_client.loop_start()
                while True:
                    self.update_strip()
                    time.sleep(0.001)  # Small delay to prevent CPU overload
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
