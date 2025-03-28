#!/usr/bin/env python3

import zmq
import json
import time
import zlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import os
from dotenv import load_dotenv

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

    def __init__(self, grid_config: GridConfig):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.DEALER)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

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

        # Compression stats
        self.compression_stats = {
            "total_frames": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "last_report_time": time.time(),
        }

    def _decompress_frame(
        self, compressed_data: bytearray, original_size: int, is_compressed: bool
    ) -> bytearray:
        """Decompress frame data if it was compressed"""
        if is_compressed:
            print(
                f"Decompressing frame: compressed={len(compressed_data)} bytes, original={original_size} bytes"
            )
            decompressed = zlib.decompress(compressed_data)
            print(f"Decompressed size: {len(decompressed)} bytes")
            return decompressed
        return compressed_data

    def _validate_frame_data(self, data: bytearray, metadata: Dict[str, Any]) -> bool:
        """Validate frame data length and format"""
        expected_size = metadata.get("frame_size", 0)
        if not expected_size:
            print("Invalid frame size in metadata")
            return False

        # For compressed frames, we expect the compressed size
        if metadata.get("is_compressed", False):
            expected_size = metadata.get("compressed_size", 0)
            if not expected_size:
                print("Invalid compressed size in metadata")
                return False

        print(
            f"Validating frame: actual={len(data)} bytes, expected={expected_size} bytes"
        )
        if len(data) != expected_size:
            print(f"Invalid frame data length: {len(data)}, expected: {expected_size}")
            return False

        # Only check RGB format for decompressed data
        if not metadata.get("is_compressed", False):
            if len(data) % 3 != 0:
                print(f"Invalid frame data length (not multiple of 3): {len(data)}")
                return False

        return True

    def _receive_frame(self) -> Optional[Frame]:
        """Receive a frame from the server"""
        try:
            # Send READY message
            self.frame_socket.send(b"READY")

            # Receive frame parts
            msg_type = self.frame_socket.recv()
            if msg_type != b"frame":
                print(f"Unexpected message type: {msg_type}")
                return None

            metadata_json = self.frame_socket.recv()
            frame_data = self.frame_socket.recv()

            try:
                metadata = json.loads(metadata_json.decode())
                print(
                    f"Received frame: compressed={len(frame_data)} bytes, original={metadata.get('frame_size')} bytes, is_compressed={metadata.get('is_compressed', False)}"
                )

                # Update compression stats
                self.compression_stats["total_frames"] += 1
                self.compression_stats["total_compressed_size"] += len(frame_data)
                self.compression_stats["total_original_size"] += metadata["frame_size"]

                # Log compression stats every 5 seconds
                current_time = time.time()
                if current_time - self.compression_stats["last_report_time"] >= 5.0:
                    compression_ratio = (
                        (
                            self.compression_stats["total_original_size"]
                            - self.compression_stats["total_compressed_size"]
                        )
                        / self.compression_stats["total_original_size"]
                        * 100
                    )
                    print(
                        f"Decompression stats: {self.compression_stats['total_frames']} frames, "
                        f"Ratio: {compression_ratio:.1f}%, "
                        f"Original: {self.compression_stats['total_original_size'] / 1024:.1f}KB, "
                        f"Compressed: {self.compression_stats['total_compressed_size'] / 1024:.1f}KB"
                    )
                    self.compression_stats["last_report_time"] = current_time

                # Validate frame data before decompression
                if not self._validate_frame_data(frame_data, metadata):
                    return None

                # Decompress frame data if needed
                frame_data = self._decompress_frame(
                    frame_data,
                    metadata["frame_size"],
                    metadata.get("is_compressed", False),
                )

                # Validate decompressed data
                if not self._validate_frame_data(frame_data, metadata):
                    return None

                return Frame(
                    sequence=metadata["seq"],
                    pattern_id=metadata["pattern_id"],
                    timestamp=metadata["timestamp"],
                    data=bytearray(frame_data),
                    metadata=metadata,
                )
            except json.JSONDecodeError as e:
                print(f"Error decoding metadata: {e}")
                return None
            except Exception as e:
                print(f"Error processing frame: {e}")
                return None

        except zmq.error.Again:
            # No message available
            return None
        except Exception as e:
            print(f"Error receiving frame: {e}")
            return None
