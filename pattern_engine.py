#!/usr/bin/env python3

import time
import json
import math
import random
import paho.mqtt.client as mqtt


class PatternEngine:
    def __init__(self):
        self.mqtt_client = mqtt.Client()
        self.width = 25
        self.height = 24
        self.matrix_drops = []

    def connect(self):
        """Connect to MQTT broker"""
        self.mqtt_client.connect("localhost", 1883, 60)

    def xy_to_index(self, x, y):
        """Convert x,y coordinates to LED strip index, accounting for serpentine layout"""
        if y % 2 == 0:  # Even rows go left to right
            return y * 25 + x
        else:  # Odd rows go right to left
            return y * 25 + (24 - x)

    def send_pixels(self, pixels):
        """Send pixel updates to the controller"""
        message = {"command": "set_pixels", "pixels": pixels}
        self.mqtt_client.publish("led/pixels", json.dumps(message))

    def clear(self):
        """Send clear command to controller"""
        message = {"command": "clear"}
        self.mqtt_client.publish("led/pixels", json.dumps(message))

    def wheel(self, pos):
        """Generate rainbow colors across 0-255 positions."""
        pos = pos % 255
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    # Pattern Generators
    def rainbow_wave(self, step=0, speed=1.0):
        """Generate rainbow wave pattern"""
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                hue = (x + y + int(step)) % 255
                r, g, b = self.wheel(hue)
                pixels.append({"index": self.xy_to_index(x, y), "r": r, "g": g, "b": b})
        self.send_pixels(pixels)

    def solid_color(self, r, g, b):
        """Set solid color pattern"""
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                pixels.append({"index": self.xy_to_index(x, y), "r": r, "g": g, "b": b})
        self.send_pixels(pixels)

    def matrix_rain(self, speed=1.0, density=0.1):
        """Generate Matrix-style rain effect"""
        pixels = []

        # Update existing drops
        new_drops = []
        for drop in self.matrix_drops:
            x, y, intensity = drop
            if y < self.height:
                pixels.append(
                    {
                        "index": self.xy_to_index(x, int(y)),
                        "r": 0,
                        "g": int(intensity * 255),
                        "b": 0,
                    }
                )
                new_drops.append((x, y + speed, max(0, intensity - 0.1)))

        # Add new drops
        if random.random() < density:
            x = random.randint(0, self.width - 1)
            new_drops.append((x, 0, 1.0))

        self.matrix_drops = new_drops
        if pixels:
            self.send_pixels(pixels)

    def run_demo(self):
        """Run a demo sequence of patterns"""
        step = 0
        try:
            while True:
                # Rainbow wave for 10 seconds
                print("Running rainbow wave pattern...")
                start_time = time.time()
                while time.time() - start_time < 10:
                    self.rainbow_wave(step=step)
                    step += 1
                    time.sleep(0.05)

                # Solid red for 5 seconds
                print("Running solid red pattern...")
                self.solid_color(255, 0, 0)
                time.sleep(5)

                # Matrix rain for 10 seconds
                print("Running matrix rain pattern...")
                start_time = time.time()
                while time.time() - start_time < 10:
                    self.matrix_rain(speed=0.2, density=0.1)
                    time.sleep(0.05)

        except KeyboardInterrupt:
            print("Demo stopped.")
            self.clear()


if __name__ == "__main__":
    engine = PatternEngine()
    engine.connect()
    engine.run_demo()
