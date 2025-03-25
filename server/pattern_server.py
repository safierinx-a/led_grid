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
import ssl

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
        print(f"\nLoading pattern: {module_name}")
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
                print(f"  - Found pattern class: {attr.__name__}")

                try:
                    # Create instance with error handling
                    print(f"  - Creating instance of {attr.__name__}")
                    instance = attr(DEFAULT_CONFIG)
                    print(f"  - Successfully created instance")

                    # Add to patterns list
                    if hasattr(PatternRegistry, "_patterns"):
                        PatternRegistry._patterns[module_name] = attr
                        print(f"  - Added to patterns list")
                        module_has_registered_patterns = True
                        print(f"Successfully loaded pattern: {module_name}")
                    else:
                        print(f"  ! Warning: PatternRegistry._patterns not initialized")
                except Exception as e:
                    print(f"  ! Error creating pattern instance: {e}")
                    print("  ! Traceback:")
                    traceback.print_exc()
                    continue

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

# Import patterns in smaller batches to avoid memory issues
pattern_batches = [
    ["test_pattern"],  # Test pattern first
    ["plasma", "rainbow_wave"],  # Simple patterns
    ["fire", "matrix_rain"],  # Complex patterns
    ["game_of_life", "starfield"],  # More complex patterns
    ["particle_system", "waves"],  # Physics-based patterns
    ["polyhedra3d", "color_cycle"],  # 3D patterns
    ["emoji", "perlin_landscape"],  # Image-based patterns
    ["sine_wave", "swarm_system"],  # Wave patterns
    ["generative"],  # Most complex patterns
]

successful_imports = 0
total_patterns = sum(len(batch) for batch in pattern_batches)

for batch in pattern_batches:
    print(f"\n=== Loading Pattern Batch ===")
    for pattern_name in batch:
        if import_pattern_module(pattern_name):
            successful_imports += 1
    # Add a small delay between batches to allow memory to stabilize
    time.sleep(0.5)

print(f"\n=== Pattern Import Summary ===")
print(
    f"Successfully imported {successful_imports} out of {total_patterns} pattern modules"
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
    try:
        # Load environment variables
        load_dotenv()

        # Create MQTT config from environment variables
        mqtt_config = {
            "host": os.getenv("MQTT_BROKER", "localhost"),
            "port": int(os.getenv("MQTT_PORT", "1883")),
            "username": os.getenv("MQTT_USER"),
            "password": os.getenv("MQTT_PASSWORD"),
        }

        # Create server with both configs
        server = LEDServer(DEFAULT_CONFIG, mqtt_config)

        # Start server
        if not server.start():
            print("Failed to start server")
            return 1

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.stop()
            return 0

    except Exception as e:
        print(f"Error in main: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
