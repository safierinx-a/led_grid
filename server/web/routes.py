"""
Routes for the LED Grid web dashboard.

This module defines the API endpoints and WebSocket handlers for the LED Grid dashboard.
"""

from flask import jsonify, request, render_template
from flask_socketio import emit
from server.web import app, socketio, led_server
from datetime import datetime
import copy


@app.route("/")
def index():
    """Serve the main dashboard page"""
    return render_template("index.html")


@app.route("/health")
def health_check():
    """Health check endpoint for the LED Grid web server"""
    return jsonify({"status": "ok", "service": "led_grid_web", "version": "1.0.0"})


@app.route("/api/patterns", methods=["GET"])
def get_patterns():
    """Get list of available patterns"""
    print("\n=== API: Get Patterns Request ===")
    patterns = led_server.pattern_manager.patterns
    print(f"Number of patterns found: {len(patterns)}")

    pattern_data = []

    for pattern in patterns:
        try:
            definition = pattern.definition()
            print(f"Processing pattern: {definition.name}")
            pattern_data.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "category": definition.category,
                    "tags": definition.tags,
                    "parameters": [
                        {
                            "name": param.name,
                            "type": param.type.__name__,
                            "default": param.default,
                            "min_value": param.min_value,
                            "max_value": param.max_value,
                            "description": param.description,
                        }
                        for param in definition.parameters
                        if not param.name.startswith("_")  # Hide internal parameters
                    ],
                }
            )
        except Exception as e:
            print(f"Error processing pattern: {e}")
            import traceback

            traceback.print_exc()

    current_pattern_name = None
    if led_server.pattern_manager.current_pattern:
        try:
            current_pattern_name = (
                led_server.pattern_manager.current_pattern.definition().name
            )
        except Exception as e:
            print(f"Error getting current pattern name: {e}")

    response_data = {"patterns": pattern_data, "current_pattern": current_pattern_name}

    print(f"Returning {len(pattern_data)} patterns")
    print(f"Response data: {response_data}")

    return jsonify(response_data)


@app.route("/api/patterns/set", methods=["POST"])
def set_pattern():
    """Set the current pattern"""
    data = request.json
    pattern_name = data.get("name")
    params = data.get("params", {})

    success = led_server.pattern_manager.set_pattern(pattern_name, params)

    return jsonify({"success": success, "pattern": pattern_name, "params": params})


@app.route("/api/params/update", methods=["POST"])
def update_params():
    """Update parameters for the current pattern"""
    data = request.json
    params = data.get("params", {})

    if led_server.pattern_manager.current_pattern:
        led_server.pattern_manager.update_pattern_params(params)
        return jsonify({"success": True, "params": params})
    else:
        return jsonify({"success": False, "error": "No active pattern"}), 400


@app.route("/api/power", methods=["POST"])
def set_power():
    """Set the power state of the LED Grid"""
    data = request.json

    # Ensure we have data and extract power_state with a default value
    if not data:
        return jsonify({"success": False, "error": "Missing request data"}), 400

    # Extract and validate the power state
    power_state = data.get("state")
    if power_state is None:
        return jsonify({"success": False, "error": "Missing 'state' parameter"}), 400

    # Convert to boolean if needed
    if not isinstance(power_state, bool):
        if power_state.lower() in ["true", "1", "on", "yes"]:
            power_state = True
        elif power_state.lower() in ["false", "0", "off", "no"]:
            power_state = False
        else:
            return jsonify(
                {"success": False, "error": f"Invalid power state: {power_state}"}
            ), 400

    try:
        # Update the power state in the pattern manager
        with led_server.pattern_manager.hardware_lock:
            led_server.pattern_manager.hardware_state["power"] = power_state

        # Call the power control handler with the appropriate state
        state_str = "ON" if power_state else "OFF"
        led_server.pattern_manager._handle_power_control(state_str.encode())

        # Broadcast the power state change to all connected clients
        socketio.emit("status_update", {"power": power_state})

        return jsonify(
            {
                "success": True,
                "power": power_state,
                "message": f"Power set to {'ON' if power_state else 'OFF'}",
            }
        )
    except Exception as e:
        print(f"Error setting power state: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/brightness", methods=["POST"])
