import math
from typing import Dict, Any, List
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Waves(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="waves",
            description="Dynamic wave patterns with multiple modes",
            parameters=[
                Parameter(
                    name="wave_type",
                    type=str,
                    default="ripple",
                    description="Wave type (ripple/interference/sine/circular)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Wave animation speed",
                ),
                Parameter(
                    name="wavelength",
                    type=float,
                    default=5.0,
                    min_value=1.0,
                    max_value=20.0,
                    description="Wave length in pixels",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="rainbow",
                    description="Color mode (rainbow/gradient/monochrome)",
                ),
            ],
            category="animations",
            tags=["waves", "water", "physics"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2

    def hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
        """Convert HSV color to RGB."""
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

    def get_color(
        self, value: float, color_mode: str, x: int, y: int
    ) -> tuple[int, int, int]:
        """Get color based on wave value and color mode"""
        if color_mode == "rainbow":
            hue = (value + 1) / 2
            return self.hsv_to_rgb(hue, 1.0, 1.0)
        elif color_mode == "gradient":
            # Blue to white gradient for water-like effect
            b = int(((value + 1) / 2) * 255)
            g = int(max(0, b - 100))
            r = int(max(0, b - 150))
            return (r, g, b)
        else:  # monochrome
            v = int(((value + 1) / 2) * 255)
            return (v, v, v)

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        wave_type = params["wave_type"]
        speed = params["speed"]
        wavelength = params["wavelength"]
        color_mode = params["color_mode"]

        self._time += 0.05 * speed
        pixels = []

        for y in range(self.height):
            for x in range(self.width):
                value = 0.0

                if wave_type == "ripple":
                    # Create expanding circular waves from center
                    dx = x - self._center_x
                    dy = y - self._center_y
                    distance = math.sqrt(dx * dx + dy * dy)
                    value = math.sin(distance / wavelength - self._time)

                elif wave_type == "interference":
                    # Create interference pattern from multiple sources
                    sources = [
                        (0, 0),
                        (self.width, 0),
                        (0, self.height),
                        (self.width, self.height),
                    ]
                    for sx, sy in sources:
                        dx = x - sx
                        dy = y - sy
                        distance = math.sqrt(dx * dx + dy * dy)
                        value += math.sin(distance / wavelength - self._time) * 0.25

                elif wave_type == "sine":
                    # Create diagonal sine waves
                    value = math.sin((x + y) / wavelength - self._time) * math.cos(
                        (x - y) / wavelength - self._time * 0.5
                    )

                else:  # circular
                    # Create circular standing waves
                    dx = x - self._center_x
                    dy = y - self._center_y
                    angle = math.atan2(dy, dx)
                    distance = math.sqrt(dx * dx + dy * dy)
                    value = math.sin(distance / wavelength - self._time) * math.cos(
                        angle * 3 + self._time
                    )

                r, g, b = self.get_color(value, color_mode, x, y)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        return pixels
