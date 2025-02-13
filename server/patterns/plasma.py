import math
import time
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Plasma(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="plasma",
            description="Dynamic plasma-like flowing effect",
            parameters=[
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Pattern scale",
                ),
                Parameter(
                    name="color_shift",
                    type=float,
                    default=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color shift amount",
                ),
            ],
            category="animations",
            tags=["plasma", "flow", "psychedelic"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0

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
        scale = params["scale"]
        color_shift = params["color_shift"]

        pixels = []
        self._time += 0.05 * speed

        for y in range(self.height):
            for x in range(self.width):
                # Calculate normalized coordinates
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5

                # Generate plasma value using multiple sine waves
                v1 = math.sin(nx * 10 * scale + self._time)
                v2 = math.sin(
                    10
                    * scale
                    * (nx * math.sin(self._time / 2) + ny * math.cos(self._time / 3))
                    + self._time
                )
                v3 = math.sin(
                    math.sqrt((nx * nx * 100 + ny * ny * 100) * scale) + self._time
                )

                # Combine waves
                plasma_value = (v1 + v2 + v3) / 3.0

                # Map to color
                hue = (plasma_value + 1) / 2 + color_shift
                r, g, b = self.hsv_to_rgb(hue, 1.0, 1.0)

                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        return pixels