def set_brightness():
    """Set the global brightness of the LED Grid"""
    data = request.json

    # Ensure we have data and extract brightness with a default value
    if not data:
        return jsonify({"success": False, "error": "Missing request data"}), 400

    # Extract the brightness value
    brightness = data.get("value")
    if brightness is None:
        return jsonify({"success": False, "error": "Missing 'value' parameter"}), 400

    try:
        # Convert to float and validate brightness value (0.0-1.0)
        brightness = float(brightness)

        # Check if the value is in the 0-255 range and normalize it
        if brightness > 1.0 and brightness <= 255:
            brightness = brightness / 255.0

        # Clamp to valid range
        brightness = max(0.0, min(1.0, brightness))

        # Update the brightness in the pattern manager with thread safety
        with led_server.pattern_manager.display_lock:
            led_server.pattern_manager.display_state["brightness"] = brightness

        # Call the brightness control handler
        led_server.pattern_manager._handle_brightness_control(str(brightness).encode())

        # Broadcast the brightness change to all connected clients
        socketio.emit("status_update", {"brightness": brightness})

        return jsonify(
            {
                "success": True,
                "brightness": brightness,
                "message": f"Brightness set to {brightness:.2f} ({int(brightness * 255)}/255)",
            }
        )
    except ValueError:
        error_msg = f"Invalid brightness value: {data.get('value')}. Must be a number between 0.0 and 1.0"
        print(error_msg)
        return jsonify({"success": False, "error": error_msg}), 400
    except Exception as e:
        print(f"Error setting brightness: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get the current status of the LED Grid"""
    try:
        status = {
            "power": led_server.pattern_manager.hardware_state.get("power", True),
            "brightness": led_server.pattern_manager.hardware_state.get(
                "brightness", 1.0
            ),
            "current_pattern": None,
        }

        # Add current pattern info if available
        if led_server.pattern_manager.current_pattern:
            try:
                status["current_pattern"] = (
                    led_server.pattern_manager.current_pattern.definition().name
                )
            except Exception as e:
                print(f"Error getting current pattern name: {e}")

        return jsonify(status)
    except Exception as e:
        print(f"Error getting status: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/reload_patterns", methods=["POST"])
def reload_patterns():
    """Manually reload patterns"""
    print("\n=== API: Reload Patterns Request ===")

    try:
        # Store the original pattern count for comparison
        original_count = len(led_server.pattern_manager.patterns)
        original_names = [
            p.definition().name for p in led_server.pattern_manager.patterns
        ]
        print(f"Original patterns: {original_count} patterns")

        # Reload patterns
        print("Calling pattern_manager.load_patterns()...")
        success = led_server.pattern_manager.load_patterns()

        if not success:
            print("Pattern manager reported loading failure")
            return jsonify(
                {
                    "success": False,
                    "message": "Pattern manager reported loading failure",
                    "patterns": original_names,
                }
            ), 500

        # Get updated pattern list
        patterns = led_server.pattern_manager.patterns
        pattern_names = [p.definition().name for p in patterns]
        print(f"Reloaded patterns: {len(patterns)} patterns")

        # Prepare response
        response = {
            "success": True,
            "message": f"Successfully reloaded {len(patterns)} patterns",
            "patterns": pattern_names,
            "before_count": original_count,
            "after_count": len(patterns),
        }

        return jsonify(response)
    except Exception as e:
        print(f"Error reloading patterns: {e}")
        import traceback

        traceback.print_exc()

        return jsonify(
            {"success": False, "message": f"Error reloading patterns: {str(e)}"}
        ), 500


@app.route("/api/grid_config", methods=["GET"])
def get_grid_config():
    """Get the current grid configuration"""
    try:
        with led_server.grid_config_lock:
            config = led_server.grid_config

            # Convert enum values to strings for JSON serialization
            response = {
                "width": config.width,
                "height": config.height,
                "start_corner": config.start_corner,
                "first_row_direction": config.first_row_direction.value,
                "row_progression": config.row_progression.value,
                "serpentine": config.serpentine,
            }

        return jsonify({"success": True, "config": response})
    except Exception as e:
        print(f"Error getting grid configuration: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/grid_config", methods=["POST"])
def set_grid_config():
    """Update the grid configuration"""
    from server.config.grid_config import GridDirection, RowDirection

    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Missing request data"}), 400

    try:
        # Validate that at least one configuration parameter is provided
        config_params = [
            "width",
            "height",
            "start_corner",
            "first_row_direction",
            "row_progression",
            "serpentine",
        ]
        if not any(param in data for param in config_params):
            return jsonify(
                {
                    "success": False,
                    "error": "No valid configuration parameters provided",
                }
            ), 400

        # Update the configuration parameters that are provided - with thread safety
        with led_server.grid_config_lock:
            if "width" in data:
                led_server.grid_config.width = int(data["width"])

            if "height" in data:
                led_server.grid_config.height = int(data["height"])

            if "start_corner" in data:
                # Parse the start corner string (format: "bottom-right", "top-left", etc.)
                corner = data["start_corner"].split("-")
                if len(corner) != 2:
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Invalid start_corner format: {data['start_corner']}",
                        }
                    ), 400

                vert, horiz = corner
                row = 0 if vert == "top" else (led_server.grid_config.height - 1)
                col = 0 if horiz == "left" else (led_server.grid_config.width - 1)
                led_server.grid_config.start_corner = (row, col)

            if "first_row_direction" in data:
                # Convert string to enum
                direction = data["first_row_direction"]
                if direction == "left_to_right":
                    led_server.grid_config.first_row_direction = (
                        GridDirection.LEFT_TO_RIGHT
                    )
                elif direction == "right_to_left":
                    led_server.grid_config.first_row_direction = (
                        GridDirection.RIGHT_TO_LEFT
                    )
                else:
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Invalid first_row_direction: {direction}",
                        }
                    ), 400

            if "row_progression" in data:
                # Convert string to enum
                progression = data["row_progression"]
                if progression == "top_to_bottom":
                    led_server.grid_config.row_progression = RowDirection.TOP_TO_BOTTOM
                elif progression == "bottom_to_top":
                    led_server.grid_config.row_progression = RowDirection.BOTTOM_TO_TOP
                else:
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Invalid row_progression: {progression}",
                        }
                    ), 400

            if "serpentine" in data:
                led_server.grid_config.serpentine = bool(data["serpentine"])

            # Make a deep copy of the grid config before passing to components
            # This ensures components get a consistent copy even if config changes during the update
            grid_config_copy = copy.deepcopy(led_server.grid_config)

            # Notify the pattern manager and frame generator about the configuration change
            led_server.pattern_manager.grid_config = grid_config_copy
            led_server.frame_generator.grid_config = grid_config_copy

        # Return the updated configuration
        return get_grid_config()

    except Exception as e:
        print(f"Error updating grid configuration: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/grid_config/save_default", methods=["POST"])
