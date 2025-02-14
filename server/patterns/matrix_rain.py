import random
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry
import math


@PatternRegistry.register
class MatrixRain(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="matrix_rain",
            description="Bold matrix-style digital rain optimized for 24x25 LED grid",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="bold",
                    description="Rain variation (bold, data, cascade, binary, corner)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Speed of falling drops",
                ),
                Parameter(
                    name="density",
                    type=float,
                    default=0.15,
                    min_value=0.05,
                    max_value=0.5,
                    description="Density of drops",
                ),
                Parameter(
                    name="brightness",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Overall brightness",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="green",
                    description="Color mode (green, cyan, rainbow, mono)",
                ),
                Parameter(
                    name="drop_size",
                    type=int,
                    default=2,
                    min_value=2,
                    max_value=3,
                    description="Size of drops (2 or 3 pixels)",
                ),
            ],
            category="animations",
            tags=["matrix", "rain", "digital"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.drops = []  # List of (x, y, intensity, size, type) for each drop
        self._step = 0
        self._data_streams = []  # For data stream variation
        self._corner_flow = []  # For corner flow variation

    def _get_color(self, intensity: float, color_mode: str) -> tuple[int, int, int]:
        """Get color based on intensity and color mode"""
        if color_mode == "green":
            return (0, int(intensity * 255), 0)
        elif color_mode == "cyan":
            return (0, int(intensity * 255), int(intensity * 255))
        elif color_mode == "rainbow":
            hue = (self._step * 0.01 + intensity) % 1.0
            return self._hsv_to_rgb(hue, 1.0, intensity)
        else:  # mono
            val = int(intensity * 255)
            return (val, val, val)

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
        """Convert HSV to RGB"""
        h = h % 1.0
        if s == 0.0:
            return (int(v * 255), int(v * 255), int(v * 255))

        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6

        if i == 0:
            rgb = (v, t, p)
        elif i == 1:
            rgb = (q, v, p)
        elif i == 2:
            rgb = (p, v, t)
        elif i == 3:
            rgb = (p, q, v)
        elif i == 4:
            rgb = (t, p, v)
        else:
            rgb = (v, p, q)

        return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))

    def _create_binary_char(self, size: int) -> List[List[bool]]:
        """Create a random binary character pattern"""
        if size == 2:
            return [[random.choice([True, False]) for _ in range(2)] for _ in range(2)]
        else:  # size == 3
            pattern = [
                [random.choice([True, False]) for _ in range(3)] for _ in range(3)
            ]
            # Ensure at least 4 pixels are lit for readability
            lit_count = sum(sum(row) for row in pattern)
            while lit_count < 4:
                x, y = random.randint(0, 2), random.randint(0, 2)
                if not pattern[y][x]:
                    pattern[y][x] = True
                    lit_count += 1
            return pattern

    def _generate_bold(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Bold matrix rain with 2x2 or 3x3 drops"""
        speed = params["speed"]
        density = params["density"]
        brightness = params["brightness"]
        color_mode = params["color_mode"]
        drop_size = params["drop_size"]

        # Update existing drops
        new_drops = []
        for x, y, intensity, size, pattern in self.drops:
            if y < self.height - size + 1:
                new_drops.append((x, y + speed, intensity * 0.95, size, pattern))

        # Add new drops
        if random.random() < density:
            x = random.randint(0, self.width - drop_size)
            pattern = self._create_binary_char(drop_size)
            new_drops.append((x, 0, 1.0, drop_size, pattern))

        self.drops = new_drops

        # Generate frame
        pixels = []
        for x, y, intensity, size, pattern in self.drops:
            if 0 <= int(y) < self.height - size + 1:
                r, g, b = self._get_color(intensity * brightness, color_mode)
                for dx in range(size):
                    for dy in range(size):
                        if pattern[dy][dx]:  # Only light up pixels in the pattern
                            px, py = int(x + dx), int(y + dy)
                            if px < self.width and py < self.height:
                                pixels.append(
                                    {
                                        "index": self.grid_config.xy_to_index(px, py),
                                        "r": r,
                                        "g": g,
                                        "b": b,
                                    }
                                )

        return pixels

    def _generate_data(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Concentrated data stream columns"""
        speed = params["speed"]
        density = params["density"]
        brightness = params["brightness"]
        color_mode = params["color_mode"]
        drop_size = params["drop_size"]

        # Update data streams
        if not self._data_streams or random.random() < 0.1:
            # Create new stream column
            if len(self._data_streams) < self.width // (drop_size * 2):
                x = random.randint(0, self.width - drop_size)
                while any(abs(x - sx) < drop_size * 2 for sx, _ in self._data_streams):
                    x = random.randint(0, self.width - drop_size)
                self._data_streams.append((x, 1.0))

        # Generate frame
        pixels = []
        new_streams = []
        for x, intensity in self._data_streams:
            if intensity > 0.2:
                # Create dense column of characters
                for y in range(0, self.height - drop_size + 1, drop_size + 1):
                    if (
                        random.random() < 0.7
                    ):  # 70% chance of character at each position
                        pattern = self._create_binary_char(drop_size)
                        r, g, b = self._get_color(intensity * brightness, color_mode)
                        for dx in range(drop_size):
                            for dy in range(drop_size):
                                if pattern[dy][dx]:
                                    px, py = x + dx, y + dy
                                    if px < self.width and py < self.height:
                                        pixels.append(
                                            {
                                                "index": self.grid_config.xy_to_index(
                                                    px, py
                                                ),
                                                "r": r,
                                                "g": g,
                                                "b": b,
                                            }
                                        )
                new_streams.append((x, intensity * 0.99))

        self._data_streams = new_streams
        return pixels

    def _generate_cascade(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Drops that follow grid patterns"""
        speed = params["speed"]
        density = params["density"]
        brightness = params["brightness"]
        color_mode = params["color_mode"]
        drop_size = params["drop_size"]

        # Update existing drops
        new_drops = []
        for x, y, intensity, size, pattern in self.drops:
            if y < self.height - size + 1:
                # Follow grid pattern - zigzag every 4 pixels
                new_x = x
                if int(y) % 4 == 0:
                    new_x = (x + 1) % (self.width - size + 1)
                new_drops.append((new_x, y + speed, intensity * 0.95, size, pattern))

        # Add new drops
        if random.random() < density:
            x = random.randint(0, self.width - drop_size)
            pattern = self._create_binary_char(drop_size)
            new_drops.append((x, 0, 1.0, drop_size, pattern))

        self.drops = new_drops

        # Generate frame
        pixels = []
        for x, y, intensity, size, pattern in self.drops:
            if 0 <= int(y) < self.height - size + 1:
                r, g, b = self._get_color(intensity * brightness, color_mode)
                for dx in range(size):
                    for dy in range(size):
                        if pattern[dy][dx]:
                            px, py = int(x + dx), int(y + dy)
                            if px < self.width and py < self.height:
                                pixels.append(
                                    {
                                        "index": self.grid_config.xy_to_index(px, py),
                                        "r": r,
                                        "g": g,
                                        "b": b,
                                    }
                                )

        return pixels

    def _generate_binary(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Binary-style matrix rain with more complex patterns"""
        speed = params["speed"]
        density = params["density"]
        brightness = params["brightness"]
        color_mode = params["color_mode"]
        drop_size = params["drop_size"]

        # Update existing drops
        new_drops = []
        for x, y, intensity, size, pattern in self.drops:
            if y < self.height - size + 1:
                # Randomly change pattern occasionally
                if random.random() < 0.1:
                    pattern = self._create_binary_char(size)
                new_drops.append((x, y + speed, intensity * 0.95, size, pattern))

        # Add new drops
        if random.random() < density:
            x = random.randint(0, self.width - drop_size)
            pattern = self._create_binary_char(drop_size)
            new_drops.append((x, 0, 1.0, drop_size, pattern))

        self.drops = new_drops

        # Generate frame
        pixels = []
        for x, y, intensity, size, pattern in self.drops:
            if 0 <= int(y) < self.height - size + 1:
                r, g, b = self._get_color(intensity * brightness, color_mode)
                for dx in range(size):
                    for dy in range(size):
                        if pattern[dy][dx]:
                            px, py = int(x + dx), int(y + dy)
                            if px < self.width and py < self.height:
                                pixels.append(
                                    {
                                        "index": self.grid_config.xy_to_index(px, py),
                                        "r": r,
                                        "g": g,
                                        "b": b,
                                    }
                                )

        return pixels

    def _generate_corner(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Corner-to-corner flowing patterns"""
        speed = params["speed"]
        density = params["density"]
        brightness = params["brightness"]
        color_mode = params["color_mode"]
        drop_size = params["drop_size"]

        # Update corner flow
        if not self._corner_flow or random.random() < 0.05:
            # Start new flow from a corner
            corner = random.choice(["tl", "tr", "bl", "br"])
            if corner == "tl":
                x, y = 0, 0
                dx, dy = 1, 1
            elif corner == "tr":
                x, y = self.width - drop_size, 0
                dx, dy = -1, 1
            elif corner == "bl":
                x, y = 0, self.height - drop_size
                dx, dy = 1, -1
            else:  # br
                x, y = self.width - drop_size, self.height - drop_size
                dx, dy = -1, -1

            self._corner_flow.append(
                {
                    "x": x,
                    "y": y,
                    "dx": dx,
                    "dy": dy,
                    "intensity": 1.0,
                    "pattern": self._create_binary_char(drop_size),
                }
            )

        # Generate frame
        pixels = []
        new_flow = []
        for flow in self._corner_flow:
            if 0.2 < flow["intensity"]:
                x, y = flow["x"], flow["y"]
                if (
                    0 <= x < self.width - drop_size + 1
                    and 0 <= y < self.height - drop_size + 1
                ):
                    # Draw current position
                    r, g, b = self._get_color(
                        flow["intensity"] * brightness, color_mode
                    )
                    pattern = flow["pattern"]
                    for dx in range(drop_size):
                        for dy in range(drop_size):
                            if pattern[dy][dx]:
                                px, py = int(x + dx), int(y + dy)
                                if px < self.width and py < self.height:
                                    pixels.append(
                                        {
                                            "index": self.grid_config.xy_to_index(
                                                px, py
                                            ),
                                            "r": r,
                                            "g": g,
                                            "b": b,
                                        }
                                    )

                    # Update position
                    flow["x"] += flow["dx"] * speed
                    flow["y"] += flow["dy"] * speed
                    flow["intensity"] *= 0.99
                    new_flow.append(flow)

        self._corner_flow = new_flow
        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the Matrix rain pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "bold":
            pattern_pixels = self._generate_bold(params)
        elif variation == "data":
            pattern_pixels = self._generate_data(params)
        elif variation == "cascade":
            pattern_pixels = self._generate_cascade(params)
        elif variation == "binary":
            pattern_pixels = self._generate_binary(params)
        else:  # corner
            pattern_pixels = self._generate_corner(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
