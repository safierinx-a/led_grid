import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Plasma(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="plasma",
            description="Bold plasma patterns optimized for 24x25 LED grid with chunky color areas",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="block",
                    description="Pattern variation (block, grid, corner, quad, digital)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=3.0,
                    description="Pattern scale",
                ),
                Parameter(
                    name="palette",
                    type=str,
                    default="plasma",
                    description="Color palette (plasma, cosmic, fire, ocean, neon)",
                ),
                Parameter(
                    name="intensity",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=2.0,
                    description="Color intensity",
                ),
                Parameter(
                    name="block_size",
                    type=int,
                    default=2,
                    min_value=2,
                    max_value=3,
                    description="Size of color blocks (2-3 pixels)",
                ),
            ],
            category="animations",
            tags=["plasma", "flow", "psychedelic"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._grid_points = self._create_grid_points()

    def _create_grid_points(self) -> List[tuple[int, int]]:
        """Create grid points for grid-aligned patterns"""
        points = []
        for y in range(0, self.height, 4):  # Grid every 4 pixels
            for x in range(0, self.width, 4):
                points.append((x, y))
        return points

    def _get_block_value(self, x: int, y: int, block_size: int, func) -> float:
        """Calculate value for a block of pixels using the given function"""
        # Use center of block for calculation
        bx = (x // block_size) * block_size + block_size / 2
        by = (y // block_size) * block_size + block_size / 2
        return func(bx, by)

    def _generate_block(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate plasma effect using block-based approach"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        intensity = params["intensity"]
        block_size = params["block_size"]
        time_factor = self._step * speed * 0.05

        pixels = []
        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                value = math.sin(bx * scale * 0.1 + time_factor) * math.cos(
                    by * scale * 0.1 + time_factor
                )
                value = (value + 1) / 2  # Normalize to [0,1]

                # Apply color to block
                color = self._get_palette_color(value, palette, intensity)
                for dy in range(block_size):
                    for dx in range(block_size):
                        px, py = bx + dx, by + dy
                        if px < self.width and py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
                                    "r": color[0],
                                    "g": color[1],
                                    "b": color[2],
                                }
                            )
        return pixels

    def _generate_grid(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Plasma that follows grid lines with enhanced visibility"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        intensity = params["intensity"]
        block_size = params["block_size"]
        time_factor = self._step * speed * 0.05

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Calculate distance to nearest grid lines
                dx = min(x % 4, 4 - (x % 4))  # Grid every 4 pixels
                dy = min(y % 4, 4 - (y % 4))
                grid_dist = min(dx, dy)

                # Create stronger effect near grid lines
                grid_intensity = max(0, 1.0 - grid_dist / 2)  # Sharper falloff

                # Generate plasma value
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5
                value = math.sin(nx * 8 * scale + time_factor) * math.sin(
                    ny * 8 * scale + time_factor
                )
                value = (value + 1) / 2

                # Enhance contrast near grid lines
                value = value * (0.5 + 0.5 * grid_intensity)

                color = self._get_palette_color(value, palette, intensity)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": color[0],
                        "g": color[1],
                        "b": color[2],
                    }
                )
        return pixels

    def _generate_corner(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Color mixing from corners with enhanced visibility"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        intensity = params["intensity"]
        block_size = params["block_size"]
        time_factor = self._step * speed * 0.05

        pixels = []
        corners = [
            (0, 0),
            (self.width - 1, 0),
            (0, self.height - 1),
            (self.width - 1, self.height - 1),
        ]

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                center_x = bx + block_size / 2
                center_y = by + block_size / 2

                # Calculate influence from each corner
                value = 0
                for i, (cx, cy) in enumerate(corners):
                    dist = math.sqrt((center_x - cx) ** 2 + (center_y - cy) ** 2)
                    max_dist = math.sqrt(self.width**2 + self.height**2)
                    corner_value = math.sin(
                        dist * scale * 0.1 + time_factor + i * math.pi / 2
                    )
                    value += corner_value * (1 - dist / max_dist)

                value = (value + len(corners)) / (2 * len(corners))  # Normalize

                # Apply color to block
                color = self._get_palette_color(value, palette, intensity)
                for dy in range(block_size):
                    for dx in range(block_size):
                        px, py = bx + dx, by + dy
                        if px < self.width and py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
                                    "r": color[0],
                                    "g": color[1],
                                    "b": color[2],
                                }
                            )
        return pixels

    def _generate_quad(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Four distinct interacting plasma fields"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        intensity = params["intensity"]
        block_size = params["block_size"]
        time_factor = self._step * speed * 0.05

        pixels = []
        mid_x = self.width // 2
        mid_y = self.height // 2

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Determine quadrant
                quad_x = 0 if bx < mid_x else 1
                quad_y = 0 if by < mid_y else 1
                quadrant = quad_y * 2 + quad_x

                # Calculate local coordinates within quadrant
                local_x = (bx - (quad_x * mid_x)) / mid_x - 0.5
                local_y = (by - (quad_y * mid_y)) / mid_y - 0.5

                # Generate unique pattern for each quadrant
                if quadrant == 0:
                    value = math.sin(local_x * 8 * scale + time_factor) * math.cos(
                        local_y * 8 * scale
                    )
                elif quadrant == 1:
                    value = math.sin(
                        (local_x + local_y) * 8 * scale + time_factor * 1.1
                    )
                elif quadrant == 2:
                    value = math.sin(
                        math.sqrt((local_x**2 + local_y**2) * 64) * scale
                        + time_factor * 0.9
                    )
                else:
                    value = math.sin(local_x * 8 * scale) * math.sin(
                        local_y * 8 * scale + time_factor * 1.2
                    )

                # Normalize to [0,1]
                value = (value + 1) / 2

                # Apply color to block
                color = self._get_palette_color(value, palette, intensity)
                for dy in range(block_size):
                    for dx in range(block_size):
                        px, py = bx + dx, by + dy
                        if px < self.width and py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
                                    "r": color[0],
                                    "g": color[1],
                                    "b": color[2],
                                }
                            )
        return pixels

    def _generate_digital(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Sharp digital transitions between colors"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        intensity = params["intensity"]
        block_size = params["block_size"]
        time_factor = self._step * speed * 0.05

        pixels = []
        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                nx = (bx + block_size / 2) / self.width - 0.5
                ny = (by + block_size / 2) / self.height - 0.5

                # Generate digital-looking pattern
                value = math.sin(nx * 6 * scale + time_factor) + math.sin(
                    ny * 6 * scale + time_factor
                )
                value = (value + 2) / 4

                # Quantize value for sharp transitions
                value = round(value * 4) / 4

                # Apply color to block
                color = self._get_palette_color(value, palette, intensity)
                for dy in range(block_size):
                    for dx in range(block_size):
                        px, py = bx + dx, by + dy
                        if px < self.width and py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
                                    "r": color[0],
                                    "g": color[1],
                                    "b": color[2],
                                }
                            )
        return pixels

    def _get_palette_color(
        self, value: float, palette: str, intensity: float
    ) -> tuple[int, int, int]:
        """Get color from palette based on value and intensity"""
        value = max(0.0, min(1.0, value))  # Clamp value to [0,1]
        intensity = max(0.1, min(2.0, intensity))  # Clamp intensity

        if palette == "plasma":
            # Purple to orange plasma
            hue = 0.8 + value * 0.3  # Range from purple (0.8) to orange (1.1)
            sat = 0.8 + value * 0.2
            val = value * intensity
        elif palette == "cosmic":
            # Deep blue to bright purple
            hue = 0.6 + value * 0.15
            sat = 0.7 + value * 0.3
            val = value * intensity
        elif palette == "fire":
            # Red to yellow
            hue = value * 0.15  # Range from red (0.0) to yellow (0.15)
            sat = 1.0 - value * 0.3
            val = value * intensity
        elif palette == "ocean":
            # Deep blue to cyan
            hue = 0.5 + value * 0.15
            sat = 0.8
            val = value * intensity
        else:  # neon
            # Bright neon colors
            hue = value
            sat = 0.8 + value * 0.2
            val = 0.8 * intensity

        # Convert HSV to RGB
        h = hue % 1.0
        if sat == 0.0:
            rgb = (val, val, val)
        else:
            i = int(h * 6.0)
            f = (h * 6.0) - i
            p = val * (1.0 - sat)
            q = val * (1.0 - sat * f)
            t = val * (1.0 - sat * (1.0 - f))
            i = i % 6

            if i == 0:
                rgb = (val, t, p)
            elif i == 1:
                rgb = (q, val, p)
            elif i == 2:
                rgb = (p, val, t)
            elif i == 3:
                rgb = (p, q, val)
            elif i == 4:
                rgb = (t, p, val)
            else:
                rgb = (val, p, q)

        return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the plasma pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "block":
            pattern_pixels = self._generate_block(params)
        elif variation == "grid":
            pattern_pixels = self._generate_grid(params)
        elif variation == "corner":
            pattern_pixels = self._generate_corner(params)
        elif variation == "quad":
            pattern_pixels = self._generate_quad(params)
        else:  # digital
            pattern_pixels = self._generate_digital(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