def save_default_grid_config():
    """Save the current grid configuration as the default"""
    from server.config.grid_config import GridDirection, RowDirection
    import inspect
    import sys
    import os

    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Missing request data"}), 400

    try:
        # First update the current configuration
        result = set_grid_config()
        if not isinstance(result, tuple) and result.status_code == 200:
            # Get the current configuration using the lock for thread safety
            with led_server.grid_config_lock:
                config = copy.deepcopy(led_server.grid_config)

            # Path to the grid_config.py file
            module_path = inspect.getfile(sys.modules["server.config.grid_config"])

            # Create a backup of the original file
            backup_path = f"{module_path}.bak"
            try:
                with open(module_path, "r") as orig_file:
                    with open(backup_path, "w") as backup_file:
                        backup_file.write(orig_file.read())
            except Exception as e:
                print(f"Error creating backup: {e}")
                return jsonify(
                    {"success": False, "error": f"Failed to create backup: {str(e)}"}
                ), 500

            # Generate new DEFAULT_CONFIG value based on current configuration
            new_default_config = (
                f"# Default configuration for our setup\n"
                f"DEFAULT_CONFIG = GridConfig(\n"
                f"    width={config.width},\n"
                f"    height={config.height},\n"
                f"    start_corner={config.start_corner},\n"
                f"    first_row_direction=GridDirection.{config.first_row_direction.name},\n"
                f"    row_progression=RowDirection.{config.row_progression.name},\n"
                f"    serpentine={config.serpentine}\n"
                f")\n"
            )

            # Read the current file content
            with open(module_path, "r") as f:
                content = f.read()

            # Replace the DEFAULT_CONFIG definition
            import re

            pattern = r"# Default configuration for our setup\s*DEFAULT_CONFIG = GridConfig\([^)]*\)"
            replacement = new_default_config.strip()
            new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

            # Write the updated file
            with open(module_path, "w") as f:
                f.write(new_content)

            return jsonify(
                {
                    "success": True,
                    "message": "Default grid configuration saved successfully",
                    "config": {
                        "width": config.width,
                        "height": config.height,
                        "start_corner": config.start_corner,
                        "first_row_direction": config.first_row_direction.value,
                        "row_progression": config.row_progression.value,
                        "serpentine": config.serpentine,
                    },
                }
            )
        else:
            # If set_grid_config returned an error
            if isinstance(result, tuple):
                return result
            return jsonify(
                {"success": False, "error": "Failed to update configuration"}
            ), 500

    except Exception as e:
        print(f"Error saving default grid configuration: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# WebSocket frame observer function
def frame_observer(frame):
    """Process frames from the generator and send to web clients"""
    # Get grid dimensions with thread safety
    with led_server.grid_config_lock:
        width = led_server.grid_config.width
        height = led_server.grid_config.height

    # Create a 2D array of RGB values
    grid_data = []
    for y in range(height):
        row = []
        for x in range(width):
            index = (y * width + x) * 3
            if index + 2 < len(frame.data):
                r = frame.data[index]
                g = frame.data[index + 1]
                b = frame.data[index + 2]
                row.append([r, g, b])
            else:
                row.append([0, 0, 0])
        grid_data.append(row)

    # Send to all connected clients
    socketio.emit(
        "frame_update",
        {
            "grid": grid_data,
            "sequence": frame.sequence,
            "timestamp": frame.timestamp,
            "pattern": frame.metadata.get("pattern_name", ""),
            "params": frame.metadata.get("params", {}),
        },
    )


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")

    # Register frame observer if not already registered
    if frame_observer not in led_server.frame_generator.frame_observers:
        led_server.frame_generator.add_frame_observer(frame_observer)


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

    # Check if there are any clients left
    if len(socketio.server.eio.sockets) == 0:
        # Remove frame observer if no clients are connected
        led_server.frame_generator.remove_frame_observer(frame_observer)
