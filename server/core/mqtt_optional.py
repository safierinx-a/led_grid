"""
Optional MQTT client for the LED grid.

This module provides a wrapper around MQTT that can gracefully handle
missing MQTT brokers.
"""

import os
import paho.mqtt.client as mqtt


class OptionalMQTT:
    """Wrapper around MQTT client that gracefully handles missing brokers."""

    def __init__(self, mqtt_config, required=False):
        """
        Initialize the optional MQTT client.

        Args:
            mqtt_config: MQTT configuration dictionary
            required: If True, will raise exceptions on connection failure
        """
        self.mqtt_config = mqtt_config
        self.client = None
        self.is_connected = False
        self.required = required
        self.enabled = os.getenv("MQTT_ENABLED", "true").lower() in ("true", "1", "yes")

    def connect(self):
        """Attempt to connect to MQTT broker, handling failure gracefully."""
        if not self.enabled:
            print("MQTT is disabled by environment variable MQTT_ENABLED")
            return True

        try:
            # Create MQTT client with unique ID
            import time

            client_id = f"pattern_manager_{int(time.time())}"
            print(f"Creating MQTT client with ID: {client_id}")
            self.client = mqtt.Client(client_id=client_id)

            # Set up authentication if provided
            if self.mqtt_config.get("username") and self.mqtt_config.get("password"):
                self.client.username_pw_set(
                    self.mqtt_config["username"], self.mqtt_config["password"]
                )

            # Connect to broker
            print(
                f"Connecting to MQTT broker at {self.mqtt_config['host']}:{self.mqtt_config.get('port', 1883)}"
            )
            self.client.connect(
                self.mqtt_config["host"], self.mqtt_config.get("port", 1883), 60
            )

            # Start MQTT loop in background thread
            self.client.loop_start()
            self.is_connected = True
            return True

        except Exception as e:
            print(f"MQTT connection failed: {e}")
            if self.required:
                raise
            return False

    def publish(self, topic, payload, qos=0, retain=False):
        """Publish a message to a topic."""
        if not self.enabled or not self.is_connected or not self.client:
            # Silently ignore if MQTT is not available
            return False

        try:
            self.client.publish(topic, payload, qos, retain)
            return True
        except Exception as e:
            print(f"MQTT publish error: {e}")
            return False

    def subscribe(self, topic, qos=0):
        """Subscribe to a topic."""
        if not self.enabled or not self.is_connected or not self.client:
            # Silently ignore if MQTT is not available
            return False

        try:
            self.client.subscribe(topic, qos)
            return True
        except Exception as e:
            print(f"MQTT subscribe error: {e}")
            return False

    def set_callback(self, callback_type, callback_function):
        """Set a callback for the MQTT client."""
        if not self.enabled or not self.client:
            # Silently ignore if MQTT is not available
            return False

        try:
            setattr(self.client, callback_type, callback_function)
            return True
        except Exception as e:
            print(f"MQTT callback error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        if self.client and self.is_connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except:
                pass
            finally:
                self.is_connected = False
