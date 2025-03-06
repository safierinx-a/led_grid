#!/usr/bin/env python3

from server.patterns.base import PatternRegistry
from server.config.grid_config import DEFAULT_CONFIG
import server.patterns  # This will import and register all patterns


def main():
    # Get all registered patterns
    pattern_defs = PatternRegistry.list_patterns()
    pattern_names = [p.name for p in pattern_defs]

    print(f"Found {len(pattern_names)} registered patterns:")
    for name in sorted(pattern_names):
        print(f"- {name}")

    # Check if plasma is registered
    if "plasma" in pattern_names:
        print("\nPlasma pattern is registered correctly!")

        # Get the plasma pattern class
        plasma_class = PatternRegistry.get_pattern("plasma")
        if plasma_class:
            # Create an instance
            plasma_instance = plasma_class(DEFAULT_CONFIG)
            print(f"Successfully created plasma pattern instance: {plasma_instance}")
        else:
            print("Error: Could not get plasma pattern class")
    else:
        print("\nError: Plasma pattern is NOT registered!")
        print("Available patterns:", pattern_names)


if __name__ == "__main__":
    main()
