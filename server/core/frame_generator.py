#!/usr/bin/env python3

import threading
import time
import queue
import json
import zmq
import traceback
import zlib
from typing import Optional, Dict, Any, List, Callable, Tuple
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

    def __init__(self, grid_config: GridConfig, pattern_manager: PatternManager):
        self.grid_config = grid_config
        self.pattern_manager = pattern_manager

        # Frame generation state
        self.frame_sequence = 0
        self.last_frame_time = 0
        self.target_fps = 24
        self.frame_interval = 1.0 / self.target_fps
        self.next_frame_time = time.time()

        # Threading control
        self.running = False
        self.frame_thread = None
        self.frame_lock = threading.Lock()
        self.generation_lock = threading.RLock()

        # Buffer management
        self.frame_buffer = []
        self.max_buffer_size = 10
        self.current_buffer = queue.PriorityQueue(maxsize=self.max_buffer_size)
        self.next_buffer = queue.PriorityQueue(maxsize=self.max_buffer_size)
        self.buffer_lock = threading.RLock()

        # Pattern state
        self.current_pattern_id = None
        self.pattern_transition = False
        self.transition_start_time = 0
        self.transition_duration = 0.5
        self.transition_lock = threading.RLock()

        # Frame tracking
        self.last_frame = None
        self.current_frame = None
        self.interpolation_factor = 0.0
        self.interpolation_step = 1.0 / self.target_fps

        # Performance tracking
        self.frame_times = []
        self.max_frame_times = 100
        self.frame_generation_times = []
        self.max_generation_times = 100
        self.last_performance_report = time.time()
        self.performance_report_interval = 5.0

        # Network optimization
        self.network_latency = 0
        self.network_samples = []
        self.max_network_samples = 50
        self.last_network_check = time.time()
        self.network_check_interval = 0.5

        # Frame dropping control
        self.drop_count = 0
        self.last_drop_time = time.time()
        self.drop_reset_interval = 1.0
        self.max_drops_per_second = 3
        self.frame_drop_threshold = 0.1

        # Compression stats
        self.compression_stats = {
            "total_frames": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "last_compression_ratio": 0.0,
        }

        # ZMQ setup
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
            while not self.current_buffer.empty():
                try:
                    self.current_buffer.get_nowait()
                except queue.Empty:
                    break

            # Generate and send an immediate frame for pattern change
            if pattern:
                frame = self._generate_frame()
                if frame:
                    try:
                        # Force this frame to be the next one sent
                        self.current_buffer.put_nowait(
                            (-1, frame)
                        )  # Use -1 as priority to ensure it's next
                    except queue.Full:
                        # If buffer is full, clear it and try again
                        while not self.current_buffer.empty():
                            try:
                                self.current_buffer.get_nowait()
                            except queue.Empty:
                                break
                        self.current_buffer.put_nowait((-1, frame))

    def _interpolate_frames(self, frame1: Frame, frame2: Frame, factor: float) -> Frame:
        """Interpolate between two frames with bounds checking"""
        if not frame1 or not frame2:
            return frame2 if frame2 else frame1

        # Validate frame sizes
        if len(frame1.data) != len(frame2.data):
            print(
                f"Warning: Frame size mismatch: {len(frame1.data)} vs {len(frame2.data)}"
            )
            return frame2

        # Validate interpolation factor
        factor = max(0.0, min(1.0, factor))

        # Create interpolated frame
        interpolated = bytearray()
        for i in range(0, len(frame1.data), 3):
            r1, g1, b1 = frame1.data[i : i + 3]
            r2, g2, b2 = frame2.data[i : i + 3]

            # Linear interpolation with bounds checking
            r = max(0, min(255, int(r1 + (r2 - r1) * factor)))
            g = max(0, min(255, int(g1 + (g2 - g1) * factor)))
            b = max(0, min(255, int(b1 + (b2 - b1) * factor)))

            interpolated.extend([r, g, b])

        return Frame(
            sequence=frame2.sequence,
            pattern_id=frame2.pattern_id,
            timestamp=frame2.timestamp,
            data=interpolated,
            metadata=frame2.metadata,
        )

    def _generate_frame(self) -> Optional[Frame]:
        """Generate a single frame with proper error handling"""
        try:
            with self.generation_lock:
                # Get current pattern ID from pattern manager
                pattern_id = self.pattern_manager.get_current_pattern_id()
                if not pattern_id:
                    print("No current pattern ID available")
                    return None

                # Get current pattern from pattern manager
                pattern = self.pattern_manager.get_pattern(pattern_id)
                if not pattern:
                    print(f"Pattern not found for ID: {pattern_id}")
                    return None

                # Get pattern parameters
                params = self.pattern_manager.get_pattern_params(pattern_id)
                if not params:
                    print(f"No parameters available for pattern: {pattern_id}")
                    return None

                # Generate frame data
                frame_data = pattern.generate_frame(params)
                if not frame_data:
                    print(f"Failed to generate frame data for pattern: {pattern_id}")
                    return None

                # Validate frame data size
                expected_size = self.grid_config.width * self.grid_config.height * 3
                if len(frame_data) != expected_size:
                    print(
                        f"Invalid frame data size: {len(frame_data)} (expected: {expected_size})"
                    )
                    return None

                # Create frame with metadata
                frame = Frame(
                    sequence=self.frame_sequence,
                    pattern_id=pattern_id,
                    timestamp=time.time(),
                    data=frame_data,
                    metadata={
                        "frame_size": len(frame_data),
                        "pattern_name": pattern.definition().name,
                        "params": params,
                    },
                )

                # Increment frame sequence
                self.frame_sequence += 1
                return frame

        except Exception as e:
            print(f"Error generating frame: {e}")
            traceback.print_exc()
            return None

    def _handle_buffer_full(self, frame: Frame, buffer: queue.PriorityQueue) -> bool:
        """Handle buffer full condition with smart frame dropping"""
        current_time = time.time()

        # Reset counter if enough time has passed
        if current_time - self.last_buffer_full_time > self.buffer_full_reset_interval:
            self.buffer_full_count = 0
            self.last_buffer_full_time = current_time

        self.buffer_full_count += 1

        if self.buffer_full_count >= self.max_buffer_full_count:
            # Force buffer clear and frame drop
            while not buffer.empty():
                try:
                    buffer.get_nowait()
                except queue.Empty:
                    break
            self.buffer_full_count = 0
            return False

        # Try to drop oldest frame
        try:
            buffer.get_nowait()  # Remove oldest frame
            buffer.put((frame.sequence, frame), timeout=0.001)
            return True
        except queue.Empty:
            return False

    def _adapt_timing(self):
        """Adapt frame timing based on performance metrics"""
        current_time = time.time()
        if current_time - self.last_adaptation < self.adaptation_interval:
            return

        if not self.frame_times:
            return

        avg_frame_time = sum(self.frame_times) / len(self.frame_times)

        # Adjust interval based on performance
        if avg_frame_time > self.target_frame_time * 1.1:
            # We're falling behind, reduce interval
            self.adaptive_interval = max(
                self.min_interval, self.adaptive_interval * 0.95
            )
        elif avg_frame_time < self.target_frame_time * 0.9:
            # We're ahead, increase interval
            self.adaptive_interval = min(
                self.max_interval, self.adaptive_interval * 1.05
            )

        self.last_adaptation = current_time
        self.frame_times.clear()

    def _synchronize_frames(self):
        """Synchronize frame delivery with precise timing"""
        current_time = time.time()

        # Calculate time until next frame
        time_until_next = self.next_frame_time - current_time

        if time_until_next > 0:
            # If we're early, sleep precisely
            if time_until_next > self.sync_window:
                time.sleep(time_until_next)
            # If we're within sync window, adjust timing
            else:
                self.sync_offset = time_until_next
                self.sync_samples.append(self.sync_offset)
                if len(self.sync_samples) > self.max_sync_samples:
                    self.sync_samples.pop(0)

                # Calculate average offset
                avg_offset = sum(self.sync_samples) / len(self.sync_samples)
                self.next_frame_time += avg_offset

    def _check_network_health(self):
        """Monitor and optimize network performance"""
        current_time = time.time()
        if current_time - self.last_network_check < self.network_check_interval:
            return

        # Calculate network latency from frame delivery times
        if self.frame_generation_times:
            avg_latency = sum(self.frame_generation_times) / len(
                self.frame_generation_times
            )
            self.network_samples.append(avg_latency)
            if len(self.network_samples) > self.max_network_samples:
                self.network_samples.pop(0)

            self.network_latency = sum(self.network_samples) / len(self.network_samples)

            # Adjust buffer size based on network latency
            if self.network_latency > self.target_frame_time * 1.5:
                # Network is slow, increase buffer
                self.buffer_size = min(self.buffer_size + 1, 8)
            elif self.network_latency < self.target_frame_time * 0.5:
                # Network is fast, decrease buffer
                self.buffer_size = max(self.buffer_size - 1, 2)

        self.last_network_check = current_time

    def _generation_loop(self):
        """Enhanced frame generation loop with perfect timing"""
        while self.running:
            try:
                current_time = time.time()
                frame_start_time = current_time

                # Check for pattern changes
                pattern_id = self.pattern_manager.get_current_pattern_id()
                with self.transition_lock:
                    if pattern_id != self.current_pattern_id:
                        self.pattern_transition = True
                        self.transition_start_time = current_time
                        self.current_pattern_id = pattern_id

                # Generate frame if it's time
                if current_time >= self.next_frame_time:
                    frame = self._generate_frame()
                    if frame:
                        # Track generation time
                        generation_time = time.time() - frame_start_time
                        self.frame_times.append(generation_time)
                        if len(self.frame_times) > self.max_frame_times:
                            self.frame_times.pop(0)

                        # Smart frame dropping
                        if (
                            generation_time
                            > self.target_frame_time * self.frame_drop_threshold
                        ):
                            current_time = time.time()
                            if (
                                current_time - self.last_drop_time
                                > self.drop_reset_interval
                            ):
                                self.drop_count = 0
                                self.last_drop_time = current_time

                            if self.drop_count < self.max_drops_per_second:
                                self.drop_count += 1
                                print(
                                    f"Warning: Frame generation took {generation_time * 1000:.1f}ms"
                                )
                                continue
                            else:
                                print("Too many frame drops, forcing catchup")
                                self.next_frame_time = current_time
                                continue

                        # Update frame tracking
                        self.last_frame = self.current_frame
                        self.current_frame = frame
                        self.interpolation_factor = 0.0

                        # Add to appropriate buffer with smart handling
                        try:
                            target_buffer = (
                                self.current_buffer
                                if pattern_id == self.current_pattern_id
                                else self.next_buffer
                            )
                            target_buffer.put((frame.sequence, frame), timeout=0.001)
                        except queue.Full:
                            if not self._handle_buffer_full(frame, target_buffer):
                                print("Failed to add frame to buffer")
                                continue

                    # Update timing with adaptive interval
                    self.next_frame_time = current_time + self.adaptive_interval

                # Report performance metrics
                if (
                    current_time - self.last_performance_report
                    >= self.performance_report_interval
                ):
                    avg_generation_time = (
                        sum(self.frame_generation_times)
                        / len(self.frame_generation_times)
                        if self.frame_generation_times
                        else 0
                    )
                    print(
                        f"Performance: Avg frame generation time: {avg_generation_time * 1000:.1f}ms, Network latency: {self.network_latency * 1000:.1f}ms"
                    )
                    self.last_performance_report = current_time

                # Sleep briefly to prevent CPU hogging
                time.sleep(0.001)

            except Exception as e:
                print(f"Error in generation loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)

    def _compress_frame(
        self, frame_data: bytearray
    ) -> Tuple[bytearray, Dict[str, Any]]:
        """Compress frame data and return compressed data with metadata"""
        try:
            # Compress frame data
            compressed_data = zlib.compress(frame_data, level=6)

            # Prepare metadata
            metadata = {
                "original_size": len(frame_data),
                "compressed_size": len(compressed_data),
                "compression_ratio": len(compressed_data) / len(frame_data)
                if len(frame_data) > 0
                else 0.0,
            }

            return compressed_data, metadata

        except Exception as e:
            print(f"Error compressing frame: {e}")
            traceback.print_exc()
            return frame_data, {
                "original_size": len(frame_data),
                "compressed_size": len(frame_data),
                "compression_ratio": 1.0,
            }

    def _send_frame(
        self, frame: Frame, compressed_data: bytearray, metadata: Dict[str, Any]
    ):
        """Send frame with proper error handling"""
        try:
            # Prepare frame parts
            identity = b"led_controller"  # Default identity for now
            msg_type = b"frame"
            metadata_json = json.dumps(metadata).encode()

            # Send frame parts
            self.frame_socket.send(identity, zmq.SNDMORE)
            self.frame_socket.send(msg_type, zmq.SNDMORE)
            self.frame_socket.send(metadata_json, zmq.SNDMORE)
            self.frame_socket.send(compressed_data)

        except Exception as e:
            print(f"Error sending frame: {e}")
            traceback.print_exc()
            raise

    def _delivery_loop(self):
        """Main frame delivery loop with proper timing control"""
        while self.running:
            try:
                # Generate frame
                frame = self._generate_frame()
                if not frame:
                    time.sleep(0.01)  # Prevent tight loop on frame generation failure
                    continue

                # Compress frame data
                compressed_data, metadata = self._compress_frame(frame.data)

                # Update compression stats
                self.compression_stats["total_frames"] += 1
                self.compression_stats["total_original_size"] += len(frame.data)
                self.compression_stats["total_compressed_size"] += len(compressed_data)
                self.compression_stats["last_compression_ratio"] = metadata[
                    "compression_ratio"
                ]

                # Send frame
                self._send_frame(frame, compressed_data, metadata)

                # Control frame rate
                current_time = time.time()
                elapsed = current_time - self.last_frame_time
                if elapsed < self.frame_interval:
                    time.sleep(self.frame_interval - elapsed)
                self.last_frame_time = time.time()

            except Exception as e:
                print(f"Error in delivery loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)  # Prevent tight error loop

    def start(self):
        """Start frame generation and delivery"""
        if not self.running:
            # Bind ZMQ socket
            if not self.bind_zmq():
                return False

            self.running = True

            # Start generation thread
            self.frame_thread = threading.Thread(target=self._generation_loop)
            self.frame_thread.daemon = True
            self.frame_thread.start()

            # Start delivery thread
            self.delivery_thread = threading.Thread(target=self._delivery_loop)
            self.delivery_thread.daemon = True
            self.delivery_thread.start()

            return True

    def stop(self):
        """Stop frame generation and delivery"""
        self.running = False

        # Stop generation thread
        if self.frame_thread and self.frame_thread.is_alive():
            self.frame_thread.join(timeout=1.0)

        # Stop delivery thread
        if self.delivery_thread and self.delivery_thread.is_alive():
            self.delivery_thread.join(timeout=1.0)

        # Clean up ZMQ
        try:
            self.frame_socket.close()
            self.zmq_context.term()
        except:
            pass
