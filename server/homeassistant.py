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
        # Pattern selection
        self._publish_pattern_select(patterns)

        # Pattern parameters
        for pattern in patterns:
            self._publish_pattern_params(pattern)

        # Modifier slots
        for i in range(4):  # Support up to 4 modifier slots
            self._publish_modifier_select(i, modifiers)
            self._publish_modifier_enable(i)

        # System sensors
        self._publish_fps_sensor()
        self._publish_status_sensors()

    def _publish_pattern_select(self, patterns: List[Dict]):
        """Publish pattern selection discovery"""
        config = {
            "name": "LED Grid Pattern",
            "unique_id": "led_grid_pattern",
            "command_topic": "led/command/pattern",
            "state_topic": "led/status/pattern",
            "options": [p.name for p in patterns],
            "icon": "mdi:led-strip-variant",
            "device": self.device_info,
        }
        self._publish_config("select/led_grid/pattern/config", config)

    def _publish_pattern_params(self, pattern: Dict):
        """Publish parameter controls for a pattern"""
        for param in pattern.parameters:
            param_id = f"pattern_{pattern.name}_{param.name}"
            config = {
                "name": f"{pattern.name} {param.name}",
                "unique_id": param_id,
                "command_topic": f"led/command/params/{param.name}",
                "state_topic": f"led/status/params/{param.name}",
                "device": self.device_info,
            }

            if param.type in [float, int]:
                config.update(
                    {
                        "min": param.min_value if param.min_value is not None else 0,
                        "max": param.max_value if param.max_value is not None else 100,
                        "step": 0.1 if param.type == float else 1,
                    }
                )
                self._publish_config(f"number/led_grid/{param_id}/config", config)
            elif param.type == bool:
                self._publish_config(f"switch/led_grid/{param_id}/config", config)
            elif param.type == str and hasattr(param, "options"):
                config["options"] = param.options
                self._publish_config(f"select/led_grid/{param_id}/config", config)

    def _publish_modifier_select(self, index: int, modifiers: List[Dict]):
        """Publish modifier slot selection"""
        config = {
            "name": f"LED Grid Modifier {index + 1}",
            "unique_id": f"led_grid_modifier_{index}",
            "command_topic": f"led/command/modifier/{index}/type",
            "state_topic": f"led/status/modifier/{index}/type",
            "options": [m.name for m in modifiers],
            "icon": "mdi:blur",
            "device": self.device_info,
        }
        self._publish_config(f"select/led_grid/modifier_{index}/config", config)

    def _publish_modifier_enable(self, index: int):
        """Publish modifier enable switch"""
        config = {
            "name": f"LED Grid Modifier {index + 1} Enable",
            "unique_id": f"led_grid_modifier_{index}_enable",
            "command_topic": f"led/command/modifier/{index}/enable",
            "state_topic": f"led/status/modifier/{index}/enable",
            "icon": "mdi:toggle-switch",
            "device": self.device_info,
        }
        self._publish_config(f"switch/led_grid/modifier_{index}_enable/config", config)

    def _publish_fps_sensor(self):
        """Publish FPS sensor"""
        config = {
            "name": "LED Grid FPS",
            "unique_id": "led_grid_fps",
            "state_topic": "led/status/fps",
            "unit_of_measurement": "FPS",
            "icon": "mdi:speedometer",
            "device": self.device_info,
        }
        self._publish_config("sensor/led_grid/fps/config", config)

    def _publish_status_sensors(self):
        """Publish system status sensors"""
        components = ["pattern_server", "led_controller"]
        for component in components:
            config = {
                "name": f"LED Grid {component.replace('_', ' ').title()}",
                "unique_id": f"led_grid_{component}",
                "state_topic": f"led/status/{component}",
                "icon": "mdi:check-circle",
                "device": self.device_info,
            }
            self._publish_config(f"sensor/led_grid/{component}/config", config)

    def _publish_config(self, discovery_topic: str, config: Dict):
        """Publish a discovery config message"""
        topic = f"{self.base_topic}/{discovery_topic}"
        self.mqtt_client.publish(topic, json.dumps(config), retain=True)

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
