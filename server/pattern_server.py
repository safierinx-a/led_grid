#!/usr/bin/env python3

"""
LED Grid Pattern Server

This script starts the pattern server, which generates patterns and sends frame data
to the LED controller via ZMQ.
"""

import os
import sys
import time
import threading
from dotenv import load_dotenv

# Import server components
from server.config.grid_config import DEFAULT_CONFIG
from server.core.server import LEDServer

# Debug: Print the current directory and Python path
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

# Import all patterns to register them
print("\n=== Importing Pattern Modules ===")
try:
    import server.patterns.test_pattern

    print("✓ Imported test_pattern pattern")
except Exception as e:
    print(f"✗ Failed to import test_pattern pattern: {e}")

try:
    import server.patterns.plasma

    print("✓ Imported plasma pattern")
except Exception as e:
    print(f"✗ Failed to import plasma pattern: {e}")

try:
    import server.patterns.rainbow_wave

    print("✓ Imported rainbow_wave pattern")
except Exception as e:
    print(f"✗ Failed to import rainbow_wave pattern: {e}")

try:
    import server.patterns.fire

    print("✓ Imported fire pattern")
except Exception as e:
    print(f"✗ Failed to import fire pattern: {e}")

try:
    import server.patterns.matrix_rain

    print("✓ Imported matrix_rain pattern")
except Exception as e:
    print(f"✗ Failed to import matrix_rain pattern: {e}")

try:
    import server.patterns.game_of_life

    print("✓ Imported game_of_life pattern")
except Exception as e:
    print(f"✗ Failed to import game_of_life pattern: {e}")

try:
    import server.patterns.starfield

    print("✓ Imported starfield pattern")
except Exception as e:
    print(f"✗ Failed to import starfield pattern: {e}")

try:
    import server.patterns.particle_system

    print("✓ Imported particle_system pattern")
except Exception as e:
    print(f"✗ Failed to import particle_system pattern: {e}")

try:
    import server.patterns.waves

    print("✓ Imported waves pattern")
except Exception as e:
    print(f"✗ Failed to import waves pattern: {e}")

try:
    import server.patterns.polyhedra3d

    print("✓ Imported polyhedra3d pattern")
except Exception as e:
    print(f"✗ Failed to import polyhedra3d pattern: {e}")

try:
    import server.patterns.color_cycle

    print("✓ Imported color_cycle pattern")
except Exception as e:
    print(f"✗ Failed to import color_cycle pattern: {e}")

try:
    import server.patterns.emoji

    print("✓ Imported emoji pattern")
except Exception as e:
    print(f"✗ Failed to import emoji pattern: {e}")

try:
    import server.patterns.perlin_landscape

    print("✓ Imported perlin_landscape pattern")
except Exception as e:
    print(f"✗ Failed to import perlin_landscape pattern: {e}")

try:
    import server.patterns.sine_wave

    print("✓ Imported sine_wave pattern")
except Exception as e:
    print(f"✗ Failed to import sine_wave pattern: {e}")

try:
    import server.patterns.swarm_system

    print("✓ Imported swarm_system pattern")
except Exception as e:
    print(f"✗ Failed to import swarm_system pattern: {e}")

try:
    import server.patterns.generative

    print("✓ Imported generative pattern")
except Exception as e:
    print(f"✗ Failed to import generative pattern: {e}")

# Import all modifiers to register them
print("\n=== Importing Modifier Modules ===")
try:
    import server.modifiers.basic

    print("✓ Imported basic modifiers")
except Exception as e:
    print(f"✗ Failed to import basic modifiers: {e}")

# Debug: Check the pattern registry
from server.patterns.base import PatternRegistry

print(f"\n=== Pattern Registry Status ===")
print(f"Registered patterns: {len(PatternRegistry._patterns)}")
for name in PatternRegistry._patterns:
    print(f"  - {name}")


def main():
    """Main entry point for the pattern server"""
    # Load environment variables
    load_dotenv()

    print("\n=== LED Grid Pattern Server ===\n")

    # Create and start the server
    server = LEDServer(DEFAULT_CONFIG)

    # Start web server in a separate thread
    from server.web import create_app, socketio

    app = create_app(server)

    web_port = int(os.getenv("WEB_PORT", "5000"))
    web_thread = threading.Thread(
        target=lambda: socketio.run(
            app,
            host="0.0.0.0",
            port=web_port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    )
    web_thread.daemon = True
    web_thread.start()
    print(f"\nWeb dashboard started on port {web_port}")
    print(f"Access the dashboard at http://localhost:{web_port}")

    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        server.stop()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
