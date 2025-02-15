import math
import random
from typing import Dict, Any, List
import numpy as np
from noise import snoise2  # For Perlin noise
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class PerlinLandscape(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="perlin_landscape",
            description="Dynamic Perlin noise landscape with smooth transitions and organic movement",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="terrain",
                    description="Landscape type (terrain, lava, ocean, clouds, plasma)",
                ),
                Parameter(
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Noise scale/zoom level",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Movement speed",
                ),
                Parameter(
                    name="octaves",
                    type=int,
                    default=3,
                    min_value=1,
                    max_value=5,
                    description="Noise detail levels",
                ),
                Parameter(
                    name="persistence",
                    type=float,
                    default=0.5,
                    min_value=0.1,
                    max_value=0.9,
                    description="How much detail is preserved",
                ),
                Parameter(
                    name="contrast",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=2.0,
                    description="Color contrast",
                ),
                Parameter(
                    name="height_offset",
                    type=float,
                    default=0.0,
                    min_value=-1.0,
                    max_value=1.0,
                    description="Vertical offset of the landscape",
                ),
                Parameter(
                    name="color_shift",
                    type=float,
                    default=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color palette shift",
                ),
            ],
            category="landscapes",
            tags=["perlin", "noise", "organic", "landscape"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._noise_buffer = np.zeros((self.height, self.width))
        self._color_buffer = {}
        self._center_x = self.width / 2
        self._center_y = self.height / 2

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

    def _get_terrain_color(
        self, height: float, params: Dict[str, Any]
    ) -> tuple[int, int, int]:
        """Get color based on height and variation."""
        variation = params["variation"]
        contrast = params["contrast"]
        shift = params["color_shift"]

        # Apply contrast
        height = ((height + 1) / 2) ** contrast  # Normalize and apply contrast

        if variation == "terrain":
            if height < 0.2:  # Deep water
                return self._hsv_to_rgb(0.6 + shift, 0.8, 0.4 + height)
            elif height < 0.3:  # Shallow water
                return self._hsv_to_rgb(0.5 + shift, 0.7, 0.5 + height)
            elif height < 0.5:  # Plains
                return self._hsv_to_rgb(0.3 + shift, 0.6, 0.4 + height)
            elif height < 0.7:  # Hills
                return self._hsv_to_rgb(0.25 + shift, 0.5, 0.3 + height)
            else:  # Mountains
                return self._hsv_to_rgb(0.1 + shift, 0.3, 0.2 + height)

        elif variation == "lava":
            if height < 0.3:  # Dark rock
                return self._hsv_to_rgb(0.0 + shift, 0.8, 0.2 + height)
            elif height < 0.6:  # Hot rock
                return self._hsv_to_rgb(0.05 + shift, 0.9, 0.4 + height)
            else:  # Lava
                return self._hsv_to_rgb(0.05 + shift, 1.0, 0.7 + height * 0.3)

        elif variation == "ocean":
            if height < 0.3:  # Deep ocean
                return self._hsv_to_rgb(0.6 + shift, 0.9, 0.3 + height)
            elif height < 0.6:  # Mid ocean
                return self._hsv_to_rgb(0.5 + shift, 0.8, 0.5 + height)
            else:  # Surface
                return self._hsv_to_rgb(0.45 + shift, 0.7, 0.6 + height * 0.4)

        elif variation == "clouds":
            # Soft whites and grays
            return self._hsv_to_rgb(0.6 + shift, 0.1, 0.7 + height * 0.3)

        else:  # plasma
            # Dynamic color cycling
            hue = (height + self._time * 0.1 + shift) % 1.0
            return self._hsv_to_rgb(hue, 0.8, 0.5 + height * 0.5)

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the Perlin landscape pattern."""
        # Validate parameters
        params = self.validate_params(params)

        # Clear buffers
        self._color_buffer.clear()
        pixels = []

        # Generate noise field
        scale = params["scale"]
        speed = params["speed"]
        octaves = params["octaves"]
        persistence = params["persistence"]
        height_offset = params["height_offset"]

        # Calculate noise for each pixel
        for y in range(self.height):
            for x in range(self.width):
                # Generate multi-octave noise
                noise_val = 0
                amplitude = 1.0
                frequency = 1.0
                max_val = 0

                for _ in range(octaves):
                    nx = x * scale * frequency / self.width
                    ny = y * scale * frequency / self.height
                    nt = self._time * speed * frequency * 0.1

                    noise_val += snoise2(nx + nt, ny + nt) * amplitude
                    max_val += amplitude
                    amplitude *= persistence
                    frequency *= 2

                # Normalize and apply height offset
                noise_val = (noise_val / max_val) + height_offset
                noise_val = max(-1, min(1, noise_val))  # Clamp to [-1, 1]

                # Get color based on height
                color = self._get_terrain_color(noise_val, params)

                # Add pixel to frame
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": color[0],
                        "g": color[1],
                        "b": color[2],
                    }
                )

        self._time += 0.1
        return pixels
