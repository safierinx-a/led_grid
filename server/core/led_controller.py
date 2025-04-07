#!/usr/bin/env python3

import zmq
import json
import time
import zlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import os
from dotenv import load_dotenv
import threading
import traceback

from server.config.grid_config import GridConfig


@dataclass
class Frame:
    """Represents a single frame of animation"""

    sequence: int
    pattern_id: str
    timestamp: int
    data: bytearray
    metadata: Dict[str, Any]


class LEDController:
    """Handles communication with LED controllers"""

    def __init__(self, grid_config: GridConfig, mqtt_config: Dict[str, Any]):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.mqtt_config = mqtt_config
        self.led_strip = None
        self.frame_socket = None
        self.zmq_context = None
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))
        self.running = False
        self.frame_thread = None
        self.frame_lock = threading.Lock()
        self.compression_stats = {
            "total_frames": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "last_compression_ratio": 0.0,
        }
        self.expected_frame_size = grid_config.width * grid_config.height * 3

        # Set socket options for reliability
        self.frame_socket.setsockopt(zmq.LINGER, 0)
        self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)
        self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)
        self.frame_socket.setsockopt(zmq.RCVHWM, 10)
        self.frame_socket.setsockopt(zmq.SNDHWM, 10)
        self.frame_socket.setsockopt(zmq.RECONNECT_IVL, 100)
        self.frame_socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000)

        # Frame tracking
        self.last_frame_sequence = -1
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.missed_frames = 0
        self.last_performance_print = time.time()

        # Performance tracking
        self.frame_times: List[float] = []
        self.last_fps_print = time.time()
        self.delivered_count = 0
        self.performance_log_interval = 5.0

    def _validate_frame_data(
        self, data: bytearray, is_compressed: bool = False
    ) -> bool:
        """Validate frame data with comprehensive checks"""
        try:
            if not data:
                print("Empty frame data received")
                return False

            if is_compressed:
                # For compressed data, just check if it's not empty
                if len(data) == 0:
                    print("Empty compressed frame data")
                    return False
            else:
                # For uncompressed data, check size and format
                if len(data) != self.expected_frame_size:
                    print(
                        f"Invalid frame data length: {len(data)} (expected: {self.expected_frame_size})"
                    )
                    return False

                # Check RGB format (every 3 bytes should be valid RGB values)
                for i in range(0, len(data), 3):
                    if i + 2 >= len(data):
                        print("Invalid RGB data format")
                        return False
                    r, g, b = data[i], data[i + 1], data[i + 2]
                    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                        print(f"Invalid RGB values at position {i}: ({r}, {g}, {b})")
                        return False

            return True

        except Exception as e:
            print(f"Error validating frame data: {e}")
            traceback.print_exc()
            return False

    def _decompress_frame(self, compressed_data: bytearray) -> Optional[bytearray]:
        """Decompress frame data with error handling"""
        try:
            if not self._validate_frame_data(compressed_data, is_compressed=True):
                return None

            # Decompress data
            decompressed_data = zlib.decompress(compressed_data)

            # Validate decompressed data
            if not self._validate_frame_data(decompressed_data, is_compressed=False):
                return None

            return decompressed_data

        except Exception as e:
            print(f"Error decompressing frame: {e}")
            traceback.print_exc()
            return None

    def _receive_frame(self) -> Optional[Frame]:
        """Receive and process a frame with error handling"""
        try:
            # Receive frame parts
            identity = self.frame_socket.recv()
            msg_type = self.frame_socket.recv()
            metadata_json = self.frame_socket.recv()
            compressed_data = self.frame_socket.recv()

            # Parse metadata
            metadata = json.loads(metadata_json.decode())
            if not metadata:
                print("Invalid frame metadata")
                return None

            # Validate compressed data
            if not self._validate_frame_data(compressed_data, is_compressed=True):
                return None

            # Decompress data
            frame_data = self._decompress_frame(compressed_data)
            if not frame_data:
                return None

            # Update compression stats
            self.compression_stats["total_frames"] += 1
            self.compression_stats["total_original_size"] += len(frame_data)
            self.compression_stats["total_compressed_size"] += len(compressed_data)
            self.compression_stats["last_compression_ratio"] = (
                len(compressed_data) / len(frame_data) if len(frame_data) > 0 else 0.0
            )

            # Create frame object
            frame = Frame(
                sequence=metadata.get("sequence", 0),
                pattern_id=metadata.get("pattern_id"),
                timestamp=metadata.get("timestamp", time.time()),
                data=frame_data,
                metadata=metadata,
            )

            return frame

        except Exception as e:
            print(f"Error receiving frame: {e}")
            traceback.print_exc()
            return None

    def _frame_loop(self):
        """Main frame processing loop"""
        while self.running:
            try:
                # Receive frame
                frame = self._receive_frame()
                if not frame:
                    time.sleep(0.01)  # Prevent tight loop on frame receive failure
                    continue

                # Update LED strip
                self._update_led_strip(frame.data)

            except Exception as e:
                print(f"Error in frame loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)  # Prevent tight error loop

    def _update_led_strip(self, frame_data: bytearray):
        """Update LED strip with frame data"""
        try:
            if not self.led_strip:
                print("LED strip not initialized")
                return

            if not self._validate_frame_data(frame_data, is_compressed=False):
                return

            # Update LED strip
            self.led_strip.set_pixels(frame_data)
            self.led_strip.show()

        except Exception as e:
            print(f"Error updating LED strip: {e}")
            traceback.print_exc()
