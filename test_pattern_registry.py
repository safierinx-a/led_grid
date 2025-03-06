#!/usr/bin/env python3

"""
Test Pattern Registry

This script tests if patterns are properly registered in the PatternRegistry.
"""

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

# Import the registry
from server.patterns.base import PatternRegistry


def main():
    """Main entry point for the test script"""
    # Get all registered patterns
    pattern_defs = PatternRegistry.list_patterns()

    # Extract pattern names
    pattern_names = [p.name for p in pattern_defs]

    print(f"Found {len(pattern_names)} registered patterns:")
    for name in sorted(pattern_names):
        print(f"- {name}")

    # Check if plasma is registered
    if "plasma" in pattern_names:
        print("\nPlasma pattern is registered correctly!")
    else:
        print("\nError: Plasma pattern is NOT registered!")
        print("Available patterns:", pattern_names)


if __name__ == "__main__":
    main()
