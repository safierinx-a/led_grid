#!/usr/bin/env python3

import threading
import time
import queue
import json
import zmq
import traceback
from typing import Optional, Dict, Any, List, Callable
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

    def __init__(self, grid_config: GridConfig, buffer_size: int = 4):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.buffer_size = buffer_size

        # Frame generation state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_id: Optional[str] = None
        self.frame_sequence = 0

        # Frame buffer with priority queue
        self.frame_buffer = queue.PriorityQueue(maxsize=buffer_size)
        self.last_frame_time = time.time()

        # Frame observers list for external components
        self.frame_observers: List[Callable[[Frame], None]] = []
        self.observer_lock = (
            threading.RLock()
        )  # Lock for thread-safe observer management

        # ZMQ setup for frame delivery
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.ROUTER)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set socket options for reliability
        self.frame_socket.setsockopt(zmq.LINGER, 0)  # Don't wait for pending messages
        self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
        self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)  # 100ms timeout
        self.frame_socket.setsockopt(zmq.RCVHWM, 10)  # High water mark for receiving
        self.frame_socket.setsockopt(zmq.SNDHWM, 10)  # High water mark for sending
        self.frame_socket.setsockopt(zmq.RECONNECT_IVL, 100)  # Reconnect interval
        self.frame_socket.setsockopt(
            zmq.RECONNECT_IVL_MAX, 5000
        )  # Max reconnect interval

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
        self.performance_log_interval = (
            5.0  # Log every 5 seconds instead of every second
        )

        # Target frame rate
        self.target_frame_time = 1.0 / 60  # 60 FPS

    def add_frame_observer(self, observer_func: Callable[[Frame], None]) -> None:
        """Add a function to be called with each new frame

        Args:
            observer_func: Function that takes a Frame object as its argument
        """
        with self.observer_lock:
            if observer_func not in self.frame_observers:
                self.frame_observers.append(observer_func)
                print(
                    f"Added frame observer, total observers: {len(self.frame_observers)}"
                )

    def remove_frame_observer(self, observer_func: Callable[[Frame], None]) -> None:
        """Remove a frame observer

        Args:
            observer_func: The observer function to remove
        """
        with self.observer_lock:
            if observer_func in self.frame_observers:
                self.frame_observers.remove(observer_func)
                print(
                    f"Removed frame observer, remaining observers: {len(self.frame_observers)}"
                )

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

                # Notify observers with the new frame
                with self.observer_lock:
                    for observer in self.frame_observers:
                        try:
                            observer(frame)
                        except Exception as e:
                            print(f"Error in frame observer: {e}")
                            traceback.print_exc()

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
                    # Try to add frame to buffer with priority based on sequence
                    try:
                        self.frame_buffer.put_nowait((frame.sequence, frame))
                        self.frame_count += 1
                    except queue.Full:
                        # If buffer is full, drop the oldest frame
                        try:
                            self.frame_buffer.get_nowait()  # Remove oldest frame
                            self.frame_buffer.put_nowait((frame.sequence, frame))
                        except queue.Empty:
                            pass  # If we can't remove old frame, skip new one

                # Performance tracking
                current_time = time.time()
                frame_time = current_time - loop_start
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 100:
                    self.frame_times.pop(0)

                # Print FPS every 5 seconds
                if current_time - self.last_fps_print >= self.performance_log_interval:
                    if self.frame_count > 0:
                        fps = self.frame_count / (current_time - self.last_fps_print)
                        delivered_fps = self.delivered_count / (
                            current_time - self.last_fps_print
                        )
                        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                        print(
                            f"Performance: FPS={fps:.1f}, Delivery={delivered_fps:.1f}, Frame={avg_frame_time * 1000:.1f}ms"
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
        delivery_errors = 0
        max_delivery_errors = 3
        error_reset_interval = 60.0
        last_error_time = time.time()

        while self.is_running:
            try:
                # Wait for frame request
                try:
                    # ROUTER socket automatically adds client identity as first frame
                    # The second frame is the empty delimiter that DEALER adds
                    # Third frame is the actual message
                    parts = self.frame_socket.recv_multipart(flags=zmq.NOBLOCK)

                    # For DEALER->ROUTER pattern, expect identity + empty delimiter + message
                    if len(parts) != 3:
                        print(
                            f"Received invalid request format: {len(parts)} parts, expected 3"
                        )
                        continue

                    identity, delimiter, msg = parts

                    # Confirm the message is READY
                    if msg == b"READY":
                        # Get frame from buffer
                        try:
                            _, frame = self.frame_buffer.get(
                                timeout=0.1
                            )  # Get frame with highest priority
                            if frame:
                                try:
                                    # Send frame with metadata
                                    metadata = {
                                        "seq": frame.sequence,
                                        "pattern_id": frame.pattern_id,
                                        "timestamp": frame.timestamp,
                                        "frame_size": len(frame.data),
                                        "pattern_name": frame.metadata.get(
                                            "pattern_name", ""
                                        ),
                                        "params": frame.metadata.get("params", {}),
                                    }

                                    # Send multipart message back to client
                                    # When sending from ROUTER to DEALER:
                                    # 1. First frame must be client identity (routing frame)
                                    # 2. Second frame should be message type
                                    # 3. Third frame is metadata
                                    # 4. Fourth frame is actual data
                                    self.frame_socket.send_multipart(
                                        [
                                            identity,  # Client identity for routing
                                            b"frame",  # Message type
                                            json.dumps(
                                                metadata
                                            ).encode(),  # Metadata as JSON
                                            frame.data,  # Frame data
                                        ]
                                    )

                                    self.delivered_count += 1
                                    delivery_errors = 0
                                    last_error_time = time.time()
                                except zmq.error.Again:
                                    print("Frame send timeout - client may be slow")
                                    continue
                                except Exception as e:
                                    print(f"Error sending frame: {e}")
                                    delivery_errors += 1
                                    if delivery_errors >= max_delivery_errors:
                                        print(
                                            "Too many delivery errors, attempting to rebind socket..."
                                        )
                                        self._rebind_socket()
                                        delivery_errors = 0
                        except queue.Empty:
                            # No frames available, send empty frame to keep client alive
                            try:
                                metadata = {
                                    "seq": -1,
                                    "pattern_id": None,
                                    "timestamp": time.time_ns(),
                                    "frame_size": 0,
                                    "pattern_name": "",
                                    "params": {},
                                }
                                # Send empty frame with same format
                                self.frame_socket.send_multipart(
                                    [
                                        identity,  # Client identity for routing
                                        b"frame",  # Message type
                                        json.dumps(
                                            metadata
                                        ).encode(),  # Metadata as JSON
                                        bytearray(),  # Empty frame data
                                    ]
                                )
                            except Exception as e:
                                print(f"Error sending empty frame: {e}")

                except zmq.Again:
                    time.sleep(0.001)  # Small sleep when no requests
                    continue

                # Reset error count if enough time has passed
                if time.time() - last_error_time > error_reset_interval:
                    delivery_errors = 0

            except Exception as e:
                print(f"Error in delivery loop: {e}")
                delivery_errors += 1

                if delivery_errors >= max_delivery_errors:
                    print("Too many delivery errors, attempting to rebind socket...")
                    self._rebind_socket()
                    delivery_errors = 0

                time.sleep(0.1)  # Brief sleep on error

    def _rebind_socket(self):
        """Rebind ZMQ socket after errors"""
        try:
            # Close existing socket
            self.frame_socket.close(linger=0)
            time.sleep(0.1)  # Give socket time to close

            # Create new socket
            self.frame_socket = self.zmq_context.socket(zmq.ROUTER)
            self.frame_socket.setsockopt(zmq.LINGER, 0)
            self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)
            self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)
            self.frame_socket.setsockopt(zmq.RCVHWM, 10)
            self.frame_socket.setsockopt(zmq.SNDHWM, 10)
            self.frame_socket.setsockopt(zmq.RECONNECT_IVL, 100)
            self.frame_socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000)

            # Rebind
            zmq_address = f"tcp://*:{self.zmq_port}"
            print(f"Rebinding frame delivery socket to {zmq_address}")
            self.frame_socket.bind(zmq_address)
            print("Socket rebound successfully")
            return True
        except Exception as e:
            print(f"Error rebinding socket: {e}")
            traceback.print_exc()
            return False

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
