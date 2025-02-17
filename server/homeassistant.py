import json
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt


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

    def publish_discovery(self, patterns: List[Dict], modifiers: List[Dict]):
        """Publish all discovery messages"""
        print(f"\nPublishing Home Assistant MQTT discovery messages...")
        print(f"Found {len(patterns)} patterns and {len(modifiers)} modifiers")

        # Pattern selection
        self._publish_pattern_select(patterns)

        # Pattern parameters
        for pattern in patterns:
            print(f"\nPublishing config for pattern: {pattern.name}")
            self._publish_pattern_params(pattern)

        # Modifier slots
        for i in range(4):
            print(f"\nPublishing config for modifier slot {i + 1}")
            self._publish_modifier_select(i, modifiers)
            self._publish_modifier_enable(i)

        # System sensors
        print("\nPublishing system sensor configs")
        self._publish_fps_sensor()
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

    def _publish_modifier_select(self, index: int, modifiers: List[Dict]):
        """Publish modifier slot selection"""
        config = {
            "name": f"Modifier {index + 1}",
            "unique_id": f"led_grid_modifier_{index}_select",
            "command_topic": "led/command/modifier/add",
            "command_template": '{"name": "{{ value }}", "params": {}}',
            "state_topic": f"led/status/modifier/{index}/type",
            "value_template": "{{ value }}",
            "options": [m.name for m in modifiers],
            "icon": "mdi:blur",
            "device": self.device_info,
        }
        self._publish_config("select", f"led_grid_modifier_{index}", config)

    def _publish_modifier_enable(self, index: int):
        """Publish modifier enable switch"""
        config = {
            "name": f"Modifier {index + 1} Enable",
            "unique_id": f"led_grid_modifier_{index}_enable",
            "command_topic": f"led/command/modifier/{index}/enable",
            "state_topic": f"led/status/modifier/{index}/enable",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_on": "ON",
            "state_off": "OFF",
            "icon": "mdi:toggle-switch",
            "device": self.device_info,
        }
        self._publish_config("switch", f"led_grid_modifier_{index}_enable", config)

    def _publish_fps_sensor(self):
        """Publish FPS sensor"""
        config = {
            "name": "FPS",
            "unique_id": "led_grid_fps",
            "state_topic": "led/status/fps",
            "unit_of_measurement": "FPS",
            "state_class": "measurement",
            "icon": "mdi:speedometer",
            "device": self.device_info,
        }
        self._publish_config("sensor", "led_grid_fps", config)

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

        result = self.mqtt_client.publish(topic, payload, retain=True)
        if not result.is_published():
            print(f"Failed to publish discovery message to {topic}")
        else:
            print(f"Successfully published discovery message to {topic}")

    def update_pattern_state(self, pattern_name: str, params: Dict[str, Any]):
        """Update pattern and parameter states"""
        self.mqtt_client.publish("led/status/pattern", pattern_name)
        for param_name, value in params.items():
            self.mqtt_client.publish(f"led/status/params/{param_name}", str(value))

    def update_modifier_state(
        self,
        index: int,
        modifier_name: Optional[str],
        enabled: bool,
        params: Dict[str, Any],
    ):
        """Update modifier states"""
        if modifier_name:
            self.mqtt_client.publish(f"led/status/modifier/{index}/type", modifier_name)
        self.mqtt_client.publish(
            f"led/status/modifier/{index}/enable", "ON" if enabled else "OFF"
        )
        for param_name, value in params.items():
            self.mqtt_client.publish(
                f"led/status/modifier/{index}/params/{param_name}", str(value)
            )

    def update_fps(self, fps: float):
        """Update FPS state"""
        self.mqtt_client.publish("led/status/fps", f"{fps:.1f}")

    def update_component_status(self, component: str, status: str):
        """Update component status"""
        self.mqtt_client.publish(f"led/status/{component}", status)
