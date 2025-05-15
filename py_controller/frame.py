import struct
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger("legrid-controller")


@dataclass
class Frame:
    """Represents a single frame of LED data"""

    width: int
    height: int
    pixels: List[Tuple[int, int, int]]  # RGB values
    pattern_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

    @property
    def pixel_count(self) -> int:
        """Get the total number of pixels in the frame"""
        return len(self.pixels)


class FrameProcessor:
    """Handles frame decoding and processing"""

    def __init__(
        self,
        width,
        height,
        layout="serpentine",
        flip_x=False,
        flip_y=False,
        transpose=False,
    ):
        self.width = width
        self.height = height
        self.layout = layout
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.transpose = transpose

        # Statistics
        self.frames_processed = 0
        self.last_frame_id = None
        self.last_pattern_id = None

    def process_binary_frame(self, binary_data):
        """Process a binary frame and return a Frame object

        Binary format:
        <Version:1><Type:1><FrameID:4><Width:2><Height:2><Pixels...>
        """
        try:
            # Ensure we have at least the header
            if len(binary_data) < 10:
                logger.warning(
                    f"Invalid frame: insufficient data ({len(binary_data)} bytes)"
                )
                return None

            # Parse header
            version = binary_data[0]
            msg_type = binary_data[1]
            frame_id_bytes = binary_data[2:6]
            width_bytes = binary_data[6:8]
            height_bytes = binary_data[8:10]

            # Parse values with appropriate endianness (little-endian)
            frame_id = struct.unpack("<I", frame_id_bytes)[0]
            width = struct.unpack("<H", width_bytes)[0]
            height = struct.unpack("<H", height_bytes)[0]

            # Log raw header values to debug
            logger.debug(
                f"Frame header: version={version}, type={msg_type}, id={frame_id}, dimensions={width}x{height}"
            )

            # Validate dimensions
            if width == 0 or height == 0 or width > 1000 or height > 1000:
                logger.warning(
                    f"Invalid frame dimensions: {width}x{height}, using defaults"
                )
                # Use default dimensions instead of failing
                width = self.width
                height = self.height

            # Make sure we only process full frames (type 1)
            # We're simplifying by ignoring delta frames as requested
            if msg_type != 1:
                logger.warning(f"Unexpected message type: {msg_type}")
                return None

            # Check if we have enough pixel data
            pixel_data = binary_data[10:]
            expected_data_length = width * height * 3
            if len(pixel_data) < expected_data_length:
                logger.warning(
                    f"Incomplete pixel data: got {len(pixel_data)} bytes, expected {expected_data_length}"
                )
                # Continue anyway - we'll use what we have

            # Decode pixels
            pixels = []
            for i in range(min(width * height, len(pixel_data) // 3)):
                idx = i * 3
                r = pixel_data[idx]
                g = pixel_data[idx + 1]
                b = pixel_data[idx + 2]
                pixels.append((r, g, b))

            # Pad with black if needed
            while len(pixels) < width * height:
                pixels.append((0, 0, 0))

            # Create frame object
            frame = Frame(width=width, height=height, pixels=pixels)

            # Update statistics
            self.frames_processed += 1
            self.last_frame_id = frame_id

            return frame

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            # Print first few bytes of data to help debug binary format issues
            if len(binary_data) > 20:
                logger.debug(f"First 20 bytes of frame data: {binary_data[:20].hex()}")
            return None

    def map_led_layout(self, frame):
        """Map logical pixel positions to physical LED indices based on configuration"""
        if not frame or not frame.pixels:
            return []

        # Create a copy of the pixel array for physical layout
        physical_pixels = [(0, 0, 0)] * (self.width * self.height)

        # Apply layout mapping
        for y in range(min(frame.height, self.height)):
            for x in range(min(frame.width, self.width)):
                # Source index in logical frame
                src_idx = y * frame.width + x

                # Only process if we have data for this pixel
                if src_idx < len(frame.pixels):
                    # Calculate physical position
                    physical_idx = self.map_pixel_to_index(x, y)

                    # Set physical pixel if within bounds
                    if 0 <= physical_idx < len(physical_pixels):
                        physical_pixels[physical_idx] = frame.pixels[src_idx]

        return physical_pixels

    def map_pixel_to_index(self, x, y):
        """Map an x,y position to a physical LED index based on the configuration"""
        width, height = self.width, self.height

        # Apply transpose if needed (swap x and y)
        if self.transpose:
            x, y = y, x
            width, height = height, width

        # Apply flips
        if self.flip_x:
            x = width - 1 - x

        if self.flip_y:
            y = height - 1 - y

        # Apply layout pattern
        if self.layout == "serpentine":
            # In serpentine layout, even rows go left to right, odd rows go right to left
            if y % 2 == 1:  # Odd row (0-indexed)
                x = width - 1 - x

        # Calculate linear index
        return y * width + x
