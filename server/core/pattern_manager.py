from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import threading
import time
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import json
import traceback

from server.config.grid_config import GridConfig
from server.patterns.base import Pattern, PatternRegistry


class PatternManager:
    """Manages pattern state and hardware control"""

    def __init__(self, grid_config: GridConfig, mqtt_config: Dict[str, Any]):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.mqtt_config = mqtt_config
        self.mqtt_client = None
        self.is_connected = False

        # Pattern state
        self.patterns = []  # Will be populated in load_patterns()
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_id: Optional[str] = None
        self.pattern_lock = threading.RLock()

        # Callback for pattern changes
        self.on_pattern_change: Optional[
            Callable[[Optional[Pattern], Dict[str, Any], str], None]
        ] = None

        # Hardware state
        self.hardware_state = {
            "brightness": 255,
            "power": True,
            "last_reset": 0,
        }
        self.hardware_lock = threading.RLock()

        # Performance tracking
        self.performance_state = {
            "fps": 0.0,
            "frame_time": 0.0,
            "frame_count": 0,
            "last_update": 0,
        }
        self.performance_lock = threading.RLock()

    def connect_mqtt(self):
        """Connect to MQTT broker and set up command handling"""
        try:
            # Create MQTT client with unique ID
            client_id = f"pattern_manager_{int(time.time())}"
            print(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Set up callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message

            # Enable automatic reconnection with exponential backoff
            self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)

            # Set up authentication if provided
            if self.mqtt_config.get("username") and self.mqtt_config.get("password"):
                self.mqtt_client.username_pw_set(
                    self.mqtt_config["username"], self.mqtt_config["password"]
                )

            # Connect to broker
            print(
                f"Connecting to MQTT broker at {self.mqtt_config['host']}:{self.mqtt_config.get('port', 1883)}"
            )
            self.mqtt_client.connect_async(
                self.mqtt_config["host"], self.mqtt_config.get("port", 1883), 60
            )

            # Start MQTT loop in background thread
            self.mqtt_client.loop_start()

            # Wait for connection
            timeout = 10
            while timeout > 0 and not self.is_connected:
                time.sleep(0.1)
                timeout -= 0.1

            if not self.is_connected:
                print(
                    "MQTT connection timeout, but continuing with async connection attempts"
                )
                # We'll continue anyway since we're using async connection

            # Set up subscriptions after connection
            self._setup_mqtt_subscriptions()

            # Subscribe to command topics
            self.mqtt_client.subscribe("led/command/#")

            # Publish online status
            self.mqtt_client.publish("led/status/pattern_server", "online", retain=True)

            return True

        except Exception as e:
            print(f"Error connecting to MQTT: {e}")
            traceback.print_exc()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client = None
            return False

    def _setup_mqtt_subscriptions(self):
        """Setup MQTT subscriptions for pattern control"""
        if not self.mqtt_client:
            print("MQTT client not initialized")
            return

        # Subscribe to all LED command topics
        self.mqtt_client.subscribe("led/command/#")

        # Set message callback
        self.mqtt_client.on_message = self._on_mqtt_message

    def register_pattern_change_callback(
        self, callback: Callable[[Optional[Pattern], Dict[str, Any], str], None]
    ):
        """Register callback for pattern changes"""
        self.on_pattern_change = callback

    def _notify_pattern_change(self):
        """Notify callback of pattern changes"""
        if self.on_pattern_change:
            pattern_id = str(time.time_ns()) if self.current_pattern else None
            self.on_pattern_change(
                self.current_pattern, self.current_params, pattern_id
            )

    def _handle_pattern_select(self, msg):
        """Handle pattern selection"""
        try:
            pattern_name = msg.decode()
            print(f"Pattern selection request: {pattern_name}")

            pattern = next(
                (p for p in self.patterns if p.definition().name == pattern_name), None
            )
            if pattern:
                print(f"Found pattern: {pattern.definition().name}")
                self.current_pattern = pattern

                # Notify callback
                self._notify_pattern_change()

                print(f"Pattern selection complete: {pattern.definition().name}")
            else:
                print(f"Pattern not found: {pattern_name}")
                print(
                    f"Available patterns: {[p.definition().name for p in self.patterns]}"
                )
        except Exception as e:
            print(f"Error handling pattern select: {e}")
            traceback.print_exc()

    def _handle_numeric_param(self, param_name: str, msg):
        """Handle numeric parameter updates"""
        try:
            value = float(msg.decode())
            if self.current_pattern:
                self.current_pattern.params[param_name] = value
            else:
                print(f"No active pattern to update parameter {param_name}")
        except Exception as e:
            print(f"Error handling numeric param {param_name}: {e}")

    def _handle_select_param(self, param_name: str, msg):
        """Handle select parameter updates"""
        try:
            value = msg.decode()
            if self.current_pattern:
                self.current_pattern.params[param_name] = value
            else:
                print(f"No active pattern to update parameter {param_name}")
        except Exception as e:
            print(f"Error handling select param {param_name}: {e}")

    def _handle_brightness_control(self, msg):
        """Handle brightness control"""
        try:
            # Parse the brightness value
            brightness_str = msg.decode()
            brightness = float(brightness_str)

            # Normalize brightness value
            if brightness > 1.0 and brightness <= 255:
                # Convert from 0-255 range to 0.0-1.0 range
                brightness = brightness / 255.0
            elif brightness < 0.0 or brightness > 1.0:
                # Clamp to valid range
                brightness = max(0.0, min(1.0, brightness))

            # Update hardware state
            self.hardware_state["brightness"] = brightness

            # Log the change
            print(f"Brightness set to {brightness:.2f} ({int(brightness * 255)}/255)")

        except Exception as e:
            print(f"Error handling brightness control: {e}")
            traceback.print_exc()

    def _handle_power_control(self, msg):
        """Handle power control"""
        try:
            state = msg.decode()
            self.hardware_state["power"] = state == "ON"
        except Exception as e:
            print(f"Error handling power control: {e}")

    def _handle_reset_control(self, msg):
        """Handle reset control"""
        try:
            if msg.decode() == "RESET":
                self.hardware_state["last_reset"] = datetime.now().isoformat()
        except Exception as e:
            print(f"Error handling reset control: {e}")

    def _handle_clear(self, msg):
        """Handle clear command"""
        try:
            if msg.decode() == "CLEAR":
                # Clear pattern and update state
                self.current_pattern = None
                self.current_params = {}
        except Exception as e:
            print(f"Error handling clear command: {e}")

    def _handle_stop(self, msg):
        """Handle stop command"""
        try:
            if msg.decode() == "STOP":
                # Stop pattern and update state
                self.current_pattern = None
                self.current_params = {}
        except Exception as e:
            print(f"Error handling stop command: {e}")

    def _handle_cleanup(self, msg):
        """Handle cleanup command"""
        try:
            if msg.decode() == "CLEANUP":
                print("Received cleanup command")
                # Clean up pattern and update state
                self.current_pattern = None
                self.current_params = {}
        except Exception as e:
            print(f"Error handling cleanup command: {e}")
            traceback.print_exc()

    def load_patterns(self):
        """Load available patterns"""
        print("\n=== Starting Pattern Loading Process ===")
        try:
            # Get pattern definitions
            print("\n=== Loading Pattern Definitions ===")
            print("Loading pattern definitions from registry...")
            pattern_defs = PatternRegistry.list_patterns()
            print(f"Found {len(pattern_defs)} pattern definitions in registry")

            if not pattern_defs:
                print("WARNING: No pattern definitions found in registry!")
                print("This could indicate that patterns were not properly registered.")
                print("Check that all pattern modules are being imported correctly.")
                print("Pattern Registry contents:", PatternRegistry._patterns)

                # Try to diagnose the issue
                print("\n=== Pattern Registry Diagnosis ===")
                if not hasattr(PatternRegistry, "_patterns"):
                    print("ERROR: PatternRegistry._patterns attribute not found!")
                    print(
                        "This suggests a serious issue with the PatternRegistry class."
                    )
                elif PatternRegistry._patterns is None:
                    print("ERROR: PatternRegistry._patterns is None!")
                    print("The registry dictionary has not been initialized properly.")
                elif not isinstance(PatternRegistry._patterns, dict):
                    print(
                        f"ERROR: PatternRegistry._patterns is not a dictionary! Type: {type(PatternRegistry._patterns)}"
                    )
                    print(
                        "The registry should be a dictionary mapping pattern names to pattern classes."
                    )
                else:
                    print("PatternRegistry._patterns is an empty dictionary.")
                    print(
                        "This suggests that no patterns were registered during import."
                    )
                    print(
                        "Check that pattern modules are imported and use the @PatternRegistry.register decorator."
                    )
            else:
                print("Pattern definitions found:")
                for pattern_def in pattern_defs:
                    print(f"  - {pattern_def.name}: {pattern_def.description}")

            # Create pattern instances
            print("\n=== Creating Pattern Instances ===")
            self.patterns = []
            successful_patterns = 0
            failed_patterns = 0

            for pattern_def in pattern_defs:
                try:
                    print(f"Loading pattern: {pattern_def.name}")
                    pattern_class = PatternRegistry.get_pattern(pattern_def.name)
                    if pattern_class:
                        print(f"  - Found pattern class: {pattern_class.__name__}")
                        try:
                            print(f"  - Creating instance of {pattern_class.__name__}")
                            pattern_instance = pattern_class(self.grid_config)
                            print(f"  - Successfully created instance")
                            self.patterns.append(pattern_instance)
                            print(f"  - Added to patterns list")
                            print(f"Successfully loaded pattern: {pattern_def.name}")
                            successful_patterns += 1
                        except Exception as instance_error:
                            print(
                                f"  - ERROR: Failed to create instance: {instance_error}"
                            )
                            import traceback

                            traceback.print_exc()
                            failed_patterns += 1
                    else:
                        print(f"ERROR: Pattern class not found for {pattern_def.name}")
                        print(
                            f"This suggests a mismatch between pattern definitions and registered patterns."
                        )
                        failed_patterns += 1
                except Exception as e:
                    print(f"ERROR: Failed to load pattern {pattern_def.name}: {e}")
                    import traceback

                    traceback.print_exc()
                    failed_patterns += 1

            print(f"\n=== Pattern Loading Summary ===")
            print(f"Loaded {len(self.patterns)} patterns")
            print(f"Successful: {successful_patterns}, Failed: {failed_patterns}")

            # Print the names of all loaded patterns
            pattern_names = [p.definition().name for p in self.patterns]
            print(f"Available patterns: {pattern_names}")

            if not self.patterns:
                print("WARNING: No patterns were loaded successfully!")
                print("This could indicate an issue with pattern initialization.")
                print("Check the error messages above for more details.")

                # Try to load a simple test pattern directly
                print("\n=== Attempting to Load Test Pattern Directly ===")
                try:
                    from server.patterns.test_pattern import TestPattern

                    test_pattern = TestPattern(self.grid_config)
                    self.patterns.append(test_pattern)
                    print("Successfully loaded test pattern directly!")
                    print(
                        "This suggests an issue with the pattern registration process."
                    )
                except Exception as e:
                    print(f"Failed to load test pattern directly: {e}")
                    traceback.print_exc()
                    print(
                        "This suggests a more fundamental issue with the pattern system."
                    )

            print("\n=== Pattern Loading Process Complete ===")
            return True
        except Exception as e:
            print(f"ERROR: Failed to load patterns: {e}")
            import traceback

            traceback.print_exc()
            print("\n=== Pattern Loading Process Failed ===")
            return False

    def initialize(self):
        """Initialize the pattern manager"""
        print("\nInitializing pattern manager...")

        # Connect to MQTT broker
        if not self.connect_mqtt():
            print("Failed to connect to MQTT broker")
            return False

        # Load patterns
        self.load_patterns()

        # Update pattern options and state
        pattern_names = [p.definition().name for p in self.patterns]
        print(f"Available patterns: {pattern_names}")

        # Initialize hardware state
        self.hardware_state["brightness"] = 255
        self.hardware_state["power"] = True
        self.hardware_state["last_reset"] = 0

        # Start performance monitoring
        self._start_performance_monitoring()

        # Publish online status
        self.mqtt_client.publish("led/status/pattern_server", "online", retain=True)

        # Trigger a full sync of all data
        self._sync_all_data()

        print("Pattern manager initialized successfully")
        return True

    def stop(self):
        """Stop pattern manager and clean up"""
        try:
            # Publish offline status
            if self.mqtt_client:
                self.mqtt_client.publish(
                    "led/status/pattern_server", "offline", retain=True
                )
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except:
            pass

    def _start_performance_monitoring(self):
        """Start monitoring performance metrics"""
        # Initialize performance state
        self.performance_state["fps"] = 0.0
        self.performance_state["frame_time"] = 0.0
        self.performance_state["frame_count"] = 0
        self.performance_state["last_update"] = time.time()

    def update_performance_metrics(self, frame_time: float):
        """Update performance metrics with latest frame data"""
        try:
            now = datetime.now()
            self.performance_state["frame_time"] = frame_time
            self.performance_state["frame_count"] += 1

            # Update FPS every second
            time_since_update = (
                now - self.performance_state["last_update"]
            ).total_seconds()
            if time_since_update >= 1.0:
                fps = self.performance_state["frame_count"] / time_since_update
                self.performance_state["fps"] = round(fps, 2)
                self.performance_state["frame_count"] = 0
                self.performance_state["last_update"] = now

                # Publish performance metrics
                self.mqtt_client.publish(
                    "led/status/performance/fps", str(self.performance_state["fps"])
                )
                self.mqtt_client.publish(
                    "led/status/performance/frame_time",
                    str(self.performance_state["frame_time"]),
                )
        except Exception as e:
            print(f"Error updating performance metrics: {e}")

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            print("Connected to MQTT broker successfully")
            self.is_connected = True
        else:
            print(f"Failed to connect to MQTT broker with code {rc}")
            self.is_connected = False

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        print(f"Disconnected from MQTT broker with code {rc}")
        self.is_connected = False

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            print(f"\nReceived message on topic: {msg.topic}")
            payload = msg.payload.decode()

            # Pattern commands
            if msg.topic == "led/command/pattern":
                try:
                    # Try to parse as JSON first
                    data = json.loads(payload)
                    pattern_name = data.get("name")
                    params = data.get("params", {})
                except json.JSONDecodeError:
                    # Fall back to treating payload as direct pattern name
                    pattern_name = payload
                    params = {}

                if pattern_name:
                    self.set_pattern(pattern_name, params)
                else:
                    print(f"Invalid pattern command: {payload}")

            # Parameter update
            elif msg.topic == "led/command/params":
                try:
                    data = json.loads(payload)
                    params = data.get("params", {})
                    if params:
                        self.update_pattern_params(params)
                    else:
                        print("No parameters provided in command")
                except json.JSONDecodeError:
                    print(f"Invalid JSON in params command: {payload}")

            # Hardware commands
            elif msg.topic == "led/command/hardware":
                try:
                    data = json.loads(payload)
                    command = data.get("command")
                    value = data.get("value")

                    if command == "brightness":
                        self._handle_brightness_control(str(value).encode())
                    elif command == "power":
                        self._handle_power_control(("ON" if value else "OFF").encode())
                    elif command == "reset":
                        self._handle_reset_control(b"RESET")
                except json.JSONDecodeError:
                    print(f"Invalid hardware command JSON: {payload}")

            # Direct hardware commands
            elif msg.topic == "led/command/brightness":
                self._handle_brightness_control(msg.payload)
            elif msg.topic == "led/command/power":
                self._handle_power_control(msg.payload)
            elif msg.topic == "led/command/reset":
                self._handle_reset_control(msg.payload)
            elif msg.topic == "led/command/clear":
                self._handle_clear(msg.payload)
            elif msg.topic == "led/command/stop":
                self._handle_stop(msg.payload)

            # Pattern list request
            elif msg.topic == "led/command/list":
                try:
                    print("\nReceived pattern list request")

                    # Get pattern names from loaded patterns
                    pattern_names = [p.definition().name for p in self.patterns]

                    if not pattern_names:
                        print("WARNING: No patterns available to list!")
                        print(
                            "This could indicate that patterns were not properly loaded."
                        )
                        print("Attempting to reload patterns...")

                        # Try to reload patterns
                        self.load_patterns()

                        # Get pattern names again after reload
                        pattern_names = [p.definition().name for p in self.patterns]

                        if not pattern_names:
                            print("ERROR: Still no patterns available after reload!")
                            # We'll continue and send an empty list, but this is a critical issue

                    print(f"Sending pattern list: {pattern_names}")

                    # Send the pattern list
                    self.mqtt_client.publish(
                        "led/status/pattern/list",
                        json.dumps(pattern_names),
                        retain=True,
                    )

                    # Also send detailed pattern information
                    patterns_info = []
                    for pattern in self.patterns:
                        pattern_def = pattern.definition()
                        patterns_info.append(
                            {
                                "name": pattern_def.name,
                                "description": pattern_def.description,
                                "parameters": [
                                    {
                                        "name": param.name,
                                        "type": str(param.type.__name__),
                                        "default": param.default,
                                        "description": param.description,
                                    }
                                    for param in pattern_def.parameters
                                ],
                            }
                        )

                    # Send detailed pattern information
                    self.mqtt_client.publish(
                        "led/status/list",
                        json.dumps(
                            {
                                "patterns": patterns_info,
                                "current_pattern": self.current_pattern.definition().name
                                if self.current_pattern
                                else None,
                                "hardware_state": self.hardware_state,
                                "performance": self.performance_state,
                            }
                        ),
                        retain=True,
                    )

                    print("Pattern list response sent successfully")
                except Exception as e:
                    print(f"ERROR: Failed to handle pattern list request: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"Error handling MQTT message: {e}")
            print(f"Message payload: {msg.payload}")
            print(f"Topic: {msg.topic}")
            traceback.print_exc()

    def set_pattern(self, pattern_name: str, params: Dict[str, Any] = None):
        """Set pattern with immediate effect"""
        with self.pattern_lock:
            print(f"\nPattern change requested: {pattern_name}")
            print(f"Initial params: {params}")

            # Clean up old pattern
            if self.current_pattern:
                print(
                    f"Cleaning up old pattern: {self.current_pattern.definition().name}"
                )

            # Set new pattern
            try:
                # First try to get the pattern directly by name
                pattern_class = PatternRegistry.get_pattern(pattern_name)

                # If not found, try to find a pattern with a similar name
                if not pattern_class:
                    print(f"Pattern {pattern_name} not found directly in registry")

                    # Get all available patterns
                    all_patterns = PatternRegistry.list_patterns()
                    all_pattern_names = [p.name for p in all_patterns]
                    print(f"Available patterns: {all_pattern_names}")

                    # Try to find a case-insensitive match
                    for p_def in all_patterns:
                        if p_def.name.lower() == pattern_name.lower():
                            print(f"Found case-insensitive match: {p_def.name}")
                            pattern_class = PatternRegistry.get_pattern(p_def.name)
                            pattern_name = p_def.name  # Update to the correct case
                            break

                if pattern_class:
                    print(f"Creating new pattern instance: {pattern_name}")
                    self.current_pattern = pattern_class(self.grid_config)
                    self.current_params = params or {}
                    self.pattern_id = str(time.time_ns())

                    # Notify frame generator
                    self._notify_pattern_change()

                    # Send success response
                    self.mqtt_client.publish(
                        "led/response/pattern",
                        json.dumps(
                            {
                                "success": True,
                                "pattern": pattern_name,
                                "params": self.current_params,
                            }
                        ),
                        retain=False,
                    )
                else:
                    print(f"Pattern {pattern_name} not found in registry")
                    print(
                        f"Available patterns: {[p.definition().name for p in self.patterns]}"
                    )

                    self.current_pattern = None
                    self.current_params = {}
                    self.pattern_id = None
                    print("Pattern cleared")

                    # Send error response
                    self.mqtt_client.publish(
                        "led/response/pattern",
                        json.dumps(
                            {
                                "success": False,
                                "error": f"Pattern '{pattern_name}' not found",
                                "available_patterns": [
                                    p.definition().name for p in self.patterns
                                ],
                            }
                        ),
                        retain=False,
                    )
            except Exception as e:
                print(f"ERROR: Failed to set pattern {pattern_name}: {e}")
                traceback.print_exc()

                self.current_pattern = None
                self.current_params = {}
                self.pattern_id = None

                # Send error response
                self.mqtt_client.publish(
                    "led/response/pattern",
                    json.dumps(
                        {
                            "success": False,
                            "error": f"Error setting pattern '{pattern_name}': {str(e)}",
                            "available_patterns": [
                                p.definition().name for p in self.patterns
                            ],
                        }
                    ),
                    retain=False,
                )

            # Notify frame generator
            self._notify_pattern_change()

            # Update hardware state
            if self.current_pattern:
                self.hardware_state["brightness"] = 255
                self.hardware_state["power"] = True
                self.hardware_state["last_reset"] = 0
            else:
                self.hardware_state["brightness"] = 255
                self.hardware_state["power"] = True
                self.hardware_state["last_reset"] = 0

    def update_pattern_params(self, params: Dict[str, Any]):
        """Update current pattern parameters"""
        with self.pattern_lock:
            if self.current_pattern:
                print(
                    f"\nUpdating parameters for pattern: {self.current_pattern.definition().name}"
                )
                print(f"Current params: {self.current_params}")
                print(f"New params to merge: {params}")
                self.current_params.update(params)
                print(f"Final merged params: {self.current_params}")

                # Notify frame generator
                self._notify_pattern_change()
            else:
                print("No active pattern to update parameters for")

    def _sync_all_data(self):
        """Synchronize all data with MQTT topics"""
        try:
            print("\nPerforming full data synchronization...")

            # 1. Synchronize pattern list
            pattern_names = [p.definition().name for p in self.patterns]
            print(f"Synchronized pattern list: {pattern_names}")

            # Send the pattern list
            self.mqtt_client.publish(
                "led/status/pattern/list",
                json.dumps(pattern_names),
                retain=True,
            )

            # 2. Synchronize current pattern and parameters
            if self.current_pattern:
                # Get the pattern definition for parameter metadata
                pattern_def = self.current_pattern.definition()

                # Log detailed information about the pattern parameters
                print(f"Current pattern: {pattern_def.name}")
                print(f"Pattern parameters: {self.current_params}")

                # Send current pattern information
                self.mqtt_client.publish(
                    "led/status/pattern/current",
                    json.dumps({"name": pattern_def.name}),
                    retain=True,
                )

                # Send current parameters
                self.mqtt_client.publish(
                    "led/status/pattern/params",
                    json.dumps({"params": self.current_params}),
                    retain=True,
                )
            else:
                print("No current pattern to synchronize")
                # Clear current pattern
                self.mqtt_client.publish(
                    "led/status/pattern/current",
                    json.dumps({"name": ""}),
                    retain=True,
                )

            # 3. Synchronize hardware state
            self.mqtt_client.publish(
                "led/status/hardware",
                json.dumps(self.hardware_state),
                retain=True,
            )
            print("Synchronized hardware state")

            # 4. Synchronize performance metrics
            with self.performance_lock:
                self.mqtt_client.publish(
                    "led/status/performance",
                    json.dumps(self.performance_state),
                    retain=True,
                )
            print("Synchronized performance metrics")

            print("Full data synchronization complete")
            return True
        except Exception as e:
            print(f"Error in _sync_all_data: {e}")
            traceback.print_exc()
            return False
