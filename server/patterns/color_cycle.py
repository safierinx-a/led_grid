import math
from typing import Dict, Any, List
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ColorCycle(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="color_cycle",
            description="Smooth color cycling pattern",
            parameters=[
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Color cycling speed",
                ),
                Parameter(
                    name="saturation",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color saturation",
                ),
                Parameter(
                    name="wave_length",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Length of color waves",
                ),
            ],
            category="animations",
            tags=["color", "cycle", "waves"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0

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

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        speed = params["speed"]
        saturation = params["saturation"]
        wave_length = params["wave_length"]

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Calculate distance from center
                cx = x - self.width / 2
                cy = y - self.height / 2
                distance = math.sqrt(cx * cx + cy * cy)

                # Calculate hue based on distance and time
                hue = (distance * wave_length + self._step) / (self.width + self.height)

                # Convert to RGB
                r, g, b = self.hsv_to_rgb(hue, saturation, 1.0)

                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        # Update step for next frame
        self._step = (self._step + speed) % (self.width + self.height)

        return pixels
