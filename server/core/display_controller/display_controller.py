#!/usr/bin/env python3

import threading
import time
import zmq
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from rpi_ws281x import PixelStrip, Color


@dataclass
class DisplayConfig:
    """LED display configuration"""

    led_count: int = 600  # Total number of LEDs
    led_pin: int = 18  # GPIO pin
    led_freq_hz: int = 800000  # LED signal frequency
    led_dma: int = 10  # DMA channel
    led_brightness: int = 255  # Brightness (0-255)
    led_invert: bool = False  # Invert signal
    led_channel: int = 0  # PWM channel


class DisplayController:
    """Handles LED display independently of pattern management and frame generation"""

    def __init__(self, config: DisplayConfig):
        self.config = config

        # LED strip
        self.strip = None
        self.strip_lock = threading.RLock()

        # Display state
        self.is_running = False
        self.display_thread = None
        self.last_frame_time = time.time()
        self.frame_timeout = 5.0  # seconds

        # Performance tracking
        self.frame_times = []
        self.last_fps_print = time.time()
        self.frame_count = 0

        # Frame callback
        self.get_next_frame: Optional[Callable[[], Optional[bytearray]]] = None

    def register_frame_callback(self, callback: Callable[[], Optional[bytearray]]):
        """Register callback to get next frame"""
        self.get_next_frame = callback

    def init_strip(self):
        """Initialize LED strip with error handling"""
        try:
            with self.strip_lock:
                self.strip = PixelStrip(
                    self.config.led_count,
                    self.config.led_pin,
                    self.config.led_freq_hz,
                    self.config.led_dma,
                    self.config.led_invert,
                    self.config.led_brightness,
                    self.config.led_channel,
                )
                self.strip.begin()
                print("LED strip initialized successfully")
                return True
        except Exception as e:
            print(f"Error initializing LED strip: {e}")
            return False

    def clear_strip(self):
        """Turn off all LEDs"""
        try:
            with self.strip_lock:
                for i in range(self.config.led_count):
                    self.strip.setPixelColor(i, Color(0, 0, 0))
                self.strip.show()
        except Exception as e:
            print(f"Error clearing strip: {e}")

    def update_strip(self, frame_data: bytearray) -> bool:
        """Update LED strip with new frame data"""
        try:
            with self.strip_lock:
                for i in range(self.config.led_count):
                    idx = i * 3
                    if idx + 2 < len(frame_data):
                        r = frame_data[idx]
                        g = frame_data[idx + 1]
                        b = frame_data[idx + 2]
                        self.strip.setPixelColor(i, Color(r, g, b))
                self.strip.show()
                return True
        except Exception as e:
            print(f"Error updating strip: {e}")
            return False

    def _display_loop(self):
        """Main display loop"""
        consecutive_errors = 0
        max_consecutive_errors = 3

        while self.is_running:
            try:
                # Get next frame
                if self.get_next_frame:
                    frame_data = self.get_next_frame()
                    if frame_data:
                        # Update strip
                        frame_start = time.time()
                        if self.update_strip(frame_data):
                            # Performance tracking
                            self.last_frame_time = time.time()
                            frame_time = self.last_frame_time - frame_start
                            self.frame_times.append(frame_time)
                            if len(self.frame_times) > 100:
                                self.frame_times.pop(0)
                            self.frame_count += 1
                            consecutive_errors = 0
                        else:
                            consecutive_errors += 1

                    # Print FPS every second
                    current_time = time.time()
                    if current_time - self.last_fps_print >= 1.0:
                        if self.frame_count > 0 and self.frame_times:
                            avg_frame_time = sum(self.frame_times) / len(
                                self.frame_times
                            )
                            fps = self.frame_count / (
                                current_time - self.last_fps_print
                            )
                            print(
                                f"Display FPS: {fps:.1f}, Update time: {avg_frame_time * 1000:.1f}ms"
                            )
                        self.frame_count = 0
                        self.last_fps_print = current_time

                # Check for timeout
                if time.time() - self.last_frame_time > self.frame_timeout:
                    print("Frame timeout - no frames received")
                    consecutive_errors += 1

                # Handle errors
                if consecutive_errors >= max_consecutive_errors:
                    print("Too many consecutive errors, reinitializing strip...")
                    self.clear_strip()
                    if not self.init_strip():
                        print("Failed to reinitialize strip")
                        break
                    consecutive_errors = 0

                # Small sleep to prevent tight loop
                time.sleep(0.001)

            except Exception as e:
                print(f"Error in display loop: {e}")
                consecutive_errors += 1
                time.sleep(0.001)

    def start(self):
        """Start display controller"""
        if not self.is_running:
            if not self.init_strip():
                return False

            self.is_running = True
            self.display_thread = threading.Thread(target=self._display_loop)
            self.display_thread.daemon = True
            self.display_thread.start()
            return True
        return False

    def stop(self):
        """Stop display controller"""
        self.is_running = False
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=1.0)
        self.clear_strip()
