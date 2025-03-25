#!/usr/bin/env python3

import threading
import time
import zmq
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
import json

from server.config.grid_config import GridConfig, DEFAULT_CONFIG
from server.patterns.base import Pattern
from server.core.pattern_manager import PatternManager
from server.core.frame_generator import FrameGenerator, Frame


class LEDServer:
    """Main server that coordinates pattern management and frame generation"""

    def __init__(self, grid_config: GridConfig, mqtt_config: Dict[str, Any]):
        # Load environment variables
        load_dotenv()

        # Store configuration
        self.grid_config = grid_config
        self.mqtt_config = mqtt_config
        self.grid_config_lock = threading.RLock()

        # Initialize components
        self.pattern_manager = PatternManager(grid_config, mqtt_config)
        self.frame_generator = FrameGenerator(grid_config)
        self.web_server = None

        # Set up pattern change observer
        self.pattern_manager.add_observer(self._on_pattern_change)

        # Server state
        self.is_running = False

    def _on_pattern_change(
        self,
        pattern: Optional[Pattern],
        params: Dict[str, Any],
        pattern_id: str,
        prev_pattern: Optional[Pattern] = None,
        prev_params: Optional[Dict[str, Any]] = None,
    ):
        """Handle pattern changes"""
        try:
            # Update frame generator with new pattern
            self.frame_generator.set_pattern(pattern, params, pattern_id)

            # Publish pattern change to MQTT
            if self.pattern_manager.mqtt_client:
                self.pattern_manager.mqtt_client.publish(
                    "led/pattern/current",
                    json.dumps(
                        {
                            "pattern": pattern.definition().name if pattern else None,
                            "params": params,
                            "pattern_id": pattern_id,
                        }
                    ),
                )
        except Exception as e:
            print(f"Error handling pattern change: {e}")

    def start(self):
        """Start all components"""
        try:
            print("\nStarting LED Server...")

            # Start pattern manager
            print("\nInitializing Pattern Manager...")
            # First initialize the pattern manager to load patterns
            print("Loading patterns...")
            self.pattern_manager.initialize()

            # Then connect to MQTT
            if not self.pattern_manager.connect_mqtt():
                print("Failed to start Pattern Manager")
                return False
            print("Pattern Manager started successfully")

            # Start frame generator
            print("\nInitializing Frame Generator...")
            self.frame_generator.start()
            print("Frame Generator started successfully")

            self.is_running = True
            print("\nLED Server started successfully")
            return True

        except Exception as e:
            print(f"Error starting server: {e}")
            self.stop()
            return False

    def stop(self):
        """Stop all components"""
        print("\nStopping LED Server...")

        try:
            # Stop frame generator
            print("Stopping Frame Generator...")
            self.frame_generator.stop()

            # Stop pattern manager
            print("Stopping Pattern Manager...")
            self.pattern_manager.stop()

            self.is_running = False
            print("LED Server stopped successfully")

        except Exception as e:
            print(f"Error during shutdown: {e}")

    def run(self):
        """Run the server"""
        if self.start():
            try:
                # Keep main thread alive
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nReceived shutdown signal")
            finally:
                self.stop()


if __name__ == "__main__":
    server = LEDServer(
        DEFAULT_CONFIG,
        {
            "host": os.getenv("MQTT_BROKER", "localhost"),
            "port": int(os.getenv("MQTT_PORT", "1883")),
            "username": os.getenv("MQTT_USER"),
            "password": os.getenv("MQTT_PASSWORD"),
        },
    )
    server.run()
