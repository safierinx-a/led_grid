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
        self.mqtt_client = mqtt.Client()

        # ZMQ setup for frame data - PUB socket for frame distribution
        self.zmq_context = zmq.Context()
        self.frame_pub_socket = self.zmq_context.socket(zmq.PUB)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set ZMQ socket options
        self.frame_pub_socket.setsockopt(zmq.LINGER, 0)  # Don't wait on close
        self.frame_pub_socket.setsockopt(
            zmq.SNDHWM, 2
        )  # Only keep last 2 frames in queue

        # MQTT settings
        self.mqtt_host = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_user = os.getenv("MQTT_USER")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")

        # Pattern state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.next_pattern: Optional[Pattern] = None
        self.next_params: Dict[str, Any] = {}
        self.pattern_lock = threading.RLock()
        self.pattern_change_pending = False

        # Modifier chain
        self.modifiers: List[Tuple[Modifier, Dict[str, Any]]] = []
        self.modifier_lock = threading.RLock()

        # Frame generation control
        self.is_running = False
        self.frame_thread = None
        self.target_frame_time = 1.0 / 60  # Target 60 FPS
        self.last_frame_time = 0
        self.frame_count = 0
        self.frame_times = []

        # Load patterns and modifiers
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

    def _frame_generation_loop(self):
        """Main frame generation loop - runs at fixed rate"""
        last_fps_print = time.time()
        frame_count = 0

        while self.is_running:
            loop_start = time.time()

            try:
                # Check for pattern change at frame boundary
                if self.pattern_change_pending:
                    self._swap_patterns()

                # Generate frame
                frame_data = None
                try:
                    with self.pattern_lock:
                        if self.current_pattern:
                            # Generate frame
                            pixels = self.current_pattern.generate_frame(
                                self.current_params
                            )

                            # Apply modifiers
                            with self.modifier_lock:
                                for modifier, params in self.modifiers:
                                    pixels = modifier.apply(pixels, params)

                            # Convert to bytes
                            frame_data = bytearray()
                            for pixel in pixels:
                                frame_data.extend([pixel["r"], pixel["g"], pixel["b"]])
                except Exception as e:
                    print(f"Error generating frame: {e}")
                    frame_data = None

                # Send empty frame if no pattern or error
                if frame_data is None:
                    frame_data = bytearray([0] * (self.grid_config.num_pixels * 3))

                # Publish frame with topic "frame"
                try:
                    self.frame_pub_socket.send_multipart(
                        [b"frame", frame_data], flags=zmq.NOBLOCK
                    )
                except zmq.Again:
                    print("Frame publish would block, skipping")

                # Performance tracking
                frame_time = time.time() - loop_start
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 100:
                    self.frame_times.pop(0)
                frame_count += 1

                # Print FPS every second
                current_time = time.time()
                time_since_last_print = current_time - last_fps_print
                if time_since_last_print >= 1.0:
                    if frame_count > 0 and len(self.frame_times) > 0:
                        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                        fps = frame_count / time_since_last_print
                        print(
                            f"Server FPS: {fps:.1f}, Frame time: {avg_frame_time * 1000:.1f}ms"
                        )
                    frame_count = 0
                    last_fps_print = current_time

                # Maintain target frame rate
                elapsed = time.time() - loop_start
                if elapsed < self.target_frame_time:
                    time.sleep(self.target_frame_time - elapsed)

            except Exception as e:
                print(f"Error in frame generation loop: {e}")
                time.sleep(0.001)  # Prevent tight error loop

    def connect(self):
        """Connect to MQTT broker and bind ZMQ socket"""
        try:
            # Create MQTT client with unique ID
            client_id = f"pattern_server_{int(time.time())}"
            print(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Update HomeAssistantManager's MQTT client reference
            self.ha_manager.mqtt_client = self.mqtt_client

            # Set up callbacks
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_message

            # Set up authentication if provided
            if self.mqtt_user and self.mqtt_password:
                print(f"Setting up authentication for user: {self.mqtt_user}")
                self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

            print(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)

            # Start MQTT loop
            self.mqtt_client.loop_start()
            print("MQTT loop started")

            # Wait for connection
            connection_timeout = 10
            start_time = time.time()
            while not hasattr(self, "_mqtt_connected") or not self._mqtt_connected:
                if time.time() - start_time > connection_timeout:
                    raise Exception("MQTT connection timeout")
                time.sleep(0.1)

            print("MQTT connection confirmed")

            # Subscribe to command topics
            print("Subscribing to command topics...")
            self.mqtt_client.subscribe("led/command/#")

            # Bind ZMQ PUB socket
            zmq_address = f"tcp://*:{self.zmq_port}"
            print(f"Binding ZMQ PUB socket at {zmq_address}")
            self.frame_pub_socket.bind(zmq_address)

            # Initial setup
            time.sleep(0.5)  # Allow sockets to settle
            self.ha_manager.update_component_status("pattern_server", "online")
            time.sleep(0.5)
            self.ha_manager.publish_discovery(
                self.list_patterns(), self.list_modifiers()
            )

            print("Initialization complete")
            return True

        except Exception as e:
            print(f"Error connecting to services: {e}")
            self.stop()
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
        """Set next pattern with double buffering for clean transitions"""
        with self.pattern_lock:
            # Clean up old next pattern if exists
            if self.next_pattern:
                if hasattr(self.next_pattern, "_color_buffer"):
                    self.next_pattern._color_buffer.clear()
                if hasattr(self.next_pattern, "trails"):
                    self.next_pattern.trails.clear()

            # Create new pattern
            pattern_class = PatternRegistry.get_pattern(pattern_name)
            if pattern_class:
                self.next_pattern = pattern_class(self.grid_config)
                self.next_params = params or {}
                self.pattern_change_pending = True
                print(f"Queued pattern change to {pattern_name} with params {params}")
            else:
                print(f"Pattern {pattern_name} not found")
                self.next_pattern = None
                self.next_params = {}
                self.pattern_change_pending = True

    def _swap_patterns(self):
        """Swap current and next patterns atomically"""
        with self.pattern_lock:
            # Clean up old pattern
            if self.current_pattern:
                if hasattr(self.current_pattern, "_color_buffer"):
                    self.current_pattern._color_buffer.clear()
                if hasattr(self.current_pattern, "trails"):
                    self.current_pattern.trails.clear()

            # Swap patterns
            self.current_pattern = self.next_pattern
            self.current_params = self.next_params
            self.next_pattern = None
            self.next_params = {}
            self.pattern_change_pending = False

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

    def start(self):
        """Start the pattern server"""
        if not self.is_running:
            self.is_running = True
            self.frame_thread = threading.Thread(target=self._frame_generation_loop)
            self.frame_thread.daemon = True
            self.frame_thread.start()

    def stop(self):
        """Stop the pattern server and clean up"""
        if not self.is_running:
            return

        print("\nInitiating graceful shutdown...")

        try:
            self.ha_manager.update_component_status("pattern_server", "shutting_down")
        except:
            pass

        # Stop frame generation
        self.is_running = False
        if self.frame_thread and self.frame_thread.is_alive():
            self.frame_thread.join(timeout=1.0)

        # Clean up ZMQ
        try:
            self.frame_pub_socket.close(linger=0)
            self.zmq_context.term()
        except:
            pass

        # Clean up MQTT
        try:
            self.ha_manager.update_component_status("pattern_server", "offline")
            time.sleep(0.1)
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except:
            pass

        # Final cleanup
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
