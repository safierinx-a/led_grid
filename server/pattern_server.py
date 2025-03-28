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

    # Start the web server in a separate thread
    web_thread = None
    try:
        from server.web import create_app, socketio

        print("\n=== Starting Web Server ===")
        app = create_app(server)

        # Get port from environment or use default
        port = int(os.environ.get("WEB_PORT", 5001))

        # Get SSL configuration from environment
        ssl_cert = os.environ.get("SSL_CERT")
        ssl_key = os.environ.get("SSL_KEY")
        use_https = (
            ssl_cert
            and ssl_key
            and os.path.exists(ssl_cert)
            and os.path.exists(ssl_key)
        )

        # Configure SSL context if using HTTPS
        ssl_context = None
        if use_https:
            print(f"HTTPS enabled with certificate: {ssl_cert}")
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(ssl_cert, ssl_key)
        else:
            print("HTTPS not enabled. Using HTTP only.")
            print("To enable HTTPS, set SSL_CERT and SSL_KEY environment variables.")

        # Define a function to run the web server
        def run_web_server():
            print(
                f"Starting {'HTTPS' if use_https else 'HTTP'} web server on port {port}..."
            )
            socketio.run(
                app,
                host="0.0.0.0",
                port=port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True,
                ssl_context=ssl_context,
            )

        # Start the web server in a separate thread
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        print("Web server thread started")
    except Exception as e:
        print(f"Error starting web server: {e}")
        traceback.print_exc()
        print("Continuing without web server...")

    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nReceived shutdown signal")
    finally:
        print("Shutting down...")
        server.stop()

        # Wait for web thread to terminate
        if web_thread and web_thread.is_alive():
            print("Waiting for web server to terminate...")
            web_thread.join(timeout=5)


if __name__ == "__main__":
    main()
