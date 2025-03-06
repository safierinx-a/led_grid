#!/usr/bin/env python3

"""
LED Grid Pattern Server

This script starts the pattern server, which generates patterns and sends frame data
to the LED controller via ZMQ.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Import server components
from server.config.grid_config import DEFAULT_CONFIG
from server.core.server import LEDServer

# Import all patterns to register them
import server.patterns.plasma
import server.patterns.rainbow_wave
import server.patterns.fire
import server.patterns.matrix_rain
import server.patterns.game_of_life
import server.patterns.starfield
import server.patterns.particle_system
import server.patterns.waves
import server.patterns.polyhedra3d
import server.patterns.color_cycle
import server.patterns.emoji
import server.patterns.perlin_landscape
import server.patterns.sine_wave
import server.patterns.swarm_system
import server.patterns.generative

# Import all modifiers to register them
import server.modifiers.basic


def main():
    """Main entry point for the pattern server"""
    # Load environment variables
    load_dotenv()

    print("\n=== LED Grid Pattern Server ===\n")

    # Create and start the server
    server = LEDServer(DEFAULT_CONFIG)

    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        server.stop()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
