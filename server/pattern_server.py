#!/usr/bin/env python3

import time
import json
import importlib
import pkgutil
import threading
from typing import Dict, Any, Optional, List, Tuple
import paho.mqtt.client as mqtt
import math

from config.grid_config import GridConfig, DEFAULT_CONFIG
from patterns.base import Pattern, PatternRegistry
from modifiers.base import Modifier, ModifierRegistry


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
        import patterns

        package = patterns

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"patterns.{name}")

    def _load_modifiers(self):
        """Dynamically load all modifier modules"""
        import modifiers

        package = modifiers

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"modifiers.{name}")

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

    # Example usage with modifiers
    server = PatternServer()
    server.connect()

    try:
        # Demo 1: Rainbow Wave with Dynamic Effects
        print("\n=== Demo 1: Rainbow Wave with Dynamic Effects ===")
        server.set_pattern(
            "rainbow_wave", {"speed": 1.0, "saturation": 1.0, "direction": "horizontal"}
        )
        server.add_modifier("mirror", {"axis": "vertical"})

        # Run for 5 seconds
        start_time = time.time()
        while time.time() - start_time < 5:
            # Dynamically adjust brightness based on time
            brightness = 0.3 + (math.sin(time.time() * 2) + 1) * 0.35
            server.update_modifier_params(0, {"level": brightness})
            server.run()

        # Demo 2: Matrix Rain with Tiling and Strobing
        print("\n=== Demo 2: Matrix Rain with Tiling and Strobing ===")
        server.clear_modifiers()
        server.set_pattern("matrix_rain", {"speed": 0.5, "density": 0.2})
        server.add_modifier("tile", {"x_tiles": 2, "y_tiles": 2})
        server.add_modifier("strobe", {"frequency": 2.0, "duty_cycle": 0.8})

        # Run for 8 seconds
        start_time = time.time()
        while time.time() - start_time < 8:
            # Gradually increase strobe frequency
            freq = 2.0 + (time.time() - start_time) * 0.5
            server.update_modifier_params(1, {"frequency": freq})
            server.run()

        # Demo 3: Particle System with Complex Modifiers
        print("\n=== Demo 3: Particle System with Complex Modifiers ===")
        server.clear_modifiers()
        server.set_pattern(
            "particle_system", {"num_particles": 50, "speed": 1.0, "decay": 0.98}
        )
        server.add_modifier("mirror", {"axis": "both"})
        server.add_modifier("brightness", {"level": 0.8})

        # Run for 10 seconds
        start_time = time.time()
        while time.time() - start_time < 10:
            # Oscillate particle count
            particles = 30 + int(math.sin(time.time()) * 20)
            server.update_pattern_params({"num_particles": particles})
            server.run()

        # Demo 4: Color Cycling Pattern with Spatial Effects
        print("\n=== Demo 4: Color Cycling with Spatial Effects ===")
        server.clear_modifiers()
        server.set_pattern("color_cycle", {"speed": 0.5, "saturation": 1.0})
        server.add_modifier("tile", {"x_tiles": 3, "y_tiles": 3})
        server.add_modifier("mirror", {"axis": "both"})

        # Run for 8 seconds
        start_time = time.time()
        while time.time() - start_time < 8:
            # Rotate through different tile configurations
            tiles = 2 + int((time.time() - start_time) / 2) % 3
            server.update_modifier_params(0, {"x_tiles": tiles, "y_tiles": tiles})
            server.run()

        # Final Demo: Combined Effects
        print("\n=== Final Demo: Combined Effects ===")
        server.clear_modifiers()
        server.set_pattern("rainbow_wave", {"speed": 2.0, "direction": "diagonal"})
        server.add_modifier("mirror", {"axis": "both"})
        server.add_modifier("brightness", {"level": 0.7})
        server.add_modifier("strobe", {"frequency": 4.0, "duty_cycle": 0.9})

        # Run for 10 seconds
        start_time = time.time()
        while time.time() - start_time < 10:
            # Create a pulsing effect
            phase = (time.time() - start_time) / 10
            brightness = 0.4 + (math.sin(phase * math.pi * 2) + 1) * 0.3
            server.update_modifier_params(1, {"level": brightness})
            server.run()

    except KeyboardInterrupt:
        print("\nDemo stopped by user")
        server.clear_modifiers()
        server.mqtt_client.publish("led/pixels", json.dumps({"command": "clear"}))
