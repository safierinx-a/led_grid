import json
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt
import time
from server.patterns.base import Pattern
import traceback


class HomeAssistantManager:
    """Manages Home Assistant MQTT discovery and state management"""

    def __init__(self, mqtt_client: mqtt.Client, base_topic: str = "homeassistant"):
        self.mqtt_client = mqtt_client
        self.base_topic = base_topic
        self.device_info = {
            "identifiers": ["led_grid_controller"],
            "name": "LED Grid",
            "model": "WS2812B 24x25",
            "manufacturer": "Custom",
            "sw_version": "1.0.0",
        }

    def publish_discovery(self):
        """Publish Home Assistant MQTT discovery messages"""
        # Pattern selector
        self._publish_discovery(
            "input_select",
            "led_grid_pattern",
            {
                "name": "LED Pattern",
                "icon": "mdi:led-strip-variant",
                "command_topic": "homeassistant/input_select/led_grid_pattern/set",
                "state_topic": "homeassistant/input_select/led_grid_pattern/state",
                "options_topic": "homeassistant/input_select/led_grid_pattern/options",
                "retain": True,
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
                    "max": 1.0,
                    "step": 0.01,
                    "mode": "slider",
                    "command_topic": f"homeassistant/input_number/pattern_{param}/set",
                    "state_topic": f"homeassistant/input_number/pattern_{param}/state",
                    "retain": True,
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
                    "command_topic": f"homeassistant/input_select/pattern_{param}/set",
                    "state_topic": f"homeassistant/input_select/pattern_{param}/state",
                    "options_topic": f"homeassistant/input_select/pattern_{param}/options",
                    "retain": True,
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
                "command_topic": "homeassistant/input_number/led_brightness/set",
                "state_topic": "homeassistant/input_number/led_brightness/state",
                "retain": True,
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
            },
        )

        # Reset button
        self._publish_discovery(
            "button",
            "led_reset",
            {
                "name": "Reset LEDs",
                "icon": "mdi:restart",
                "command_topic": "led/command/reset",
                "payload_press": "RESET",
                "retain": True,
            },
        )

        # Clear button
        self._publish_discovery(
            "button",
            "led_clear",
            {
                "name": "Clear LEDs",
                "icon": "mdi:led-off",
                "command_topic": "led/command/clear",
                "payload_press": "CLEAR",
                "retain": True,
            },
        )

        # Stop button
        self._publish_discovery(
            "button",
            "led_stop",
            {
                "name": "Stop Pattern",
                "icon": "mdi:stop",
                "command_topic": "led/command/stop",
                "payload_press": "STOP",
                "retain": True,
            },
        )

        # Performance sensors
        self._publish_discovery(
            "sensor",
            "led_fps",
            {
                "name": "LED FPS",
                "icon": "mdi:speedometer",
                "state_topic": "led/status/performance/fps",
                "unit_of_measurement": "FPS",
                "retain": True,
            },
        )

        self._publish_discovery(
            "sensor",
            "led_frame_time",
            {
                "name": "LED Frame Time",
                "icon": "mdi:timer-outline",
                "state_topic": "led/status/performance/frame_time",
                "unit_of_measurement": "ms",
                "retain": True,
            },
        )

        self._publish_discovery(
            "sensor",
            "led_last_reset",
            {
                "name": "Last Reset Time",
                "icon": "mdi:clock-outline",
                "state_topic": "led/status/hardware/last_reset",
                "device_class": "timestamp",
                "retain": True,
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

            # Build discovery topic (format: homeassistant/[component]/[node_id]/[object_id]/config)
            topic = f"{self.base_topic}/{component}/led_grid/{object_id}/config"
            payload = json.dumps(config)

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
        """Helper method to publish messages with retry logic"""
        max_retries = 3
        retry_delay = 0.5  # seconds

        for attempt in range(max_retries):
            try:
                if not self.mqtt_client.is_connected():
                    print(
                        f"MQTT client not connected, waiting... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    continue

                result = self.mqtt_client.publish(topic, payload, retain=retain, qos=1)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(
                        f"Publish returned error code {result.rc} (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    continue

                result.wait_for_publish()
                return True

            except Exception as e:
                print(f"Error publishing to {topic}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        print(f"Failed to publish message to {topic} after {max_retries} attempts")
        return False

    def update_pattern_options(self, patterns: List[Pattern]):
        """Update pattern selection options"""
        try:
            pattern_names = [p.definition().name for p in patterns]
            print(f"Publishing pattern options: {pattern_names}")
            self._publish_with_retry(
                "homeassistant/input_select/led_grid_pattern/options",
                json.dumps(pattern_names),
                retain=True,
            )

            # Also update the current state if empty
            self._publish_with_retry(
                "homeassistant/input_select/led_grid_pattern/state",
                pattern_names[0] if pattern_names else "",
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
            "homeassistant/input_select/led_grid_pattern/state",
            pattern_name,
            retain=True,
        )

        # Update parameters
        for param_name, value in params.items():
            if param_name in ["speed", "scale", "intensity"]:
                self._publish_with_retry(
                    f"homeassistant/input_number/pattern_{param_name}/state",
                    str(value),
                    retain=True,
                )
            elif param_name in ["variation", "color_mode"]:
                self._publish_with_retry(
                    f"homeassistant/input_select/pattern_{param_name}/state",
                    str(value),
                    retain=True,
                )

    def update_hardware_state(self, state: Dict[str, Any]):
        """Update hardware state"""
        # Update brightness
        self._publish_with_retry(
            "homeassistant/input_number/led_brightness/state",
            str(state["brightness"]),
            retain=True,
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
        self._publish_with_retry(f"led/status/{component}", status, retain=True)
