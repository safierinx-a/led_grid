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

        # Enhanced timing control
        self.target_fps = 24
        self.target_frame_time = 1.0 / self.target_fps
        self.frame_interval = 1.0 / self.target_fps
        self.next_frame_time = time.time()
        self.last_frame_time = time.time()
        self.frame_drop_threshold = 0.1  # Drop frame if generation takes too long
        self.max_frame_lag = 3  # Maximum frames to lag before forcing catchup

        # Adaptive timing
        self.frame_times = []
        self.max_frame_times = 100
        self.adaptive_interval = self.frame_interval
        self.min_interval = self.frame_interval * 0.8
        self.max_interval = self.frame_interval * 1.2
        self.last_adaptation = time.time()
        self.adaptation_interval = 1.0  # Adapt every second

        # Frame synchronization
        self.sync_window = 0.001  # 1ms sync window
        self.last_sync_time = time.time()
        self.sync_offset = 0
        self.sync_samples = []
        self.max_sync_samples = 50

        # Enhanced buffer management
        self.current_buffer = queue.PriorityQueue(maxsize=buffer_size)
        self.next_buffer = queue.PriorityQueue(maxsize=buffer_size)
        self.buffer_lock = threading.RLock()
        self.buffer_full_count = 0
        self.max_buffer_full_count = 3
        self.buffer_full_reset_interval = 5.0
        self.last_buffer_full_time = time.time()

        # Smart frame dropping
        self.drop_count = 0
        self.last_drop_time = time.time()
        self.drop_reset_interval = 1.0
        self.max_drops_per_second = 3

        # Pattern transition state
        self.pattern_transition = False
        self.transition_start_time = 0
        self.transition_duration = 0.5  # 500ms transition
        self.transition_lock = threading.RLock()

        # Performance monitoring
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
        self.frame_count = 0
        self.delivered_count = 0
        self.performance_log_interval = 5.0

        # Frame interpolation
        self.last_frame = None
        self.current_frame = None
        self.interpolation_factor = 0.0
        self.interpolation_step = 1.0 / self.target_fps

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
        """Generate a single frame"""
        try:
            with self.generation_lock:
                # Get current pattern and parameters
                pattern_id = self.pattern_manager.get_current_pattern_id()
                pattern = self.pattern_manager.get_pattern(pattern_id)
                params = self.pattern_manager.get_pattern_params(pattern_id)
                display_state = self.pattern_manager.get_display_state()

                # Generate frame data
                pixels = pattern.generate_frame(params, display_state)
                if not pixels:
                    return None

                # Convert to bytearray
                frame_data = bytearray()
                for pixel in pixels:
                    frame_data.extend([pixel["r"], pixel["g"], pixel["b"]])

                # Create frame object
                frame = Frame(
                    sequence=self.pattern_manager.get_frame_sequence(),
                    pattern_id=pattern_id,
                    timestamp=time.time_ns(),
                    data=frame_data,
                    metadata={
                        "pattern_name": pattern.name,
                        "params": params,
                        "display_state": display_state,
                    },
                )

                # Update frame sequence
                self.pattern_manager.increment_frame_sequence()

                return frame

        except Exception as e:
            print(f"Error generating frame: {e}")
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
        while self.is_running:
            try:
                current_time = time.time()
                frame_start_time = current_time

                # Adapt timing based on performance
                self._adapt_timing()

                # Check network health
                self._check_network_health()

                # Synchronize frame delivery
                self._synchronize_frames()

                # Check for pattern changes
                pattern_id = self.pattern_manager.get_current_pattern_id()
                with self.transition_lock:
                    if pattern_id != self.current_pattern_id:
                        self.pattern_transition = True
                        self.transition_start_time = current_time
                        self.current_pattern_id = pattern_id
                        # Clear next buffer
                        while not self.next_buffer.empty():
                            try:
                                self.next_buffer.get_nowait()
                            except queue.Empty:
                                break

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

    def _compress_frame(self, frame_data: bytearray) -> bytearray:
        """Compress frame data"""
        return zlib.compress(frame_data, level=6)

    def _delivery_loop(self):
        """Enhanced frame delivery loop with better error handling"""
        delivery_errors = 0
        max_delivery_errors = 3
        error_reset_interval = 60.0
        last_error_time = time.time()
        last_empty_frame_time = 0
        empty_frame_interval = 1.0
        last_frame_time = time.time()
        consecutive_timeouts = 0
        max_consecutive_timeouts = 5

        while self.is_running:
            try:
                try:
                    # Receive the message with identity frame from DEALER
                    identity = self.frame_socket.recv(flags=zmq.NOBLOCK)
                    msg = self.frame_socket.recv(flags=zmq.NOBLOCK)

                    if msg == b"READY":
                        current_time = time.time()

                        # Ensure we maintain target frame rate
                        if current_time - last_frame_time < self.target_frame_time:
                            time.sleep(
                                self.target_frame_time
                                - (current_time - last_frame_time)
                            )
                            continue

                        try:
                            with self.buffer_lock:
                                priority, frame = self.current_buffer.get(timeout=0.001)

                            if frame:
                                try:
                                    # Handle pattern transition
                                    with self.transition_lock:
                                        if self.pattern_transition:
                                            transition_progress = min(
                                                1.0,
                                                (
                                                    current_time
                                                    - self.transition_start_time
                                                )
                                                / self.transition_duration,
                                            )
                                            if transition_progress >= 1.0:
                                                self.pattern_transition = False
                                            else:
                                                # Interpolate between patterns
                                                frame = self._interpolate_frames(
                                                    self.last_frame,
                                                    frame,
                                                    transition_progress,
                                                )

                                    # Interpolate between frames if needed
                                    if self.last_frame and self.current_frame:
                                        self.interpolation_factor += (
                                            self.interpolation_step
                                        )
                                        if self.interpolation_factor >= 1.0:
                                            self.interpolation_factor = 0.0
                                        frame = self._interpolate_frames(
                                            self.last_frame,
                                            frame,
                                            self.interpolation_factor,
                                        )

                                    # Compress and send frame
                                    compressed_data = self._compress_frame(frame.data)
                                    self._send_frame(identity, frame, compressed_data)

                                    last_frame_time = time.time()
                                    self.frame_count += 1
                                    delivery_errors = 0
                                    consecutive_timeouts = 0
                                    last_error_time = time.time()

                                except zmq.error.Again:
                                    consecutive_timeouts += 1
                                    if consecutive_timeouts >= max_consecutive_timeouts:
                                        print(
                                            "Too many consecutive timeouts, attempting to recover..."
                                        )
                                        self._rebind_socket()
                                        consecutive_timeouts = 0
                                    continue
                                except Exception as e:
                                    print(f"Error sending frame: {e}")
                                    traceback.print_exc()
                                    delivery_errors += 1
                                    if delivery_errors >= max_delivery_errors:
                                        print(
                                            "Too many delivery errors, attempting to rebind socket..."
                                        )
                                        self._rebind_socket()
                                        delivery_errors = 0

                        except queue.Empty:
                            self._handle_empty_buffer(
                                current_time,
                                last_empty_frame_time,
                                identity,
                                empty_frame_interval,
                            )

                except zmq.error.Again:
                    time.sleep(0.001)

                # Reset error count if enough time has passed
                if time.time() - last_error_time > error_reset_interval:
                    delivery_errors = 0

            except Exception as e:
                print(f"Error in delivery loop: {e}")
                traceback.print_exc()
                delivery_errors += 1
                if delivery_errors >= max_delivery_errors:
                    print("Too many delivery errors, attempting to rebind socket...")
                    self._rebind_socket()
                    delivery_errors = 0
                time.sleep(0.1)

    def _send_frame(self, identity: bytes, frame: Frame, compressed_data: bytearray):
        """Send frame with proper error handling"""
        try:
            metadata = {
                "seq": frame.sequence,
                "pattern_id": frame.pattern_id,
                "timestamp": time.time_ns(),
                "frame_size": len(frame.data),
                "compressed_size": len(compressed_data),
                "pattern_name": frame.metadata.get("pattern_name", ""),
                "params": frame.metadata.get("params", {}),
                "display_state": frame.metadata.get("display_state", {}),
            }

            # Send frame parts
            self.frame_socket.send(identity, zmq.SNDMORE)
            self.frame_socket.send(b"frame", zmq.SNDMORE)
            self.frame_socket.send(json.dumps(metadata).encode(), zmq.SNDMORE)
            self.frame_socket.send(compressed_data)
        except Exception as e:
            print(f"Error sending frame: {e}")
            raise

    def _handle_empty_buffer(
        self,
        current_time: float,
        last_empty_frame_time: float,
        identity: bytes,
        empty_frame_interval: float,
    ):
        """Handle empty buffer situation"""
        if current_time - last_empty_frame_time >= empty_frame_interval:
            try:
                empty_frame = bytearray(
                    [0] * (self.grid_config.width * self.grid_config.height * 3)
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

                self._send_frame(
                    identity,
                    Frame(-1, None, time.time_ns(), empty_frame, metadata),
                    compressed_empty,
                )
                last_empty_frame_time = current_time
            except Exception as e:
                print(f"Error sending empty frame: {e}")
                traceback.print_exc()

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
