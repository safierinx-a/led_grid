#!/usr/bin/env python3

import time
import json
import importlib
import pkgutil
import threading
from typing import Dict, Any, Optional, List, Tuple
import paho.mqtt.client as mqtt
import zmq  # Add ZMQ import
import math
import signal
import os
from dotenv import load_dotenv

from server.config.grid_config import GridConfig, DEFAULT_CONFIG
from server.patterns.base import Pattern, PatternRegistry
from server.modifiers.base import Modifier, ModifierRegistry
from server.homeassistant import HomeAssistantManager

# Load environment variables
load_dotenv()


class PatternServer:
    def __init__(self, grid_config: GridConfig = DEFAULT_CONFIG):
        self.grid_config = grid_config

        # MQTT client for control commands
        self.mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)  # Use MQTT v5 protocol

        # ZMQ setup for frame data
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.ROUTER)  # Change to ROUTER
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # MQTT settings
        self.mqtt_host = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_user = os.getenv("MQTT_USER")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")

        # Current pattern state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_lock = threading.Lock()  # Add lock for pattern state

        # Modifier chain
        self.modifiers: List[Tuple[Modifier, Dict[str, Any]]] = []
        self.modifier_lock = threading.Lock()  # Add lock for modifier chain

        # Thread control
        self.is_running = False
        self.update_thread = None

        # Memory management
        self.frame_count = 0
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # Cleanup every 60 seconds

        # Load all patterns and modifiers
        self._load_patterns()
        self._load_modifiers()

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        # Home Assistant integration
        self.ha_manager = HomeAssistantManager(self.mqtt_client)

    def _load_patterns(self):
        """Dynamically load all pattern modules"""
        import server.patterns as patterns

        package = patterns

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"server.patterns.{name}")

    def _load_modifiers(self):
        """Dynamically load all modifier modules"""
        import server.modifiers as modifiers

        package = modifiers

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            if name != "base":
                importlib.import_module(f"server.modifiers.{name}")

    def connect(self):
        """Connect to MQTT broker and bind ZMQ socket"""
        try:
            # Create MQTT client with unique ID
            client_id = f"pattern_server_{int(time.time())}"
            print(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt.Client(client_id=client_id)  # Remove MQTTv5 for now

            # Update HomeAssistantManager's MQTT client reference
            self.ha_manager.mqtt_client = self.mqtt_client

            # Set up callbacks
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_publish = self.on_mqtt_publish

            # Set up authentication if provided
            if self.mqtt_user and self.mqtt_password:
                print(f"Setting up authentication for user: {self.mqtt_user}")
                self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

            print(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)

            # Start the loop
            self.mqtt_client.loop_start()
            print("MQTT loop started")

            # Wait for connection to be established
            connection_timeout = 10  # seconds
            start_time = time.time()
            while not hasattr(self, "_mqtt_connected") or not self._mqtt_connected:
                if time.time() - start_time > connection_timeout:
                    raise Exception("MQTT connection timeout")
                time.sleep(0.1)

            print("MQTT connection confirmed")

            # Subscribe to command topics
            print("Subscribing to command topics...")
            self.mqtt_client.subscribe("led/command/#")

            # Bind ZMQ socket for frame data
            zmq_address = f"tcp://0.0.0.0:{self.zmq_port}"
            print(f"Binding ZMQ socket at {zmq_address}")
            self.zmq_socket.bind(zmq_address)

            # Wait a moment for everything to settle
            time.sleep(0.5)

            # Initial status update
            print("Publishing initial status...")
            self.ha_manager.update_component_status("pattern_server", "online")

            # Wait another moment for status to propagate
            time.sleep(0.5)

            # Publish Home Assistant discovery
            print("Publishing Home Assistant discovery messages...")
            self.ha_manager.publish_discovery(
                self.list_patterns(), self.list_modifiers()
            )

            print("Initialization complete")
            return True

        except Exception as e:
            print(f"Error connecting to services: {e}")
            self.stop()  # Clean up if connection fails
            raise

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        rc_codes = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorised",
        }

        if rc == 0:
            print(f"Connected to MQTT broker successfully (rc={rc})")
            self._mqtt_connected = True
        else:
            error_message = rc_codes.get(rc, f"Unknown error code {rc}")
            print(f"Failed to connect to MQTT broker: {error_message}")
            self._mqtt_connected = False

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        print(f"Disconnected from MQTT broker with code {rc}")
        self._mqtt_connected = False

    def on_mqtt_publish(self, client, userdata, mid):
        """Handle MQTT publish confirmation"""
        print(f"Message {mid} published successfully")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            print(f"Received message on topic: {msg.topic}")
            data = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic == "led/command/pattern":
                self.set_pattern(data["name"], data.get("params", {}))
                self.ha_manager.update_pattern_state(
                    data["name"], data.get("params", {})
                )

            elif topic == "led/command/params":
                self.update_pattern_params(data["params"])
                if self.current_pattern:
                    self.ha_manager.update_pattern_state(
                        self.current_pattern.definition().name, self.current_params
                    )

            elif topic == "led/command/modifier/add":
                self.add_modifier(data["name"], data.get("params", {}))
                # Update modifier state in HA
                for i, (modifier, params) in enumerate(self.modifiers):
                    self.ha_manager.update_modifier_state(
                        i, modifier.definition().name, True, params
                    )

            elif topic == "led/command/modifier/remove":
                index = data["index"]
                self.remove_modifier(index)
                self.ha_manager.update_modifier_state(index, None, False, {})

            elif topic == "led/command/modifier/clear":
                self.clear_modifiers()
                for i in range(4):
                    self.ha_manager.update_modifier_state(i, None, False, {})

            elif topic == "led/command/modifier/params":
                self.update_modifier_params(data["index"], data["params"])
                if 0 <= data["index"] < len(self.modifiers):
                    modifier, params = self.modifiers[data["index"]]
                    self.ha_manager.update_modifier_state(
                        data["index"], modifier.definition().name, True, params
                    )

            elif topic == "led/command/list":
                # Send back pattern and modifier information
                response = {
                    "patterns": self.list_patterns(),
                    "modifiers": self.list_modifiers(),
                    "current_pattern": self.current_pattern.definition().name
                    if self.current_pattern
                    else None,
                    "current_modifiers": [
                        (m.definition().name, p) for m, p in self.modifiers
                    ],
                }
                self.mqtt_client.publish("led/status/list", json.dumps(response))

            elif topic == "led/command/stop":
                self.set_pattern(None)

            elif topic == "led/command/clear":
                self.mqtt_client.publish("led/pixels", json.dumps({"command": "clear"}))

        except Exception as e:
            print(f"Error handling command: {e}")
            print(f"Message payload: {msg.payload}")

    def set_pattern(self, pattern_name: str, params: Dict[str, Any] = None):
        """Set current pattern with cleanup of old pattern"""
        with self.pattern_lock:  # Protect pattern state changes
            # Clean up old pattern
            if self.current_pattern:
                if hasattr(self.current_pattern, "_color_buffer"):
                    self.current_pattern._color_buffer.clear()
                if hasattr(self.current_pattern, "trails"):
                    self.current_pattern.trails.clear()

            # Create new pattern
            pattern_class = PatternRegistry.get_pattern(pattern_name)
            if pattern_class:
                self.current_pattern = pattern_class(self.grid_config)
                self.current_params = params or {}
                print(f"Set pattern to {pattern_name} with params {params}")
            else:
                print(f"Pattern {pattern_name} not found")

    def add_modifier(self, modifier_name: str, params: Dict[str, Any] = None):
        """Add a modifier to the chain"""
        with self.modifier_lock:  # Protect modifier chain changes
            modifier_class = ModifierRegistry.get_modifier(modifier_name)
            if modifier_class:
                modifier = modifier_class(self.grid_config)
                self.modifiers.append((modifier, params or {}))
                print(f"Added modifier {modifier_name} with params {params}")
            else:
                print(f"Modifier {modifier_name} not found")

    def remove_modifier(self, index: int):
        """Remove a modifier from the chain"""
        with self.modifier_lock:  # Protect modifier chain changes
            if 0 <= index < len(self.modifiers):
                modifier, params = self.modifiers.pop(index)
                print(f"Removed modifier at index {index}")

    def clear_modifiers(self):
        """Clear all modifiers"""
        with self.modifier_lock:  # Protect modifier chain changes
            self.modifiers = []
            print("Cleared all modifiers")

    def update_pattern_params(self, params: Dict[str, Any]):
        """Update current pattern parameters"""
        with self.pattern_lock:  # Protect parameter updates
            if self.current_pattern:
                self.current_params.update(params)

    def update_modifier_params(self, index: int, params: Dict[str, Any]):
        """Update modifier parameters"""
        with self.modifier_lock:  # Protect modifier parameter updates
            if 0 <= index < len(self.modifiers):
                modifier, current_params = self.modifiers[index]
                current_params.update(params)
                self.modifiers[index] = (modifier, current_params)

    def send_frame(self, pixels: list):
        """Send frame data to LED controller using optimized format"""
        # Convert to compact format: [index,r,g,b,index,r,g,b,...]
        compact_data = []
        for pixel in pixels:
            compact_data.extend([pixel["index"], pixel["r"], pixel["g"], pixel["b"]])

        message = {"command": "set_pixels_fast", "data": compact_data}
        self.mqtt_client.publish("led/pixels", json.dumps(message), qos=0)

    def cleanup(self):
        """Perform periodic cleanup of resources"""
        try:
            # Clear any accumulated buffers
            if self.current_pattern:
                if hasattr(self.current_pattern, "_color_buffer"):
                    self.current_pattern._color_buffer.clear()
                if hasattr(self.current_pattern, "trails"):
                    self.current_pattern.trails.clear()

            # Clear modifier buffers
            for modifier, _ in self.modifiers:
                if hasattr(modifier, "_buffer"):
                    modifier._buffer.clear()

            # Force garbage collection
            import gc

            gc.collect()

        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _update_loop(self):
        """Main update loop with synchronized frame generation"""
        last_fps_print = time.time()
        frame_count = 0
        frame_times = []

        while self.is_running:
            try:
                # Use poll with timeout to allow for graceful shutdown
                if self.zmq_socket.poll(timeout=1000) == 0:  # 1 second timeout
                    continue

                try:
                    # Get the request - ROUTER socket receives [identity, empty, msg]
                    message = self.zmq_socket.recv_multipart()
                    if len(message) != 3:
                        print(
                            f"Invalid message format, expected 3 parts but got {len(message)}"
                        )
                        continue

                    identity, empty, request = message
                    if request != b"READY":
                        print(f"Invalid request: {request}")
                        continue

                    frame_start = time.time()

                    try:
                        # Generate frame if we have a pattern
                        frame_data = None
                        with self.pattern_lock:  # Lock while accessing pattern
                            if self.current_pattern:
                                # Generate frame
                                pixels = self.current_pattern.generate_frame(
                                    self.current_params
                                )

                                with (
                                    self.modifier_lock
                                ):  # Lock while applying modifiers
                                    # Apply modifiers
                                    for modifier, params in self.modifiers:
                                        pixels = modifier.apply(pixels, params)

                                # Convert to bytes for efficient transmission
                                frame_data = bytearray()
                                for pixel in pixels:
                                    frame_data.extend(
                                        [pixel["r"], pixel["g"], pixel["b"]]
                                    )

                        if frame_data is None:
                            # Send empty frame if no pattern
                            frame_data = bytearray(
                                [0] * (self.grid_config.num_pixels * 3)
                            )

                        # Send response with identity for ROUTER socket
                        self.zmq_socket.send_multipart([identity, empty, frame_data])

                        # Track performance
                        frame_time = time.time() - frame_start
                        frame_times.append(frame_time)
                        if len(frame_times) > 100:
                            frame_times.pop(0)
                        frame_count += 1

                        # Update FPS in Home Assistant
                        current_time = time.time()
                        if current_time - last_fps_print >= 1.0:
                            fps = frame_count / (current_time - last_fps_print)
                            self.ha_manager.update_fps(fps)
                            frame_count = 0
                            last_fps_print = current_time

                    except Exception as e:
                        print(f"Error generating frame: {e}")
                        # Send empty frame on error
                        self.zmq_socket.send_multipart(
                            [
                                identity,
                                empty,
                                bytearray([0] * (self.grid_config.num_pixels * 3)),
                            ]
                        )

                except zmq.Again:
                    continue  # No message available

                # Periodic cleanup if needed
                current_time = time.time()
                if current_time - self.last_cleanup > self.cleanup_interval:
                    self.cleanup()
                    self.last_cleanup = current_time

            except Exception as e:
                if self.is_running:  # Only log errors if we're supposed to be running
                    print(f"Error in update loop: {e}")
                time.sleep(0.01)

    def start(self):
        """Start the pattern server"""
        if not self.is_running:
            self.is_running = True
            self.update_thread = threading.Thread(target=self._update_loop)
            self.update_thread.daemon = True
            self.update_thread.start()

    def stop(self):
        """Stop the pattern server and clean up resources gracefully"""
        if not self.is_running:  # Prevent multiple shutdown attempts
            return

        print("\nInitiating graceful shutdown...")

        # 1. Signal shutdown to Home Assistant
        try:
            self.ha_manager.update_component_status("pattern_server", "shutting_down")
        except:
            pass

        # 2. Set flag to stop update loop
        self.is_running = False

        # 3. Close ZMQ socket first to unblock update thread
        print("Cleaning up ZMQ...")
        try:
            self.zmq_socket.close(linger=0)  # Don't wait for messages
        except:
            pass

        # 4. Wait for update thread to finish
        if self.update_thread and self.update_thread.is_alive():
            print("Waiting for update thread to finish...")
            self.update_thread.join(timeout=1.0)  # Wait up to 1 second

        # 5. Clean up MQTT
        print("Cleaning up MQTT...")
        try:
            # Send offline status
            self.ha_manager.update_component_status("pattern_server", "offline")
            time.sleep(0.1)  # Allow status to be sent
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except:
            pass

        # 6. Terminate ZMQ context
        try:
            self.zmq_context.term()
        except:
            pass

        # 7. Final cleanup
        print("Performing final cleanup...")
        self.cleanup()

        print("Shutdown complete")

    def list_patterns(self):
        """List all available patterns"""
        return PatternRegistry.list_patterns()

    def list_modifiers(self):
        """List all available modifiers"""
        return ModifierRegistry.list_modifiers()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()


if __name__ == "__main__":
    import time

    # Create and start server
    server = PatternServer()
    server.connect()
    server.start()

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
