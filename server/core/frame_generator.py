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
        last_frame_time = time.time()
        frame_interval = 1.0 / 60.0  # Target 60 FPS
        min_sleep = 0.001  # Minimum sleep time to prevent busy waiting
        max_sleep = 0.016  # Maximum sleep time (1/60th of a second)

        while self.is_running:
            try:
                current_time = time.time()
                elapsed = current_time - last_frame_time

                # Generate frame if enough time has passed
                if elapsed >= frame_interval:
                    frame = self._generate_frame()
                    if frame:
                        # Try to add frame to buffer with priority based on sequence
                        try:
                            self.frame_buffer.put_nowait((frame.sequence, frame))
                            self.frame_count += 1
                            last_frame_time = current_time
                        except queue.Full:
                            # If buffer is full, drop the oldest frame
                            try:
                                self.frame_buffer.get_nowait()  # Remove oldest frame
                                self.frame_buffer.put_nowait((frame.sequence, frame))
                            except queue.Empty:
                                pass  # If we can't remove old frame, skip new one

                # Performance tracking
                if frame:
                    frame_time = time.time() - current_time
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
                        avg_frame_time = (
                            sum(self.frame_times) / len(self.frame_times)
                            if self.frame_times
                            else 0
                        )
                        print(
                            f"Performance: FPS={fps:.1f}, Delivery={delivered_fps:.1f}, Frame={avg_frame_time * 1000:.1f}ms"
                        )
                    self.frame_count = 0
                    self.delivered_count = 0
                    self.last_fps_print = current_time

                # Adaptive sleep based on frame generation time
                sleep_time = max(0, min(max_sleep, frame_interval - elapsed))
                if sleep_time > min_sleep:
                    time.sleep(sleep_time)

            except Exception as e:
                print(f"Error in generation loop: {e}")
                time.sleep(min_sleep)  # Brief sleep on error

    def _delivery_loop(self):
        """Frame delivery loop"""
        delivery_errors = 0
        max_delivery_errors = 3
        error_reset_interval = 60.0
        last_error_time = time.time()
        min_sleep = 0.001  # Minimum sleep time
        max_sleep = 0.016  # Maximum sleep time (1/60th of a second)
        empty_frame_count = 0
        max_empty_frames = 3  # Maximum number of empty frames to send before waiting

        while self.is_running:
            try:
                # Wait for frame request with timeout
                try:
                    identity, msg = self.frame_socket.recv_multipart(flags=zmq.NOBLOCK)
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
                                    delivery_errors = 0
                                    last_error_time = time.time()
                                    empty_frame_count = 0  # Reset empty frame counter
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
                            # Handle empty buffer
                            if empty_frame_count < max_empty_frames:
                                # Send empty frame to keep client alive
                                try:
                                    metadata = {
                                        "seq": -1,
                                        "pattern_id": None,
                                        "timestamp": time.time_ns(),
                                        "frame_size": 0,
                                    }
                                    self.frame_socket.send_multipart(
                                        [
                                            identity,
                                            b"frame",
                                            json.dumps(metadata).encode(),
                                            bytearray(),
                                        ]
                                    )
                                    empty_frame_count += 1
                                except Exception as e:
                                    print(f"Error sending empty frame: {e}")
                            else:
                                # Wait a bit longer if we've sent too many empty frames
                                time.sleep(max_sleep)
                                empty_frame_count = 0

                except zmq.Again:
                    # No requests, sleep briefly
                    time.sleep(min_sleep)
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

                time.sleep(min_sleep)  # Brief sleep on error

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
