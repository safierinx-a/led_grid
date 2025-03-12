import json
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt
import time
from server.patterns.base import Pattern
import traceback
import random


class HomeAssistantManager:
    """
    Manages Home Assistant MQTT discovery and state management for the LED Grid system.

    This class handles:
    1. MQTT discovery for automatic entity registration in Home Assistant
    2. State updates for patterns, parameters, hardware, and performance metrics
    3. Bidirectional communication between the LED Grid system and Home Assistant

    Usage:
        1. Initialize with an MQTT client
        2. Call publish_discovery() to register entities
        3. Use update_* methods to keep Home Assistant state in sync

    Entity Structure:
        - Pattern selection (input_select)
        - Pattern parameters (input_number, input_select)
        - Hardware controls (brightness, power)
        - Action buttons (reset, clear, stop)
        - Status sensors (FPS, frame time, component status)
    """

    def __init__(
        self,
        mqtt_client: mqtt.Client,
        base_topic: str = "homeassistant",
        unique_id_prefix: str = "led_grid",
    ):
        """
        Initialize the Home Assistant Manager.

        Args:
            mqtt_client: MQTT client for communication with Home Assistant
            base_topic: Base topic for Home Assistant MQTT discovery (default: "homeassistant")
            unique_id_prefix: Prefix for all unique IDs to prevent conflicts (default: "led_grid")
        """
        self.mqtt_client = mqtt_client
        self.base_topic = base_topic
        self.unique_id_prefix = unique_id_prefix
        # Generate a random suffix to ensure uniqueness across restarts
        self.unique_suffix = f"_{random.randint(1000, 9999)}"

        # Create a unique device identifier that will be consistent across restarts
        device_id = f"{unique_id_prefix}_controller"

        self.device_info = {
            "identifiers": [device_id],
            "name": "LED Grid",
            "model": "WS2812B 24x25",
            "manufacturer": "Custom",
            "sw_version": "1.0.0",
        }

        # Keep track of published entities for cleanup
        self.published_entities = set()

    def publish_discovery(self):
        """
        Publish Home Assistant MQTT discovery messages for all entities.

        This method registers the following entities in Home Assistant:

        Controls:
        - input_select.led_grid_pattern: Pattern selection
        - input_number.pattern_speed: Pattern speed control
        - input_number.pattern_scale: Pattern scale control
        - input_number.pattern_intensity: Pattern intensity control
        - input_select.pattern_variation: Pattern variation selection
        - input_select.pattern_color_mode: Pattern color mode selection
        - input_number.led_brightness: LED brightness control
        - switch.led_power: LED power control

        Buttons:
        - button.reset_leds: Reset LED hardware
        - button.clear_leds: Clear LED display
        - button.stop_pattern: Stop current pattern

        Sensors:
        - sensor.led_fps: Current FPS
        - sensor.led_frame_time: Frame processing time
        - sensor.led_last_reset: Last reset timestamp
        - binary_sensor.pattern_server_status: Pattern server connectivity
        - binary_sensor.led_controller_status: LED controller connectivity

        All entities are grouped under a single device in Home Assistant.
        """
        # Clean up old entities first
        self.cleanup_old_entities()

        # Now publish new discovery messages
        print("Publishing discovery messages...")

        # Pattern selector
        self._publish_discovery(
            "input_select",
            "led_grid_pattern",
            {
                "name": "LED Pattern",
                "icon": "mdi:led-strip-variant",
                "command_topic": "led/command/pattern",
                "state_topic": "led/status/pattern/current",
                "options_topic": "led/status/pattern/list",
                "value_template": "{{ value_json.name }}",
                "command_template": '{"name": "{{ value }}"}',
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_pattern_select",
                "entity_category": "config",
            },
        )

        # Pattern parameters - numeric
        for param in ["speed", "scale", "intensity"]:
            self._publish_discovery(
                "input_number",
                f"pattern_{param}",
                {
                    "name": f"Pattern {param.title()}",
                    "icon": "mdi:speedometer"
                    if param == "speed"
                    else "mdi:ruler"
                    if param == "scale"
                    else "mdi:brightness-percent",
                    "min": 0.0,
                    "max": 1.0 if param != "speed" else 5.0,
                    "step": 0.1,
                    "mode": "slider",
                    "command_topic": "led/command/params",
                    "state_topic": "led/status/pattern/params",
                    "value_template": "{{ value_json.params." + param + " }}",
                    "command_template": '{"params": {"' + param + '": {{ value }}}}',
                    "retain": True,
                    "device": self.device_info,
                    "unique_id": f"{self.unique_id_prefix}_pattern_{param}",
                    "entity_category": "config",
                },
            )

        # Pattern parameters - select
        for param in ["variation", "color_mode"]:
            self._publish_discovery(
                "input_select",
                f"pattern_{param}",
                {
                    "name": f"Pattern {param.replace('_', ' ').title()}",
                    "icon": "mdi:palette-swatch-variant"
                    if param == "color_mode"
                    else "mdi:shape-plus",
                    "command_topic": "led/command/params",
                    "state_topic": "led/status/pattern/params",
                    "options_topic": f"led/status/pattern/{param}_options",
                    "value_template": "{{ value_json.params." + param + " }}",
                    "command_template": '{"params": {"' + param + '": "{{ value }}"}}',
                    "retain": True,
                    "device": self.device_info,
                    "unique_id": f"{self.unique_id_prefix}_pattern_{param}",
                    "entity_category": "config",
                },
            )

        # Hardware controls
        self._publish_discovery(
            "input_number",
            "led_brightness",
            {
                "name": "LED Brightness",
                "icon": "mdi:brightness-percent",
                "min": 0.0,
                "max": 1.0,
                "step": 0.01,
                "mode": "slider",
                "command_topic": "led/command/hardware",
                "command_template": '{"command": "brightness", "value": {{ value }}}',
                "state_topic": "led/status/hardware/brightness",
                "value_template": "{{ value }}",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_brightness",
                "entity_category": "config",
            },
        )

        # Power switch
        self._publish_discovery(
            "switch",
            "led_power",
            {
                "name": "LED Power",
                "icon": "mdi:power",
                "command_topic": "led/command/power",
                "state_topic": "led/status/hardware/power",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_power",
            },
        )

        # Buttons
        for button_id, config in {
            "reset": ("Reset LEDs", "mdi:restart", "RESET"),
            "clear": ("Clear LEDs", "mdi:led-off", "CLEAR"),
            "stop": ("Stop Pattern", "mdi:stop", "STOP"),
        }.items():
            name, icon, payload = config
            self._publish_discovery(
                "button",
                f"{self.unique_id_prefix}_led_{button_id}",
                {
                    "name": name,
                    "icon": icon,
                    "command_topic": f"led/command/{button_id}",
                    "payload_press": payload,
                    "retain": True,
                    "device": self.device_info,
                    "unique_id": f"{self.unique_id_prefix}_{button_id}",
                },
            )

        # Performance sensors
        self._publish_discovery(
            "sensor",
            f"{self.unique_id_prefix}_fps",
            {
                "name": "FPS",
                "state_topic": "led/status/fps",
                "unit_of_measurement": "FPS",
                "icon": "mdi:speedometer",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_fps",
            },
        )

        # Frame time sensor
        self._publish_discovery(
            "sensor",
            f"{self.unique_id_prefix}_frame_time",
            {
                "name": "Frame Time",
                "state_topic": "led/status/performance/frame_time",
                "unit_of_measurement": "ms",
                "icon": "mdi:timer-outline",
                "state_class": "measurement",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_frame_time",
            },
        )

        # Last reset sensor
        self._publish_discovery(
            "sensor",
            f"{self.unique_id_prefix}_last_reset",
            {
                "name": "Last Reset",
                "state_topic": "led/status/hardware/last_reset",
                "device_class": "timestamp",
                "icon": "mdi:clock-outline",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_last_reset",
            },
        )

        # Status sensors
        self._publish_discovery(
            "binary_sensor",
            f"{self.unique_id_prefix}_pattern_server_status",
            {
                "name": "Pattern Server Status",
                "state_topic": "led/status/pattern_server",
                "payload_on": "online",
                "payload_off": "offline",
                "device_class": "connectivity",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_pattern_server_status",
            },
        )

        self._publish_discovery(
            "binary_sensor",
            f"{self.unique_id_prefix}_controller_status",
            {
                "name": "Controller Status",
                "state_topic": "led/status/led_controller",
                "payload_on": "online",
                "payload_off": "offline",
                "device_class": "connectivity",
                "retain": True,
                "device": self.device_info,
                "unique_id": f"{self.unique_id_prefix}_controller_status",
            },
        )

    def _publish_discovery(self, component: str, object_id: str, config: Dict):
        """Publish a discovery config message"""
        try:
            # Add availability
            config["availability"] = [
                {
                    "topic": "led/status/pattern_server",
                    "payload_available": "online",
                    "payload_not_available": "offline",
                }
            ]

            # Build discovery topic with unique prefix (format: homeassistant/[component]/[node_id]/[object_id]/config)
            # Use the unique prefix for the node_id to avoid conflicts
            topic = f"{self.base_topic}/{component}/{self.unique_id_prefix}/{object_id}/config"
            payload = json.dumps(config)

            # Track this entity for cleanup
            self.published_entities.add((component, object_id))

            print(f"\nPublishing discovery message:")
            print(f"Topic: {topic}")
            print(f"Payload: {json.dumps(config, indent=2)}")

            # Publish with retry
            max_retries = 3
            retry_delay = 1.0  # seconds
            for attempt in range(max_retries):
                try:
                    # Check if client is connected
                    if not self.mqtt_client.is_connected():
                        print(
                            f"MQTT client not connected, waiting... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(retry_delay)
                        continue

                    # Publish with QoS 1 and wait for confirmation
                    result = self.mqtt_client.publish(
                        topic, payload, retain=True, qos=1
                    )
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        print(
                            f"Publish returned error code {result.rc} (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(retry_delay)
                        continue

                    # Wait for the message to be published
                    result.wait_for_publish()
                    print(f"Successfully published discovery message to {topic}")
                    return True

                except Exception as e:
                    print(f"Error publishing to {topic}: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        raise

            print(
                f"Failed to publish discovery message to {topic} after {max_retries} attempts"
            )
            return False

        except Exception as e:
            print(f"Error in _publish_config: {str(e)}")
            return False

    def _publish_with_retry(
        self, topic: str, payload: str, retain: bool = False
    ) -> bool:
        """Publish a message with retry logic"""
        if not self.mqtt_client:
            print(f"MQTT client not initialized, can't publish to {topic}")
            return False

        # Exponential backoff parameters
        max_retries = 5
        base_delay = 0.5  # seconds
        max_delay = 8.0  # seconds

        for attempt in range(max_retries):
            try:
                result = self.mqtt_client.publish(topic, payload, retain=retain)
                if result.rc == 0:
                    return True
                else:
                    print(
                        f"Failed to publish to {topic} (attempt {attempt + 1}/{max_retries}): MQTT error code {result.rc}"
                    )
            except Exception as e:
                print(
                    f"Exception publishing to {topic} (attempt {attempt + 1}/{max_retries}): {e}"
                )

            # Calculate backoff delay with jitter
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = delay * 0.2 * (random.random() * 2 - 1)  # +/- 20% jitter
            sleep_time = max(0.1, delay + jitter)

            print(f"Retrying in {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

        print(f"Failed to publish message to {topic} after {max_retries} attempts")
        return False

    def update_pattern_options(self, patterns: List[Pattern]):
        """Update pattern selection options"""
        try:
            pattern_names = [p.definition().name for p in patterns]
            print(f"Publishing pattern options: {pattern_names}")
            # Publish to both topics for backward compatibility
            self._publish_with_retry(
                "led/status/pattern/list", json.dumps(pattern_names), retain=True
            )
            # Publish to the topic used by the automation
            self._publish_with_retry(
                "homeassistant/input_select/led_grid_pattern/options",
                json.dumps(pattern_names),
                retain=True,
            )
        except Exception as e:
            print(f"Error updating pattern options: {e}")
            traceback.print_exc()

    def update_pattern_variations(self, pattern: Pattern):
        """Update variation options for current pattern"""
        try:
            variation_param = next(
                (p for p in pattern.definition().parameters if p.name == "variation"),
                None,
            )
            if variation_param and "(" in variation_param.description:
                options_str = variation_param.description.split("(")[1].split(")")[0]
                variations = [opt.strip() for opt in options_str.split(",")]
                # Publish to both topics for backward compatibility
                self._publish_with_retry(
                    "led/status/pattern/variation_options",
                    json.dumps(variations),
                    retain=True,
                )
                # Publish to the topic used by the automation
                self._publish_with_retry(
                    "homeassistant/input_select/pattern_variation/options",
                    json.dumps(variations),
                    retain=True,
                )
        except Exception as e:
            print(f"Error updating variation options: {e}")

    def update_color_modes(self, pattern: Pattern):
        """Update color mode options for current pattern"""
        try:
            color_param = next(
                (p for p in pattern.definition().parameters if p.name == "color_mode"),
                None,
            )
            if color_param and "(" in color_param.description:
                options_str = color_param.description.split("(")[1].split(")")[0]
                color_modes = [opt.strip() for opt in options_str.split(",")]
                # Publish to both topics for backward compatibility
                self._publish_with_retry(
                    "led/status/pattern/color_mode_options",
                    json.dumps(color_modes),
                    retain=True,
                )
                # Publish to the topic used by the automation
                self._publish_with_retry(
                    "homeassistant/input_select/pattern_color_mode/options",
                    json.dumps(color_modes),
                    retain=True,
                )
        except Exception as e:
            print(f"Error updating color mode options: {e}")

    def update_pattern_state(self, pattern_name: str, params: Dict[str, Any]):
        """Update pattern and parameter states"""
        # Update pattern selection
        self._publish_with_retry(
            "led/status/pattern/current",
            json.dumps({"name": pattern_name}),
            retain=True,
        )

        # Update parameters
        self._publish_with_retry(
            "led/status/pattern/params", json.dumps({"params": params}), retain=True
        )

    def update_hardware_state(self, state: Dict[str, Any]):
        """Update hardware state"""
        # Update brightness
        self._publish_with_retry(
            "led/status/hardware/brightness", str(state["brightness"]), retain=True
        )

        # Update power state
        self._publish_with_retry(
            "led/status/hardware/power", "ON" if state["power"] else "OFF", retain=True
        )

        # Update last reset time
        self._publish_with_retry(
            "led/status/hardware/last_reset", str(state["last_reset"]), retain=True
        )

    def update_modifier_state(
        self,
        index: int,
        modifier_name: Optional[str],
        enabled: bool,
        params: Dict[str, Any],
    ):
        """Update modifier states"""
        if modifier_name:
            self._publish_with_retry(f"led/status/modifier/{index}/type", modifier_name)
        self._publish_with_retry(
            f"led/status/modifier/{index}/enable", "ON" if enabled else "OFF"
        )
        for param_name, value in params.items():
            self._publish_with_retry(
                f"led/status/modifier/{index}/params/{param_name}", str(value)
            )

    def update_fps(self, fps: float):
        """Update FPS state"""
        self._publish_with_retry("led/status/fps", f"{fps:.1f}")

    def update_component_status(self, component: str, status: str):
        """Update component status"""
        # Map component names to their topic names if needed
        topic_map = {
            "pattern_server": "pattern_server",
            "controller": "led_controller",  # Ensure this matches the discovery topic
        }

        # Get the correct topic name
        topic_name = topic_map.get(component, component)

        # Publish the status
        self._publish_with_retry(f"led/status/{topic_name}", status, retain=True)

    def update_performance_metrics(self, fps: float, frame_time: float):
        """Update performance metrics"""
        self._publish_with_retry(
            "led/status/performance/fps", f"{fps:.1f}", retain=True
        )
        self._publish_with_retry(
            "led/status/performance/frame_time", f"{frame_time * 1000:.1f}", retain=True
        )

    def cleanup_old_entities(self):
        """
        Clean up old entities that are no longer needed.
        This should be called before publishing new discovery messages.
        """
        print("Cleaning up old entities...")

        # List of components to check for cleanup
        components = [
            "sensor",
            "binary_sensor",
            "switch",
            "button",
            "light",
            "select",
            "number",
        ]

        # List of known object IDs that might have been created in previous versions
        known_object_ids = [
            "led_fps",
            "led_frame_time",
            "led_last_reset",
            "pattern_server_status",
            "led_controller_status",
            "led_power",
            "led_reset",
            "led_clear",
            "led_stop",
            "led_grid_pattern",
            "pattern_variation",
            "pattern_color_mode",
            "pattern_speed",
            "pattern_scale",
            "pattern_intensity",
            "led_brightness",
        ]

        # Clean up entities with known IDs
        for component in components:
            for object_id in known_object_ids:
                # Clean up the entity without suffix
                topic = f"{self.base_topic}/{component}/{self.unique_id_prefix}/{object_id}/config"
                self._publish_with_retry(topic, "", retain=True)

                # Clean up entities with the old format (led_grid as node_id)
                topic = f"{self.base_topic}/{component}/led_grid/{object_id}/config"
                self._publish_with_retry(topic, "", retain=True)

        # Wait a moment for the messages to be processed
        time.sleep(1)

        print("Cleanup complete.")
