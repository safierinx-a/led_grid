#!/usr/bin/env python3

import time
import math
import json
from server.pattern_server import PatternServer


def run_demo():
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


if __name__ == "__main__":
    run_demo()
