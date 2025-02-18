#!/usr/bin/env python3

import threading
import time
import json
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, List, Tuple, Callable
import os
from dotenv import load_dotenv

from server.patterns.base import Pattern, PatternRegistry
from server.config.grid_config import GridConfig
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
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_id: Optional[str] = None
        self.pattern_lock = threading.RLock()

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
            "last_update": 0,
        }
        self.performance_lock = threading.RLock()

        # Home Assistant integration
        self.ha_manager = HomeAssistantManager(None)  # Will be updated with MQTT client

        # Pattern change callback
        self.on_pattern_change: Optional[
            Callable[[Optional[Pattern], Dict[str, Any], str], None]
        ] = None

    def register_pattern_change_callback(
        self, callback: Callable[[Optional[Pattern], Dict[str, Any], str], None]
    ):
        """Register callback for pattern changes"""
        self.on_pattern_change = callback

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
                if hasattr(self.current_pattern, "_color_buffer"):
                    self.current_pattern._color_buffer.clear()
                if hasattr(self.current_pattern, "trails"):
                    self.current_pattern.trails.clear()

            # Set new pattern
            pattern_class = PatternRegistry.get_pattern(pattern_name)
            if pattern_class:
                print(f"Creating new pattern instance: {pattern_name}")
                self.current_pattern = pattern_class(self.grid_config)
                self.current_params = params or {}
                self.pattern_id = str(time.time_ns())
                print(f"Pattern changed to {pattern_name} with ID {self.pattern_id}")
                print(f"Final params: {self.current_params}")
            else:
                print(f"Pattern {pattern_name} not found in registry")
                self.current_pattern = None
                self.current_params = {}
                self.pattern_id = None
                print("Pattern cleared")

            # Notify frame generator
            if self.on_pattern_change:
                self.on_pattern_change(
                    self.current_pattern, self.current_params, self.pattern_id
                )

            # Update Home Assistant state
            self._update_pattern_state()

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
                if self.on_pattern_change:
                    self.on_pattern_change(
                        self.current_pattern, self.current_params, self.pattern_id
                    )

                # Update Home Assistant state
                self._update_pattern_state()
            else:
                print("No active pattern to update parameters for")

    def set_brightness(self, brightness: int):
        """Set LED brightness"""
        with self.hardware_lock:
            brightness = max(0, min(255, brightness))
            self.hardware_state["brightness"] = brightness
            self._publish_hardware_command("brightness", brightness)
            self._update_hardware_state()

    def set_power(self, power: bool):
        """Set LED power state"""
        with self.hardware_lock:
            self.hardware_state["power"] = power
            self._publish_hardware_command("power", "ON" if power else "OFF")
            self._update_hardware_state()

    def reset_hardware(self):
        """Reset LED hardware"""
        with self.hardware_lock:
            self.hardware_state["last_reset"] = time.time()
            self._publish_hardware_command("reset", True)
            self._update_hardware_state()

    def update_performance(self, fps: float, frame_time: float):
        """Update performance metrics"""
        with self.performance_lock:
            self.performance_state["fps"] = fps
            self.performance_state["frame_time"] = frame_time
            self.performance_state["last_update"] = time.time()
            self._update_performance_state()

    def _publish_hardware_command(self, command: str, value: Any):
        """Publish hardware command to control topic"""
        if self.mqtt_client and self.is_connected:
            try:
                payload = json.dumps({"command": command, "value": value})
                self.mqtt_client.publish(f"led/command/hardware", payload)
            except Exception as e:
                print(f"Error publishing hardware command: {e}")

    def _update_pattern_state(self):
        """Update pattern state in Home Assistant"""
        if self.current_pattern:
            self.ha_manager.update_pattern_state(
                self.current_pattern.definition().name, self.current_params
            )

    def _update_hardware_state(self):
        """Update hardware state in Home Assistant"""
        self.ha_manager.update_hardware_state(self.hardware_state)

    def _update_performance_state(self):
        """Update performance state in Home Assistant"""
        self.ha_manager.update_performance_state(self.performance_state)

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

            # Set up authentication if provided
            if self.mqtt_config.get("username") and self.mqtt_config.get("password"):
                self.mqtt_client.username_pw_set(
                    self.mqtt_config["username"], self.mqtt_config["password"]
                )

            # Connect to broker
            print(
                f"Connecting to MQTT broker at {self.mqtt_config['host']}:{self.mqtt_config.get('port', 1883)}"
            )
            self.mqtt_client.connect(
                self.mqtt_config["host"], self.mqtt_config.get("port", 1883), 60
            )

            # Start MQTT loop
            self.mqtt_client.loop_start()

            # Wait for connection
            timeout = 10
            while timeout > 0 and not self.is_connected:
                time.sleep(0.1)
                timeout -= 0.1

            if not self.is_connected:
                raise Exception("MQTT connection timeout")

            # Subscribe to command topics
            self.mqtt_client.subscribe("led/command/#")

            # Publish discovery information
            self.ha_manager.update_component_status("pattern_server", "online")
            self.ha_manager.publish_discovery(PatternRegistry.list_patterns())

            return True

        except Exception as e:
            print(f"Error connecting to MQTT: {e}")
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client = None
            return False

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
            data = json.loads(msg.payload.decode())

            if msg.topic == "led/command/pattern":
                self.set_pattern(data["name"], data.get("params", {}))

            elif msg.topic == "led/command/params":
                self.update_pattern_params(data["params"])

            elif msg.topic == "led/command/hardware":
                command = data.get("command")
                value = data.get("value")

                if command == "brightness":
                    self.set_brightness(int(value))
                elif command == "power":
                    self.set_power(value == "ON")
                elif command == "reset":
                    self.reset_hardware()

            elif msg.topic == "led/command/list":
                response = {
                    "patterns": PatternRegistry.list_patterns(),
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

    def stop(self):
        """Stop pattern manager and clean up"""
        try:
            self.ha_manager.update_component_status("pattern_server", "shutting_down")

            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

            self.ha_manager.update_component_status("pattern_server", "offline")
        except:
            pass
