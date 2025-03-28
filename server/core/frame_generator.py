#!/usr/bin/env python3

import threading
import time
import queue
import json
import zmq
import traceback
import zlib
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
import os
from dotenv import load_dotenv

from server.patterns.base import Pattern
from server.config.grid_config import GridConfig
from server.core.pattern_manager import PatternManager


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

    def __init__(
        self,
        grid_config: GridConfig,
        pattern_manager: PatternManager,
        buffer_size: int = 4,
    ):
        # Load environment variables
        load_dotenv()

        self.grid_config = grid_config
        self.pattern_manager = pattern_manager
        self.buffer_size = buffer_size

        # Frame buffer with priority queue
        self.frame_buffer = queue.PriorityQueue(maxsize=buffer_size)
        self.last_frame_time = time.time()

        # Frame observers list for external components
        self.frame_observers: List[Callable[[Frame], None]] = []
        self.observer_lock = threading.RLock()

        # ZMQ setup for frame delivery
        self.zmq_context = zmq.Context()
        self.frame_socket = self.zmq_context.socket(zmq.ROUTER)
        self.zmq_port = int(os.getenv("ZMQ_PORT", "5555"))

        # Set socket options for reliability
        self.frame_socket.setsockopt(zmq.LINGER, 0)
        self.frame_socket.setsockopt(zmq.RCVTIMEO, 100)
        self.frame_socket.setsockopt(zmq.SNDTIMEO, 100)
        self.frame_socket.setsockopt(zmq.RCVHWM, 10)
        self.frame_socket.setsockopt(zmq.SNDHWM, 10)
        self.frame_socket.setsockopt(zmq.RECONNECT_IVL, 100)
        self.frame_socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000)

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
        self.performance_log_interval = 5.0

        # Target frame rate - reduced to 24 FPS for LED animations
        self.target_fps = 24
        self.target_frame_time = 1.0 / self.target_fps
        self.last_frame_time = time.time()
        self.frame_interval = 1.0 / self.target_fps  # Time between frames
        self.next_frame_time = time.time()  # When to generate next frame

        # Compression stats
        self.compression_stats = {
            "total_frames": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "last_report_time": time.time(),
        }

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

            # Clear frame buffer immediately
            while not self.frame_buffer.empty():
                try:
                    self.frame_buffer.get_nowait()
                except queue.Empty:
                    break

            # Generate and send an immediate frame for pattern change
            if pattern:
                frame = self._generate_frame()
                if frame:
                    try:
                        # Force this frame to be the next one sent
                        self.frame_buffer.put_nowait(
                            (-1, frame)
                        )  # Use -1 as priority to ensure it's next
                    except queue.Full:
                        # If buffer is full, clear it and try again
                        while not self.frame_buffer.empty():
                            try:
                                self.frame_buffer.get_nowait()
                            except queue.Empty:
                                break
                        self.frame_buffer.put_nowait((-1, frame))

    def _generate_frame(self) -> Optional[Frame]:
        """Generate a single frame with error handling"""
        try:
            with self.generation_lock:
                # Get current pattern state from pattern manager
                pattern = self.pattern_manager.current_pattern
                params = self.pattern_manager.current_params.copy()
                pattern_id = self.pattern_manager.pattern_id

                if not pattern:
                    return None

                # Generate frame
                pixels = pattern.generate_frame(params)

                # Convert to bytes
                frame_data = bytearray()
                for pixel in pixels:
                    frame_data.extend([pixel["r"], pixel["g"], pixel["b"]])

                # Get current display state
                with self.pattern_manager.display_lock:
                    display_state = self.pattern_manager.display_state.copy()

                # Create frame object
                frame = Frame(
                    sequence=self.pattern_manager.frame_sequence,
                    pattern_id=pattern_id,
                    timestamp=time.time_ns(),
                    data=frame_data,
                    metadata={
                        "frame_size": len(frame_data),
                        "pattern_name": pattern.definition().name,
                        "params": params,
                        "display_state": display_state,
                    },
                )

                # Increment frame sequence in pattern manager
                self.pattern_manager.frame_sequence += 1

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
            current_time = time.time()

            # Only generate a new frame if it's time
            if current_time >= self.next_frame_time:
                try:
                    # Generate frame
                    frame_start = time.time()
                    frame = self._generate_frame()

                    if frame:
                        # Calculate next frame time based on target FPS
                        self.next_frame_time = current_time + self.frame_interval

                        # Clear any old frames from the buffer
                        while not self.frame_buffer.empty():
                            try:
                                self.frame_buffer.get_nowait()
                            except queue.Empty:
                                break

                        # Add the new frame
                        try:
                            self.frame_buffer.put_nowait((-frame.sequence, frame))
                        except queue.Full:
                            # If buffer is full, clear it and try again
                            while not self.frame_buffer.empty():
                                try:
                                    self.frame_buffer.get_nowait()
                                except queue.Empty:
                                    break
                            self.frame_buffer.put_nowait((-frame.sequence, frame))

                        # Report frame generation time to pattern manager
                        frame_time = time.time() - frame_start
                        self.pattern_manager.update_performance_metrics(frame_time)

                except Exception as e:
                    print(f"Error in generation loop: {e}")
                    traceback.print_exc()

            # Sleep until next frame time, but ensure at least minimal sleep
            sleep_time = self.next_frame_time - time.time()
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.001))
            else:
                time.sleep(0.001)  # Always sleep a tiny amount to prevent CPU hogging

    def _compress_frame(self, frame_data: bytearray) -> bytearray:
        """Compress frame data"""
        return zlib.compress(frame_data, level=6)

    def _delivery_loop(self):
        """Frame delivery loop"""
        delivery_errors = 0
        max_delivery_errors = 3
        error_reset_interval = 60.0
        last_error_time = time.time()
        last_empty_frame_time = 0
        empty_frame_interval = 1.0  # Send empty frames no more than once per second
        last_frame_time = time.time()  # Track last frame delivery time

        while self.is_running:
            try:
                # Wait for frame request
                try:
                    # Receive the message with identity frame from DEALER
                    identity = self.frame_socket.recv(flags=zmq.NOBLOCK)

                    # Receive the actual READY message
                    msg = self.frame_socket.recv(flags=zmq.NOBLOCK)

                    # Check if the message is a frame request
                    if msg == b"READY":
                        current_time = time.time()

                        # Ensure we maintain target frame rate
                        if current_time - last_frame_time < self.target_frame_time:
                            time.sleep(
                                self.target_frame_time
                                - (current_time - last_frame_time)
                            )
                            continue

                        # Get frame from buffer with minimal timeout
                        try:
                            # Try to get newest frame from buffer with a very short timeout
                            priority, frame = self.frame_buffer.get(timeout=0.001)

                            if (
                                frame and len(frame.data) > 0
                            ):  # Only process non-empty frames
                                try:
                                    # Always compress frame data
                                    compressed_data = self._compress_frame(frame.data)

                                    # Update compression stats
                                    self.compression_stats["total_frames"] += 1
                                    self.compression_stats["total_original_size"] += (
                                        len(frame.data)
                                    )
                                    self.compression_stats["total_compressed_size"] += (
                                        len(compressed_data)
                                    )

                                    # Log compression stats every 5 seconds
                                    if (
                                        current_time
                                        - self.compression_stats["last_report_time"]
                                        >= 5.0
                                    ):
                                        compression_ratio = (
                                            (
                                                self.compression_stats[
                                                    "total_original_size"
                                                ]
                                                - self.compression_stats[
                                                    "total_compressed_size"
                                                ]
                                            )
                                            / self.compression_stats[
                                                "total_original_size"
                                            ]
                                            * 100
                                        )
                                        print(
                                            f"Compression stats: {self.compression_stats['total_frames']} frames, "
                                            f"Ratio: {compression_ratio:.1f}%, "
                                            f"Original: {self.compression_stats['total_original_size'] / 1024:.1f}KB, "
                                            f"Compressed: {self.compression_stats['total_compressed_size'] / 1024:.1f}KB"
                                        )
                                        self.compression_stats["last_report_time"] = (
                                            current_time
                                        )

                                    # Prepare metadata
                                    metadata = {
                                        "seq": frame.sequence,
                                        "pattern_id": frame.pattern_id,
                                        "timestamp": time.time_ns(),
                                        "frame_size": len(frame.data),  # Original size
                                        "compressed_size": len(
                                            compressed_data
                                        ),  # Compressed size
                                        "pattern_name": frame.metadata.get(
                                            "pattern_name", ""
                                        ),
                                        "params": frame.metadata.get("params", {}),
                                        "display_state": frame.metadata.get(
                                            "display_state", {}
                                        ),
                                    }

                                    # Send frame back to the client
                                    # First frame must be client identity for routing
                                    self.frame_socket.send(identity, zmq.SNDMORE)
                                    # Then actual message parts
                                    self.frame_socket.send(b"frame", zmq.SNDMORE)
                                    self.frame_socket.send(
                                        json.dumps(metadata).encode(), zmq.SNDMORE
                                    )
                                    self.frame_socket.send(compressed_data)

                                    last_frame_time = time.time()
                                    self.frame_count += 1
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
                            else:
                                # No valid frames available
                                # Only send empty frame if enough time has passed since the last one
                                if (
                                    current_time - last_empty_frame_time
                                    >= empty_frame_interval
                                ):
                                    try:
                                        # Create a minimal valid frame with all pixels black
                                        empty_frame = bytearray(
                                            [0]
                                            * (
                                                self.grid_config.width
                                                * self.grid_config.height
                                                * 3
                                            )
                                        )
                                        compressed_empty = self._compress_frame(
                                            empty_frame
                                        )

                                        metadata = {
                                            "seq": -1,
                                            "pattern_id": None,
                                            "timestamp": time.time_ns(),
                                            "frame_size": len(empty_frame),
                                            "compressed_size": len(compressed_empty),
                                            "pattern_name": "",
                                            "params": {},
                                            "display_state": {},
                                        }
                                        # Send empty frame with same format
                                        self.frame_socket.send(identity, zmq.SNDMORE)
                                        self.frame_socket.send(b"frame", zmq.SNDMORE)
                                        self.frame_socket.send(
                                            json.dumps(metadata).encode(), zmq.SNDMORE
                                        )
                                        self.frame_socket.send(compressed_empty)
                                        last_empty_frame_time = current_time
                                    except Exception as e:
                                        print(f"Error sending empty frame: {e}")
                        except queue.Empty:
                            # No frames available
                            # Only send empty frame if enough time has passed since the last one
                            if (
                                current_time - last_empty_frame_time
                                >= empty_frame_interval
                            ):
                                try:
                                    # Create a minimal valid frame with all pixels black
                                    empty_frame = bytearray(
                                        [0]
                                        * (
                                            self.grid_config.width
                                            * self.grid_config.height
                                            * 3
                                        )
                                    )
                                    compressed_empty = self._compress_frame(empty_frame)

                                    metadata = {
                                        "seq": -1,
                                        "pattern_id": None,
                                        "timestamp": time.time_ns(),
                                        "frame_size": len(empty_frame),
                                        "compressed_size": len(compressed_empty),
                                        "pattern_name": "",
                                        "params": {},
                                        "display_state": {},
                                    }
                                    # Send empty frame with same format
                                    self.frame_socket.send(identity, zmq.SNDMORE)
                                    self.frame_socket.send(b"frame", zmq.SNDMORE)
                                    self.frame_socket.send(
                                        json.dumps(metadata).encode(), zmq.SNDMORE
                                    )
                                    self.frame_socket.send(compressed_empty)
                                    last_empty_frame_time = current_time
                                except Exception as e:
                                    print(f"Error sending empty frame: {e}")
                except zmq.error.Again:
                    # No requests available, sleep briefly
                    time.sleep(0.001)

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
