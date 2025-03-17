"""
Routes for the LED Grid web dashboard.

This module defines the API endpoints and WebSocket handlers for the LED Grid dashboard.
"""

from flask import jsonify, request, render_template
from flask_socketio import emit
from server.web import app, socketio, led_server
from datetime import datetime


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
    power_state = data.get("state", False)

    try:
        # Update the power state in the pattern manager
        led_server.pattern_manager.hardware_state["power"] = power_state

        # Call the power control handler with the appropriate state
        state_str = "ON" if power_state else "OFF"
        led_server.pattern_manager._handle_power_control(state_str.encode())

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
    brightness = data.get("value", 1.0)

    try:
        # Validate brightness value (0.0-1.0)
        brightness = float(brightness)
        brightness = max(0.0, min(1.0, brightness))

        # Update the brightness in the pattern manager
        led_server.pattern_manager.hardware_state["brightness"] = brightness

        # Call the brightness control handler
        led_server.pattern_manager._handle_brightness_control(str(brightness).encode())

        return jsonify(
            {
                "success": True,
                "brightness": brightness,
                "message": f"Brightness set to {brightness:.2f} ({int(brightness * 255)}/255)",
            }
        )
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
        # Reload patterns
        led_server.pattern_manager.load_patterns()

        # Get updated pattern list
        patterns = led_server.pattern_manager.patterns
        pattern_names = [p.definition().name for p in patterns]

        return jsonify(
            {
                "success": True,
                "message": f"Successfully reloaded {len(patterns)} patterns",
                "patterns": pattern_names,
            }
        )
    except Exception as e:
        print(f"Error reloading patterns: {e}")
        import traceback

        traceback.print_exc()

        return jsonify(
            {"success": False, "message": f"Error reloading patterns: {str(e)}"}
        ), 500


# WebSocket frame observer function
def frame_observer(frame):
    """Process frames from the generator and send to web clients"""
    # Convert frame data to RGB array for web rendering
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
