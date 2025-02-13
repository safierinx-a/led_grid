#!/usr/bin/env python3

import time
import json
import paho.mqtt.client as mqtt
from rpi_ws281x import PixelStrip, Color

# LED strip configuration
LED_COUNT = 600  # Total number of LEDs (24 strips * 25 LEDs)
LED_PIN = 18  # GPIO pin connected to the pixels
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal
LED_CHANNEL = 0  # PWM channel to use


class LEDController:
    def __init__(self):
        # Create NeoPixel object with appropriate configuration
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

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        # Frame buffer to store current state
        self.frame_buffer = [(0, 0, 0)] * LED_COUNT
        self.needs_update = False

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        # Subscribe to pixel commands
        client.subscribe("led/pixels")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            command = data.get("command")

            if command == "set_pixels":
                pixels = data.get("pixels", [])
                for pixel in pixels:
                    index = pixel.get("index")
                    r = pixel.get("r", 0)
                    g = pixel.get("g", 0)
                    b = pixel.get("b", 0)
                    if 0 <= index < LED_COUNT:
                        self.frame_buffer[index] = (r, g, b)
                self.needs_update = True

            elif command == "clear":
                self.frame_buffer = [(0, 0, 0)] * LED_COUNT
                self.needs_update = True

        except json.JSONDecodeError:
            print("Error decoding message")

    def update_strip(self):
        """Update the LED strip with current frame buffer"""
        if self.needs_update:
            for i, (r, g, b) in enumerate(self.frame_buffer):
                self.strip.setPixelColor(i, Color(r, g, b))
            self.strip.show()
            self.needs_update = False

    def run(self):
        """Main run loop"""
        # Connect to MQTT broker
        self.mqtt_client.connect("localhost", 1883, 60)

        # Start MQTT loop in background thread
        self.mqtt_client.loop_start()

        try:
            while True:
                self.update_strip()
                time.sleep(0.05)  # Small delay to prevent overwhelming the strip

        except KeyboardInterrupt:
            print("Shutting down...")
            # Clear on shutdown
            for i in range(self.strip.numPixels()):
                self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()
            self.mqtt_client.loop_stop()


if __name__ == "__main__":
    controller = LEDController()
    controller.run()
