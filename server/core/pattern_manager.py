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
from server.homeassistant import HomeAssistantManager


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

        # Home Assistant integration
        self.ha_manager = HomeAssistantManager(None)  # Will be updated with MQTT client

    def connect_mqtt(self):
        """Connect to MQTT broker and set up command handling"""
        try:
            # Create MQTT client with unique ID
            client_id = f"pattern_manager_{int(time.time())}"
            print(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Update HomeAssistantManager's MQTT client reference
            self.ha_manager.mqtt_client = self.mqtt_client

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

            # Publish discovery information
            self.ha_manager.update_component_status("pattern_server", "online")
            self.ha_manager.publish_discovery()

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

        # Pattern selection
        self.mqtt_client.subscribe("homeassistant/input_select/led_grid_pattern/set")

        # Pattern parameters
        for param in ["speed", "scale", "intensity"]:
            self.mqtt_client.subscribe(
                f"homeassistant/input_number/pattern_{param}/set"
            )

        for param in ["variation", "color_mode"]:
            self.mqtt_client.subscribe(
                f"homeassistant/input_select/pattern_{param}/set"
            )

        # Hardware controls
        self.mqtt_client.subscribe("homeassistant/input_number/led_brightness/set")
        self.mqtt_client.subscribe("led/command/power")
        self.mqtt_client.subscribe("led/command/reset")
        self.mqtt_client.subscribe("led/command/clear")
        self.mqtt_client.subscribe("led/command/stop")

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
            pattern = next((p for p in self.patterns if p.name == pattern_name), None)
            if pattern:
                self.current_pattern = pattern
                self.ha_manager.update_pattern_state(pattern.name, pattern.params)
                self.ha_manager.update_pattern_variations(pattern)
                self.ha_manager.update_color_modes(pattern)
                self._notify_pattern_change()  # Notify callback
        except Exception as e:
            print(f"Error handling pattern select: {e}")

    def _handle_numeric_param(self, param_name: str, msg):
        """Handle numeric parameter updates"""
        try:
            value = float(msg.decode())
            if self.current_pattern:
                self.current_pattern.params[param_name] = value
                self.ha_manager.update_pattern_state(
                    self.current_pattern.name, self.current_pattern.params
                )
                # Send success response
                self.mqtt_client.publish(
                    "led/response/params",
                    json.dumps({"success": True, "param": param_name, "value": value}),
                    retain=False,
                )
        except Exception as e:
            print(f"Error handling numeric param {param_name}: {e}")
            # Send error response
            self.mqtt_client.publish(
                "led/response/params",
                json.dumps(
                    {
                        "success": False,
                        "error": f"Failed to update {param_name}: {str(e)}",
                        "param": param_name,
                    }
                ),
                retain=False,
            )

    def _handle_select_param(self, param_name: str, msg):
        """Handle select parameter updates"""
        try:
            value = msg.decode()
            if self.current_pattern:
                self.current_pattern.params[param_name] = value
                self.ha_manager.update_pattern_state(
                    self.current_pattern.name, self.current_pattern.params
                )
                # Send success response
                self.mqtt_client.publish(
                    "led/response/params",
                    json.dumps({"success": True, "param": param_name, "value": value}),
                    retain=False,
                )
        except Exception as e:
            print(f"Error handling select param {param_name}: {e}")
            # Send error response
            self.mqtt_client.publish(
                "led/response/params",
                json.dumps(
                    {
                        "success": False,
                        "error": f"Failed to update {param_name}: {str(e)}",
                        "param": param_name,
                    }
                ),
                retain=False,
            )

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
            self.ha_manager.update_hardware_state(self.hardware_state)

            # Log the change
            print(f"Brightness set to {brightness:.2f} ({int(brightness * 255)}/255)")

            # Send response
            self.mqtt_client.publish(
                "led/response/brightness",
                json.dumps({"success": True, "value": brightness}),
                retain=False,
            )

        except Exception as e:
            print(f"Error handling brightness control: {e}")
            traceback.print_exc()

            # Send error response
            self.mqtt_client.publish(
                "led/response/brightness",
                json.dumps({"success": False, "error": str(e)}),
                retain=False,
            )

    def _handle_power_control(self, msg):
        """Handle power control"""
        try:
            state = msg.decode()
            self.hardware_state["power"] = state == "ON"
            self.ha_manager.update_hardware_state(self.hardware_state)
        except Exception as e:
            print(f"Error handling power control: {e}")

    def _handle_reset_control(self, msg):
        """Handle reset control"""
        try:
            if msg.decode() == "RESET":
                self.hardware_state["last_reset"] = datetime.now().isoformat()
                self.ha_manager.update_hardware_state(self.hardware_state)
        except Exception as e:
            print(f"Error handling reset control: {e}")

    def _handle_clear(self, msg):
        """Handle clear command"""
        try:
            if msg.decode() == "CLEAR":
                # Clear pattern and update state
                self.current_pattern = None
                self.current_params = {}
                self.ha_manager.update_pattern_state("", {})
                self._notify_pattern_change()  # Notify callback
        except Exception as e:
            print(f"Error handling clear command: {e}")

    def _handle_stop(self, msg):
        """Handle stop command"""
        try:
            if msg.decode() == "STOP":
                # Stop pattern and update state
                self.current_pattern = None
                self.current_params = {}
                self.ha_manager.update_pattern_state("", {})
                self._notify_pattern_change()  # Notify callback
        except Exception as e:
            print(f"Error handling stop command: {e}")

    def load_patterns(self):
        """Load available patterns"""
        # Get pattern definitions
        pattern_defs = PatternRegistry.list_patterns()

        # Create pattern instances
        self.patterns = []
        for pattern_def in pattern_defs:
            pattern_class = PatternRegistry.get_pattern(pattern_def.name)
            if pattern_class:
                self.patterns.append(pattern_class(self.grid_config))

        print(f"Loaded {len(self.patterns)} patterns")

    def start(self):
        """Start the pattern manager"""
        # Load patterns
        self.load_patterns()

        # Initialize Home Assistant
        self.ha_manager.publish_discovery()

        # Update pattern options and state
        pattern_names = [p.definition().name for p in self.patterns]
        print(f"Available patterns: {pattern_names}")
        self.ha_manager.update_pattern_options(self.patterns)

        # Initialize hardware state
        self.ha_manager.update_hardware_state(self.hardware_state)

        # Start performance monitoring
        self._start_performance_monitoring()

        # Publish online status
        self.mqtt_client.publish("led/status/pattern_server", "online", retain=True)

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

            # Pattern selection
            if (
                msg.topic == "homeassistant/input_select/led_grid_pattern/set"
                or msg.topic == "led/command/pattern/set"
            ):
                self._handle_pattern_select(msg.payload)

            # Pattern parameters - numeric
            elif (
                any(
                    msg.topic == f"homeassistant/input_number/pattern_{param}/set"
                    for param in ["speed", "scale", "intensity"]
                )
                or msg.topic == "led/command/params"
            ):
                if msg.topic == "led/command/params":
                    data = json.loads(payload)
                    for param, value in data.get("params", {}).items():
                        self._handle_numeric_param(param, str(value).encode())
                else:
                    param = msg.topic.split("/")[-2].split("_")[1]  # Extract param name
                    self._handle_numeric_param(param, msg.payload)

            # Pattern parameters - select
            elif any(
                msg.topic == f"homeassistant/input_select/pattern_{param}/set"
                for param in ["variation", "color_mode"]
            ):
                param = msg.topic.split("/")[-2].split("_")[1]  # Extract param name
                self._handle_select_param(param, msg.payload)

            # Hardware controls
            elif (
                msg.topic == "homeassistant/input_number/led_brightness/set"
                or msg.topic == "led/command/brightness"
            ):
                self._handle_brightness_control(msg.payload)
            elif msg.topic == "led/command/power":
                self._handle_power_control(msg.payload)
            elif msg.topic == "led/command/reset":
                self._handle_reset_control(msg.payload)
            elif msg.topic == "led/command/clear":
                self._handle_clear(msg.payload)
            elif msg.topic == "led/command/stop":
                self._handle_stop(msg.payload)

            # Pattern commands
            elif msg.topic == "led/command/pattern":
                data = json.loads(payload)
                self.set_pattern(data["name"], data.get("params", {}))
            elif msg.topic == "led/command/hardware":
                data = json.loads(payload)
                command = data.get("command")
                value = data.get("value")

                if command == "brightness":
                    self._handle_brightness_control(str(value).encode())
                elif command == "power":
                    self._handle_power_control(("ON" if value else "OFF").encode())
                elif command == "reset":
                    self._handle_reset_control(b"RESET")

            # Pattern list request
            elif msg.topic == "led/command/list":
                response = {
                    "patterns": [p.definition() for p in self.patterns],
                    "current_pattern": self.current_pattern.definition().name
                    if self.current_pattern
                    else None,
                    "hardware_state": self.hardware_state,
                    "performance": self.performance_state,
                }
                self.mqtt_client.publish("led/status/list", json.dumps(response))

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
            pattern_class = PatternRegistry.get_pattern(pattern_name)
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

            # Notify frame generator
            self._notify_pattern_change()

            # Update Home Assistant state
            self.ha_manager.update_pattern_state(pattern_name, self.current_params)

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

                # Update Home Assistant state
                self.ha_manager.update_pattern_state(
                    self.current_pattern.definition().name, self.current_params
                )
            else:
                print("No active pattern to update parameters for")
