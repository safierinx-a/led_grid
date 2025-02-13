#!/usr/bin/env python3

import time
import json
import importlib
import pkgutil
import threading
from typing import Dict, Any, Optional, List, Tuple
import paho.mqtt.client as mqtt
import math
import signal

from server.config.grid_config import GridConfig, DEFAULT_CONFIG
from server.patterns.base import Pattern, PatternRegistry
from server.modifiers.base import Modifier, ModifierRegistry


class PatternServer:
    def __init__(self, grid_config: GridConfig = DEFAULT_CONFIG):
        self.grid_config = grid_config
        self.mqtt_client = mqtt.Client()

        # Current pattern state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}

        # Modifier chain
        self.modifiers: List[Tuple[Modifier, Dict[str, Any]]] = []

        # Thread control
        self.is_running = False
        self.update_thread = None

        # Load all patterns and modifiers
        self._load_patterns()
        self._load_modifiers()

    def _load_patterns(self):
        """Dynamically load all pattern modules"""
        import server.patterns as patterns

        package = patterns

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"server.patterns.{name}")

    def _load_modifiers(self):
        """Dynamically load all modifier modules"""
        import server.modifiers as modifiers

        package = modifiers

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"server.modifiers.{name}")

    def connect(self):
        """Connect to MQTT broker"""
        self.mqtt_client.connect("localhost", 1883, 60)
        self.mqtt_client.loop_start()

    def set_pattern(self, pattern_name: str, params: Dict[str, Any] = None):
        """Set the current pattern"""
        # Clear the current pattern by sending a clear command
        self.mqtt_client.publish("led/pixels", json.dumps({"command": "clear"}))

        # Set the new pattern
        pattern_class = PatternRegistry.get_pattern(pattern_name)
        if pattern_class:
            self.current_pattern = pattern_class(self.grid_config)
            self.current_params = params or {}
            print(f"Set pattern to {pattern_name} with params {params}")
        else:
            print(f"Pattern {pattern_name} not found")

    def add_modifier(self, modifier_name: str, params: Dict[str, Any] = None):
        """Add a modifier to the chain"""
        modifier_class = ModifierRegistry.get_modifier(modifier_name)
        if modifier_class:
            modifier = modifier_class(self.grid_config)
            self.modifiers.append((modifier, params or {}))
            print(f"Added modifier {modifier_name} with params {params}")
        else:
            print(f"Modifier {modifier_name} not found")

    def remove_modifier(self, index: int):
        """Remove a modifier from the chain"""
        if 0 <= index < len(self.modifiers):
            modifier, params = self.modifiers.pop(index)
            print(f"Removed modifier at index {index}")

    def clear_modifiers(self):
        """Clear all modifiers"""
        self.modifiers = []
        print("Cleared all modifiers")

    def update_pattern_params(self, params: Dict[str, Any]):
        """Update current pattern parameters"""
        if self.current_pattern:
            self.current_params.update(params)

    def update_modifier_params(self, index: int, params: Dict[str, Any]):
        """Update modifier parameters"""
        if 0 <= index < len(self.modifiers):
            modifier, current_params = self.modifiers[index]
            current_params.update(params)
            self.modifiers[index] = (modifier, current_params)

    def send_frame(self, pixels: list):
        """Send frame data to LED controller"""
        message = {"command": "set_pixels", "pixels": pixels}
        self.mqtt_client.publish("led/pixels", json.dumps(message))

    def _update_loop(self):
        """Main update loop running in background thread"""
        while self.is_running:
            try:
                if self.current_pattern:
                    # Generate base frame
                    frame = self.current_pattern.generate_frame(self.current_params)

                    # Apply modifier chain
                    for modifier, params in self.modifiers:
                        frame = modifier.apply(frame, params)

                    # Send final frame
                    self.send_frame(frame)

                time.sleep(0.05)  # 20fps

            except Exception as e:
                print(f"Error in update loop: {e}")
                time.sleep(0.1)  # Brief pause on error

    def start(self):
        """Start the pattern server"""
        if not self.is_running:
            self.is_running = True
            self.update_thread = threading.Thread(target=self._update_loop)
            self.update_thread.daemon = True
            self.update_thread.start()

    def stop(self):
        """Stop the pattern server"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
        self.clear_modifiers()
        self.mqtt_client.publish("led/pixels", json.dumps({"command": "clear"}))
        self.mqtt_client.loop_stop()

    def list_patterns(self):
        """List all available patterns"""
        return PatternRegistry.list_patterns()

    def list_modifiers(self):
        """List all available modifiers"""
        return ModifierRegistry.list_modifiers()


if __name__ == "__main__":
    import time

    # Create and start server
    server = PatternServer()
    server.connect()
    server.start()

    # Set up MQTT command handlers
    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic == "led/command/pattern":
                server.set_pattern(data["name"], data.get("params", {}))

            elif topic == "led/command/params":
                server.update_pattern_params(data["params"])

            elif topic == "led/command/modifier/add":
                server.add_modifier(data["name"], data.get("params", {}))

            elif topic == "led/command/modifier/remove":
                server.remove_modifier(data["index"])

            elif topic == "led/command/modifier/clear":
                server.clear_modifiers()

            elif topic == "led/command/modifier/params":
                server.update_modifier_params(data["index"], data["params"])

            elif topic == "led/command/list":
                # Send back pattern and modifier information
                response = {
                    "patterns": server.list_patterns(),
                    "modifiers": server.list_modifiers(),
                    "current_pattern": server.current_pattern.definition().name
                    if server.current_pattern
                    else None,
                    "current_modifiers": [
                        (m.definition().name, p) for m, p in server.modifiers
                    ],
                }
                server.mqtt_client.publish("led/status/list", json.dumps(response))

            elif topic == "led/command/stop":
                server.set_pattern(None)

            elif topic == "led/command/clear":
                server.mqtt_client.publish(
                    "led/pixels", json.dumps({"command": "clear"})
                )

        except Exception as e:
            print(f"Error handling command: {e}")

    # Subscribe to command topics
    server.mqtt_client.on_message = on_message
    server.mqtt_client.subscribe("led/command/#")

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print("\nShutting down...")
        server.stop()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
