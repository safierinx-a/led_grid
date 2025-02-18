from datetime import datetime
from typing import Dict, List, Any


class PatternManager:
    def __init__(self, mqtt_client, ha_manager):
        self.mqtt = mqtt_client
        self.ha_manager = ha_manager
        self.patterns = []
        self.current_pattern = None
        self.hardware_state = {
            "brightness": 1.0,
            "power": True,
            "last_reset": datetime.now().isoformat(),
        }
        self.performance_state = {
            "fps": 0.0,
            "frame_time": 0.0,
            "last_frame_time": datetime.now(),
            "frame_count": 0,
            "last_fps_update": datetime.now(),
        }
        self._setup_mqtt_subscriptions()

    def _setup_mqtt_subscriptions(self):
        """Setup MQTT subscriptions for pattern control"""
        # Pattern selection
        self.mqtt.subscribe(
            "homeassistant/input_select/led_grid_pattern/set",
            self._handle_pattern_select,
        )

        # Pattern parameters
        for param in ["speed", "scale", "intensity"]:
            self.mqtt.subscribe(
                f"homeassistant/input_number/pattern_{param}/set",
                lambda msg, param=param: self._handle_numeric_param(param, msg),
            )

        for param in ["variation", "color_mode"]:
            self.mqtt.subscribe(
                f"homeassistant/input_select/pattern_{param}/set",
                lambda msg, param=param: self._handle_select_param(param, msg),
            )

        # Hardware controls
        self.mqtt.subscribe(
            "homeassistant/input_number/led_brightness/set",
            self._handle_brightness_control,
        )
        self.mqtt.subscribe("led/command/power", self._handle_power_control)
        self.mqtt.subscribe("led/command/reset", self._handle_reset_control)
        self.mqtt.subscribe("led/command/clear", self._handle_clear)
        self.mqtt.subscribe("led/command/stop", self._handle_stop)

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
        except Exception as e:
            print(f"Error handling numeric param {param_name}: {e}")

    def _handle_select_param(self, param_name: str, msg):
        """Handle select parameter updates"""
        try:
            value = msg.decode()
            if self.current_pattern:
                self.current_pattern.params[param_name] = value
                self.ha_manager.update_pattern_state(
                    self.current_pattern.name, self.current_pattern.params
                )
        except Exception as e:
            print(f"Error handling select param {param_name}: {e}")

    def _handle_brightness_control(self, msg):
        """Handle brightness control"""
        try:
            brightness = float(msg.decode())
            self.hardware_state["brightness"] = brightness
            self.ha_manager.update_hardware_state(self.hardware_state)
        except Exception as e:
            print(f"Error handling brightness control: {e}")

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
                self.ha_manager.update_pattern_state("", {})
        except Exception as e:
            print(f"Error handling clear command: {e}")

    def _handle_stop(self, msg):
        """Handle stop command"""
        try:
            if msg.decode() == "STOP":
                # Stop pattern and update state
                self.current_pattern = None
                self.ha_manager.update_pattern_state("", {})
        except Exception as e:
            print(f"Error handling stop command: {e}")

    def start(self):
        """Start the pattern manager"""
        # Initialize Home Assistant
        self.ha_manager.publish_discovery()
        self.ha_manager.update_pattern_options(self.patterns)

        # Initialize hardware state
        self.ha_manager.update_hardware_state(self.hardware_state)

        # Start performance monitoring
        self._start_performance_monitoring()

    def _start_performance_monitoring(self):
        """Start monitoring performance metrics"""
        # Initialize performance state
        self.performance_state["fps"] = 0.0
        self.performance_state["frame_time"] = 0.0
        self.performance_state["last_frame_time"] = datetime.now()
        self.performance_state["frame_count"] = 0
        self.performance_state["last_fps_update"] = datetime.now()

    def update_performance_metrics(self, frame_time: float):
        """Update performance metrics with latest frame data"""
        try:
            now = datetime.now()
            self.performance_state["frame_time"] = frame_time
            self.performance_state["frame_count"] += 1

            # Update FPS every second
            time_since_update = (
                now - self.performance_state["last_fps_update"]
            ).total_seconds()
            if time_since_update >= 1.0:
                fps = self.performance_state["frame_count"] / time_since_update
                self.performance_state["fps"] = round(fps, 2)
                self.performance_state["frame_count"] = 0
                self.performance_state["last_fps_update"] = now

                # Publish performance metrics
                self.mqtt.publish(
                    "led/status/performance/fps", str(self.performance_state["fps"])
                )
                self.mqtt.publish(
                    "led/status/performance/frame_time",
                    str(self.performance_state["frame_time"]),
                )
        except Exception as e:
            print(f"Error updating performance metrics: {e}")
