#!/usr/bin/env python3

import threading
import time
import queue
import json
import zmq
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import os
from dotenv import load_dotenv

from server.patterns.base import Pattern
from server.config.grid_config import GridConfig


@dataclass
class Frame:
    """Represents a single frame of animation"""

    sequence: int
    pattern_id: str
    timestamp: int
    data: bytearray
    metadata: Dict[str, Any]


class FrameGenerator:
    """Handles frame generation and delivery to LED controllers"""

    def __init__(self, grid_config: GridConfig, buffer_size: int = 2):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.buffer_size = buffer_size

        # Frame generation state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_id: Optional[str] = None
        self.frame_sequence = 0

        # Frame buffer
        self.frame_buffer = queue.Queue(maxsize=buffer_size)

        # ZMQ setup for frame delivery
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.ROUTER)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set socket options
        self.frame_socket.setsockopt(zmq.LINGER, 0)
        self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
        self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)  # 100ms timeout

        # Threading control
        self.is_running = False
        self.generation_thread = None
        self.delivery_thread = None
        self.generation_lock = threading.RLock()

        # Performance tracking
        self.frame_times: List[float] = []
        self.last_fps_print = time.time()
        self.frame_count = 0
        self.delivered_count = 0

        # Target frame rate
        self.target_frame_time = 1.0 / 60  # 60 FPS

    def bind_zmq(self):
        """Bind ZMQ socket for frame delivery"""
        try:
            zmq_address = f"tcp://*:{self.zmq_port}"
            print(f"Binding frame delivery socket to {zmq_address}")
            self.frame_socket.bind(zmq_address)
            return True
        except Exception as e:
            print(f"Error binding ZMQ socket: {e}")
            return False

    def set_pattern(
        self, pattern: Optional[Pattern], params: Dict[str, Any], pattern_id: str
    ):
        """Update the current pattern with thread safety"""
        with self.generation_lock:
            self.current_pattern = pattern
            self.current_params = (
                params.copy()
            )  # Make a copy to prevent external modification
            self.pattern_id = pattern_id
            self.frame_sequence = 0  # Reset sequence for new pattern

            # Clear frame buffer
            while not self.frame_buffer.empty():
                try:
                    self.frame_buffer.get_nowait()
                except queue.Empty:
                    break

    def _generate_frame(self) -> Optional[Frame]:
        """Generate a single frame with error handling"""
        try:
            with self.generation_lock:
                if not self.current_pattern:
                    return None

                # Generate frame
                pixels = self.current_pattern.generate_frame(self.current_params)

                # Convert to bytes
                frame_data = bytearray()
                for pixel in pixels:
                    frame_data.extend([pixel["r"], pixel["g"], pixel["b"]])

                # Create frame object
                frame = Frame(
                    sequence=self.frame_sequence,
                    pattern_id=self.pattern_id,
                    timestamp=time.time_ns(),
                    data=frame_data,
                    metadata={
                        "frame_size": len(frame_data),
                        "pattern_name": self.current_pattern.definition().name,
                        "params": self.current_params,
                    },
                )

                self.frame_sequence += 1
                return frame

        except Exception as e:
            print(f"Error generating frame: {e}")
            return None

    def _generation_loop(self):
        """Main frame generation loop"""
        while self.is_running:
            loop_start = time.time()

            try:
                # Generate frame
                frame = self._generate_frame()

                if frame:
                    # Try to add frame to buffer, skip if full
                    try:
                        self.frame_buffer.put_nowait(frame)
                        self.frame_count += 1
                    except queue.Full:
                        pass  # Skip frame if buffer is full

                # Performance tracking
                current_time = time.time()
                frame_time = current_time - loop_start
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 100:
                    self.frame_times.pop(0)

                # Print FPS every second
                if current_time - self.last_fps_print >= 1.0:
                    if self.frame_count > 0:
                        fps = self.frame_count / (current_time - self.last_fps_print)
                        delivered_fps = self.delivered_count / (
                            current_time - self.last_fps_print
                        )
                        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                        print(
                            f"Generation FPS: {fps:.1f}, Delivery FPS: {delivered_fps:.1f}, Frame time: {avg_frame_time * 1000:.1f}ms"
                        )
                    self.frame_count = 0
                    self.delivered_count = 0
                    self.last_fps_print = current_time

                # Maintain target frame rate
                elapsed = time.time() - loop_start
                if elapsed < self.target_frame_time:
                    time.sleep(self.target_frame_time - elapsed)

            except Exception as e:
                print(f"Error in generation loop: {e}")
                time.sleep(0.001)  # Brief sleep on error

    def _delivery_loop(self):
        """Frame delivery loop"""
        while self.is_running:
            try:
                # Wait for frame request
                try:
                    identity, msg = self.frame_socket.recv_multipart(flags=zmq.NOBLOCK)
                    if msg == b"READY":
                        # Get frame from buffer
                        frame = self.frame_buffer.get(timeout=0.1)
                        if frame:
                            # Send frame with metadata
                            metadata = {
                                "seq": frame.sequence,
                                "pattern_id": frame.pattern_id,
                                "timestamp": frame.timestamp,
                                "frame_size": len(frame.data),
                            }
                            self.frame_socket.send_multipart(
                                [
                                    identity,
                                    b"frame",
                                    json.dumps(metadata).encode(),
                                    frame.data,
                                ]
                            )
                            self.delivered_count += 1

                except zmq.Again:
                    time.sleep(0.001)  # Small sleep when no requests
                    continue

            except Exception as e:
                print(f"Error in delivery loop: {e}")
                time.sleep(0.001)

    def start(self):
        """Start frame generation and delivery"""
        if not self.is_running:
            # Bind ZMQ socket
            if not self.bind_zmq():
                return False

            self.is_running = True

            # Start generation thread
            self.generation_thread = threading.Thread(target=self._generation_loop)
            self.generation_thread.daemon = True
            self.generation_thread.start()

            # Start delivery thread
            self.delivery_thread = threading.Thread(target=self._delivery_loop)
            self.delivery_thread.daemon = True
            self.delivery_thread.start()

            return True

    def stop(self):
        """Stop frame generation and delivery"""
        self.is_running = False

        # Stop generation thread
        if self.generation_thread and self.generation_thread.is_alive():
            self.generation_thread.join(timeout=1.0)

        # Stop delivery thread
        if self.delivery_thread and self.delivery_thread.is_alive():
            self.delivery_thread.join(timeout=1.0)

        # Clean up ZMQ
        try:
            self.frame_socket.close()
            self.zmq_context.term()
        except:
            pass
