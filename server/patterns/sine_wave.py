import math
import random
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class SineWave(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="sine_wave",
            description="Multiple horizontal or vertical bands shifting in sine wave patterns with smooth color transitions",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="horizontal",
                    description="Wave direction (horizontal, vertical, diagonal, radial)",
                ),
                Parameter(
                    name="frequency",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Number of wave peaks across the grid",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Wave movement speed",
                ),
                Parameter(
                    name="amplitude",
                    type=float,
                    default=0.5,
                    min_value=0.1,
                    max_value=1.0,
                    description="Wave height/displacement",
                ),
                Parameter(
                    name="wave_count",
                    type=int,
                    default=3,
                    min_value=1,
                    max_value=5,
                    description="Number of overlapping waves",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="rainbow",
                    description="Color scheme (rainbow, ocean, pastel, mono)",
                ),
                Parameter(
                    name="phase_offset",
                    type=float,
                    default=0.3,
                    min_value=0.0,
                    max_value=1.0,
                    description="Phase difference between waves",
                ),
                Parameter(
                    name="blend",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color blending between waves",
                ),
            ],
            category="animations",
            tags=["waves", "smooth", "colorful"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._color_buffer = {}  # For color blending

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
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

    def _get_wave_color(
        self, value: float, time: float, wave_index: int, mode: str
    ) -> tuple[int, int, int]:
        """Get color based on wave value and color mode."""
        if mode == "rainbow":
            # Smooth rainbow transitions
            hue = (value + time * 0.1 + wave_index * 0.2) % 1.0
            return self._hsv_to_rgb(hue, 0.8, 1.0)
        elif mode == "ocean":
            # Ocean blues and teals
            hue = 0.5 + value * 0.2  # Range in blue-green spectrum
            sat = 0.8 + value * 0.2
            val = 0.7 + value * 0.3
            return self._hsv_to_rgb(hue, sat, val)
        elif mode == "pastel":
            # Soft pastel colors
            hue = (value + time * 0.05 + wave_index * 0.3) % 1.0
            return self._hsv_to_rgb(hue, 0.4, 1.0)
        else:  # mono
            # Monochrome wave
            val = 0.3 + value * 0.7
            return self._hsv_to_rgb(0.0, 0.0, val)

    def _blend_colors(
        self, color1: tuple[int, int, int], color2: tuple[int, int, int], factor: float
    ) -> tuple[int, int, int]:
        """Blend two colors with given factor."""
        return tuple(
            int(c1 * (1 - factor) + c2 * factor) for c1, c2 in zip(color1, color2)
        )

    def _calculate_wave(
        self, x: float, y: float, time: float, params: Dict[str, Any], wave_index: int
    ) -> float:
        """Calculate wave value at given position."""
        frequency = params["frequency"]
        speed = params["speed"]
        amplitude = params["amplitude"]
        phase_offset = params["phase_offset"] * wave_index

        if params["variation"] == "horizontal":
            # Horizontal waves
            return math.sin(y * frequency + time * speed + phase_offset) * amplitude
        elif params["variation"] == "vertical":
            # Vertical waves
            return math.sin(x * frequency + time * speed + phase_offset) * amplitude
        elif params["variation"] == "diagonal":
            # Diagonal waves
            return (
                math.sin((x + y) * frequency * 0.7 + time * speed + phase_offset)
                * amplitude
            )
        else:  # radial
            # Radial waves from center
            dx = x - self._center_x
            dy = y - self._center_y
            dist = math.sqrt(dx * dx + dy * dy)
            return (
                math.sin(dist * frequency * 0.2 + time * speed + phase_offset)
                * amplitude
            )

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the sine wave pattern."""
        # Validate parameters
        params = self.validate_params(params)

        # Clear color buffer
        self._color_buffer.clear()

        # Initialize pixels
        pixels = []
        wave_count = params["wave_count"]
        blend = params["blend"]

        # Generate each pixel
        for y in range(self.height):
            for x in range(self.width):
                # Calculate combined wave value
                wave_values = [
                    self._calculate_wave(x, y, self._time, params, i)
                    for i in range(wave_count)
                ]

                # Get colors for each wave
                wave_colors = [
                    self._get_wave_color(
                        (value + 1) / 2,  # Normalize to 0-1
                        self._time,
                        i,
                        params["color_mode"],
                    )
                    for i, value in enumerate(wave_values)
                ]

                # Blend colors based on wave values
                final_color = wave_colors[0]
                for i in range(1, len(wave_colors)):
                    blend_factor = (wave_values[i] + 1) / 2 * blend
                    final_color = self._blend_colors(
                        final_color, wave_colors[i], blend_factor
                    )

                # Add pixel to frame
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": final_color[0],
                        "g": final_color[1],
                        "b": final_color[2],
                    }
                )

        self._time += 0.1
        return pixels
