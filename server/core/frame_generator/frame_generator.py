#!/usr/bin/env python3

import threading
import time
import queue
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import numpy as np

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
    """Handles frame generation independently of pattern management and display"""

    def __init__(self, grid_config: GridConfig, buffer_size: int = 2):
        self.grid_config = grid_config
        self.buffer_size = buffer_size

        # Frame generation state
        self.current_pattern: Optional[Pattern] = None
        self.current_params: Dict[str, Any] = {}
        self.pattern_id: Optional[str] = None
        self.frame_sequence = 0

        # Frame buffer
        self.frame_buffer = queue.Queue(maxsize=buffer_size)

        # Threading control
        self.is_running = False
        self.generation_thread = None
        self.generation_lock = threading.RLock()

        # Performance tracking
        self.frame_times: List[float] = []
        self.last_fps_print = time.time()
        self.frame_count = 0

        # Target frame rate
        self.target_frame_time = 1.0 / 60  # 60 FPS

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
                        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                        print(
                            f"Generation FPS: {fps:.1f}, Frame time: {avg_frame_time * 1000:.1f}ms"
                        )
                    self.frame_count = 0
                    self.last_fps_print = current_time

                # Maintain target frame rate
                elapsed = time.time() - loop_start
                if elapsed < self.target_frame_time:
                    time.sleep(self.target_frame_time - elapsed)

            except Exception as e:
                print(f"Error in generation loop: {e}")
                time.sleep(0.001)  # Brief sleep on error

    def get_frame(self, timeout: float = 0.1) -> Optional[Frame]:
        """Get the next frame, optionally waiting up to timeout seconds"""
        try:
            return self.frame_buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    def start(self):
        """Start frame generation"""
        if not self.is_running:
            self.is_running = True
            self.generation_thread = threading.Thread(target=self._generation_loop)
            self.generation_thread.daemon = True
            self.generation_thread.start()

    def stop(self):
        """Stop frame generation"""
        self.is_running = False
        if self.generation_thread and self.generation_thread.is_alive():
            self.generation_thread.join(timeout=1.0)
