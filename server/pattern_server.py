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
import traceback
from dotenv import load_dotenv

# Import server components
from server.config.grid_config import DEFAULT_CONFIG
from server.core.server import LEDServer
from server.patterns.base import PatternRegistry, Pattern

# Debug: Print the current directory and Python path
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

# Import all patterns to register them
print("\n=== Importing Pattern Modules ===")


# Function to import a pattern module with detailed error reporting
def import_pattern_module(module_name):
    try:
        module = __import__(f"server.patterns.{module_name}", fromlist=["*"])
        print(f"✓ Imported {module_name} pattern")

        # Check if the module contains any classes that are registered with PatternRegistry
        module_has_registered_patterns = False
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                hasattr(attr, "__module__")
                and attr.__module__ == f"server.patterns.{module_name}"
                and isinstance(attr, type)  # Check if it's a class
                and issubclass(attr, Pattern)  # Check if it's a Pattern subclass
                and attr != Pattern  # Exclude the base Pattern class
            ):
                print(f"  - Found Pattern subclass: {attr.__name__}")

                # Check if this class is in the PatternRegistry
                if hasattr(PatternRegistry, "_patterns") and PatternRegistry._patterns:
                    for (
                        pattern_name,
                        pattern_class,
                    ) in PatternRegistry._patterns.items():
                        if pattern_class == attr:
                            module_has_registered_patterns = True
                            print(
                                f"  - Confirmed registered in PatternRegistry: {pattern_name}"
                            )

                # Check if it has a definition method
                if hasattr(attr, "definition"):
                    try:
                        definition = attr.definition()
                        print(f"  - Pattern definition: {definition.name}")
                    except Exception as e:
                        print(f"  - Error getting pattern definition: {e}")
                else:
                    print(
                        f"  - Warning: Pattern class {attr.__name__} has no definition method"
                    )

        if not module_has_registered_patterns:
            print(
                f"  ! Warning: Module {module_name} imported but no patterns were registered"
            )
            print(
                f"  ! Check that pattern classes have the @PatternRegistry.register decorator"
            )

        return True
    except Exception as e:
        print(f"✗ Failed to import {module_name} pattern: {e}")
        print(f"Traceback:")
        traceback.print_exc()
        return False


# Initialize the PatternRegistry if needed
if not hasattr(PatternRegistry, "_patterns") or PatternRegistry._patterns is None:
    print("Initializing PatternRegistry._patterns as it was not initialized")
    PatternRegistry._patterns = {}

# Import patterns
patterns_to_import = [
    "test_pattern",  # Import test pattern first
    "plasma",
    "rainbow_wave",
    "fire",
    "matrix_rain",
    "game_of_life",
    "starfield",
    "particle_system",
    "waves",
    "polyhedra3d",
    "color_cycle",
    "emoji",
    "perlin_landscape",
    "sine_wave",
    "swarm_system",
    "generative",
]

successful_imports = 0
for pattern_name in patterns_to_import:
    if import_pattern_module(pattern_name):
        successful_imports += 1

print(f"\n=== Pattern Import Summary ===")
print(
    f"Successfully imported {successful_imports} out of {len(patterns_to_import)} pattern modules"
)

# Import modifiers
print("\n=== Importing Modifier Modules ===")
try:
    import server.modifiers.basic

    print("✓ Imported basic modifiers")
except Exception as e:
    print(f"✗ Failed to import basic modifiers: {e}")
    traceback.print_exc()

# Print the contents of the pattern registry
print("\n=== Pattern Registry Contents ===")
if not hasattr(PatternRegistry, "_patterns") or not PatternRegistry._patterns:
    print("! WARNING: Pattern registry is empty!")
    print("! No patterns will be available in the UI.")
    print(
        "! Check that pattern modules are being imported correctly and patterns are registered."
    )

    # Try to diagnose the issue
    print("\n=== Pattern Registry Diagnosis ===")
    if not hasattr(PatternRegistry, "_patterns"):
        print("ERROR: PatternRegistry._patterns attribute not found!")
        print("This suggests a serious issue with the PatternRegistry class.")
        print("Initializing it now as an empty dictionary.")
        PatternRegistry._patterns = {}
    elif PatternRegistry._patterns is None:
        print("ERROR: PatternRegistry._patterns is None!")
        print("The registry dictionary has not been initialized properly.")
        print("Initializing it now as an empty dictionary.")
        PatternRegistry._patterns = {}
else:
    print(f"Found {len(PatternRegistry._patterns)} registered patterns:")
    for pattern_name, pattern_class in PatternRegistry._patterns.items():
        try:
            definition = pattern_class.definition()
            print(
                f"  - {pattern_name}: {definition.description} (Category: {definition.category})"
            )
        except Exception as e:
            print(f"  - {pattern_name}: Error getting definition: {e}")


# Create and run the server
def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()

    # Create server
    server = LEDServer(DEFAULT_CONFIG)

    # Print server configuration
    print("\n=== Server Configuration ===")
    print(f"Grid dimensions: {server.grid_config.width}x{server.grid_config.height}")
    print(f"Pattern manager: {server.pattern_manager}")
    print(
        f"Available patterns: {[p.definition().name for p in server.pattern_manager.patterns]}"
    )

    # Run server
    server.run()


if __name__ == "__main__":
    main()
