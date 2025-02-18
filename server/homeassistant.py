import json
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt
import time


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

    def publish_discovery(self, patterns: List[Dict]):
        """Publish all discovery messages"""
        print(f"\nPublishing Home Assistant MQTT discovery messages...")
        print(f"Found {len(patterns)} patterns")

        # Pattern selection
        self._publish_pattern_select(patterns)

        # Pattern parameters
        for pattern in patterns:
            print(f"\nPublishing config for pattern: {pattern.name}")
            self._publish_pattern_params(pattern)

        # Hardware controls
        print("\nPublishing hardware control configs")
        self._publish_brightness_control()
        self._publish_power_control()
        self._publish_reset_control()

        # Status sensors
        print("\nPublishing status sensor configs")
        self._publish_hardware_sensors()
        self._publish_performance_sensors()
        self._publish_status_sensors()

    def _publish_pattern_select(self, patterns: List[Dict]):
        """Publish pattern selection discovery"""
        config = {
            "name": "Pattern",
            "unique_id": "led_grid_pattern_select",
            "command_topic": "led/command/pattern",
            "command_template": '{"name": "{{ value }}", "params": {}}',
            "state_topic": "led/status/pattern",
            "value_template": "{{ value }}",
            "options": [p.name for p in patterns],
            "icon": "mdi:led-strip-variant",
            "device": self.device_info,
        }
        self._publish_config("select", "led_grid_pattern", config)

    def _publish_pattern_params(self, pattern: Dict):
        """Publish parameter controls for a pattern"""
        for param in pattern.parameters:
            param_id = f"led_grid_{pattern.name}_{param.name}"
            name = f"{pattern.name} {param.name}"

            # Base config
            config = {
                "name": name,
                "unique_id": param_id,
                "command_topic": "led/command/params",
                "command_template": '{"params": {"' + param.name + '": {{ value }}}}',
                "state_topic": f"led/status/params/{param.name}",
                "value_template": "{{ value }}",
                "device": self.device_info,
            }

            if param.type in [float, int]:
                config.update(
                    {
                        "min": param.min_value if param.min_value is not None else 0,
                        "max": param.max_value if param.max_value is not None else 100,
                        "step": 0.1 if param.type == float else 1,
                        "mode": "box",
                    }
                )
                self._publish_config("number", param_id, config)
            elif param.type == bool:
                config.update(
                    {
                        "payload_on": "true",
                        "payload_off": "false",
                        "state_on": "true",
                        "state_off": "false",
                    }
                )
                self._publish_config("switch", param_id, config)
            elif param.type == str:
                if hasattr(param, "description") and "(" in param.description:
                    # Extract options from description if present
                    options_str = param.description.split("(")[1].split(")")[0]
                    config["options"] = [opt.strip() for opt in options_str.split(",")]
                self._publish_config("select", param_id, config)

    def _publish_brightness_control(self):
        """Publish brightness control discovery"""
        config = {
            "name": "LED Brightness",
            "unique_id": "led_grid_brightness",
            "command_topic": "led/command/hardware",
            "command_template": '{"command": "brightness", "value": {{ value }}}',
            "state_topic": "led/status/hardware/brightness",
            "min": 0,
            "max": 255,
            "step": 1,
            "icon": "mdi:brightness-6",
            "device": self.device_info,
        }
        self._publish_config("number", "led_grid_brightness", config)

    def _publish_power_control(self):
        """Publish power control discovery"""
        config = {
            "name": "LED Power",
            "unique_id": "led_grid_power",
            "command_topic": "led/command/hardware",
            "command_template": '{"command": "power", "value": "{{ value }}"}',
            "state_topic": "led/status/hardware/power",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:power",
            "device": self.device_info,
        }
        self._publish_config("switch", "led_grid_power", config)

    def _publish_reset_control(self):
        """Publish reset button discovery"""
        config = {
            "name": "LED Reset",
            "unique_id": "led_grid_reset",
            "command_topic": "led/command/hardware",
            "command_template": '{"command": "reset", "value": true}',
            "icon": "mdi:restart",
            "device": self.device_info,
        }
        self._publish_config("button", "led_grid_reset", config)

    def _publish_hardware_sensors(self):
        """Publish hardware state sensors"""
        # Brightness sensor
        config = {
            "name": "LED Brightness",
            "unique_id": "led_grid_brightness_state",
            "state_topic": "led/status/hardware/brightness",
            "unit_of_measurement": "level",
            "icon": "mdi:brightness-6",
            "device": self.device_info,
        }
        self._publish_config("sensor", "led_grid_brightness_state", config)

        # Power sensor
        config = {
            "name": "LED Power State",
            "unique_id": "led_grid_power_state",
            "state_topic": "led/status/hardware/power",
            "icon": "mdi:power",
            "device": self.device_info,
        }
        self._publish_config("sensor", "led_grid_power_state", config)

    def _publish_performance_sensors(self):
        """Publish performance sensors"""
        # FPS sensor
        config = {
            "name": "LED FPS",
            "unique_id": "led_grid_fps",
            "state_topic": "led/status/performance/fps",
            "unit_of_measurement": "FPS",
            "icon": "mdi:speedometer",
            "device": self.device_info,
        }
        self._publish_config("sensor", "led_grid_fps", config)

        # Frame time sensor
        config = {
            "name": "LED Frame Time",
            "unique_id": "led_grid_frame_time",
            "state_topic": "led/status/performance/frame_time",
            "unit_of_measurement": "ms",
            "icon": "mdi:timer",
            "device": self.device_info,
        }
        self._publish_config("sensor", "led_grid_frame_time", config)

    def _publish_status_sensors(self):
        """Publish system status sensors"""
        components = ["pattern_server", "led_controller"]
        for component in components:
            config = {
                "name": f"{component.replace('_', ' ').title()}",
                "unique_id": f"led_grid_{component}_status",
                "state_topic": f"led/status/{component}",
                "icon": "mdi:check-circle",
                "device": self.device_info,
            }
            self._publish_config("sensor", f"led_grid_{component}", config)

    def _publish_config(self, component: str, object_id: str, config: Dict):
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

    def update_pattern_state(self, pattern_name: str, params: Dict[str, Any]):
        """Update pattern and parameter states"""
        self._publish_with_retry("led/status/pattern", pattern_name)
        for param_name, value in params.items():
            self._publish_with_retry(f"led/status/params/{param_name}", str(value))

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
