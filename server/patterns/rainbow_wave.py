from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry
import math


@PatternRegistry.register
class RainbowWave(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="rainbow_wave",
            description="Bold, grid-optimized rainbow patterns designed for 24x25 LED matrix",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="bold",
                    description="Wave variation (bold, quad, edge, bands, grid)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=10.0,
                    description="Speed of the wave movement",
                ),
                Parameter(
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Scale of the wave pattern",
                ),
                Parameter(
                    name="thickness",
                    type=int,
                    default=3,
                    min_value=2,
                    max_value=4,
                    description="Thickness of wave lines (2-4 pixels)",
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
                    name="brightness",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Overall brightness",
                ),
                Parameter(
                    name="contrast",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    description="Color contrast between waves",
                ),
            ],
            category="animations",
            tags=["rainbow", "wave", "colorful"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
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

    def _generate_classic_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Classic diagonal rainbow wave"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        saturation = params["saturation"]
        brightness = params["brightness"]

        for y in range(self.height):
            for x in range(self.width):
                # Calculate wave value
                wave = (x + y + self._step * speed) * scale
                hue = (wave % 100) / 100.0

                # Get color and create pixel
                r, g, b = self.hsv_to_rgb(hue, saturation, brightness)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )
        return pixels

    def _generate_bold_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Bold single wave with enhanced thickness and contrast"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        thickness = params["thickness"]
        saturation = params["saturation"]
        brightness = params["brightness"]
        contrast = params["contrast"]

        # Calculate diagonal wave position optimized for 24x25 grid
        wave_pos = (self._step * speed) % (self.width + self.height)

        for y in range(self.height):
            for x in range(self.width):
                # Calculate distance to diagonal wave front
                diagonal_pos = (x + y) % (self.width + self.height)
                dist = min(
                    (diagonal_pos - wave_pos) % (self.width + self.height),
                    (wave_pos - diagonal_pos) % (self.width + self.height),
                )

                # Create bold wave with sharp edges
                if dist < thickness:
                    # Enhanced color contrast
                    hue = (
                        diagonal_pos / (self.width + self.height)
                        + self._step * speed * 0.1
                    ) % 1.0
                    # Apply contrast enhancement
                    v = brightness * (1.0 + (contrast - 1.0) * (1.0 - dist / thickness))
                    r, g, b = self.hsv_to_rgb(hue, saturation, min(1.0, v))
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": r,
                            "g": g,
                            "b": b,
                        }
                    )
                else:
                    # Add subtle background glow
                    bg_hue = ((diagonal_pos / (self.width + self.height)) + 0.5) % 1.0
                    r, g, b = self.hsv_to_rgb(
                        bg_hue, saturation * 0.5, brightness * 0.2
                    )
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": r,
                            "g": g,
                            "b": b,
                        }
                    )
        return pixels

    def _generate_quad_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Four distinct interacting wave patterns with clear quadrant separation"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        saturation = params["saturation"]
        brightness = params["brightness"]
        contrast = params["contrast"]

        # Define quadrant boundaries
        mid_x = self.width // 2
        mid_y = self.height // 2

        # Define distinct color offsets for each quadrant
        quadrant_colors = [0.0, 0.25, 0.5, 0.75]  # Different base hues

        for y in range(self.height):
            for x in range(self.width):
                # Determine quadrant
                quad_x = 0 if x < mid_x else 1
                quad_y = 0 if y < mid_y else 1
                quadrant = quad_y * 2 + quad_x

                # Calculate local coordinates within quadrant
                local_x = x if x < mid_x else x - mid_x
                local_y = y if y < mid_y else y - mid_y

                # Generate wave pattern specific to quadrant
                wave_val = math.sin(
                    (local_x + local_y) * scale * 0.2
                    + self._step * speed * (1.0 + quadrant * 0.1)
                )

                # Add quadrant-specific color and enhance contrast
                hue = (quadrant_colors[quadrant] + wave_val * 0.2) % 1.0
                v = brightness * (0.7 + wave_val * 0.3 * contrast)

                r, g, b = self.hsv_to_rgb(hue, saturation, min(1.0, v))
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )
        return pixels

    def _generate_edge_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Enhanced waves emanating from edges with clear wave fronts"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        thickness = params["thickness"]
        saturation = params["saturation"]
        brightness = params["brightness"]
        contrast = params["contrast"]

        for y in range(self.height):
            for x in range(self.width):
                # Calculate distance from each edge
                dist_left = x
                dist_right = self.width - 1 - x
                dist_top = y
                dist_bottom = self.height - 1 - y

                # Calculate wave values from each edge
                time = self._step * speed
                wave_left = math.sin(dist_left * scale * 0.5 + time)
                wave_right = math.sin(dist_right * scale * 0.5 + time + math.pi)
                wave_top = math.sin(dist_top * scale * 0.5 + time + math.pi * 0.5)
                wave_bottom = math.sin(dist_bottom * scale * 0.5 + time + math.pi * 1.5)

                # Combine waves with distance-based attenuation
                wave_val = max(
                    wave_left * (1 - dist_left / self.width),
                    wave_right * (1 - dist_right / self.width),
                    wave_top * (1 - dist_top / self.height),
                    wave_bottom * (1 - dist_bottom / self.height),
                )

                # Create pronounced wave fronts
                wave_val = math.pow(wave_val * 0.5 + 0.5, contrast)
                hue = (wave_val + time * 0.1) % 1.0

                r, g, b = self.hsv_to_rgb(hue, saturation, brightness * wave_val)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )
        return pixels

    def _generate_bands(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Thick color bands with sharp transitions"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        thickness = max(3, params["thickness"])  # Ensure minimum thickness of 3
        saturation = params["saturation"]
        brightness = params["brightness"]
        contrast = params["contrast"]

        # Calculate optimal band width for grid size
        band_width = thickness * 2
        diagonal_length = math.sqrt(self.width * self.width + self.height * self.height)

        for y in range(self.height):
            for x in range(self.width):
                # Calculate diagonal position for smooth band flow
                pos = (x + y + self._step * speed) * scale
                band_pos = int(pos / band_width)

                # Calculate position within band for edge highlighting
                band_offset = (pos % band_width) / band_width

                # Create sharp transitions between bands
                edge_highlight = max(0, 1.0 - abs(band_offset - 0.5) * 4)
                hue = (band_pos / 6) % 1.0  # 6 distinct bands

                # Apply contrast and edge highlighting
                v = brightness * (0.7 + 0.3 * edge_highlight * contrast)

                r, g, b = self.hsv_to_rgb(hue, saturation, min(1.0, v))
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )
        return pixels

    def _generate_grid_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Enhanced waves that follow grid lines with pronounced intersections"""
        pixels = []
        speed = params["speed"]
        scale = params["scale"]
        thickness = params["thickness"]
        saturation = params["saturation"]
        brightness = params["brightness"]
        contrast = params["contrast"]

        for y in range(self.height):
            for x in range(self.width):
                # Calculate grid-aligned waves
                h_wave = math.sin(x * scale * 0.5 + self._step * speed)
                v_wave = math.sin(y * scale * 0.5 + self._step * speed * 1.1)

                # Calculate distance to nearest grid line
                h_dist = min(y % 4, 4 - (y % 4))  # Horizontal grid lines every 4 pixels
                v_dist = min(x % 4, 4 - (x % 4))  # Vertical grid lines every 4 pixels
                grid_dist = min(h_dist, v_dist)

                # Create pronounced grid effect
                grid_intensity = max(0, 1.0 - grid_dist / thickness)
                wave_val = (h_wave + v_wave) * 0.5 * grid_intensity

                # Enhance intersections
                is_intersection = grid_dist < 1.0 and h_dist < 2 and v_dist < 2
                if is_intersection:
                    wave_val = wave_val * 1.5

                # Calculate final color
                hue = (wave_val * 0.3 + self._step * speed * 0.1) % 1.0
                v = brightness * (0.3 + 0.7 * grid_intensity * contrast)

                r, g, b = self.hsv_to_rgb(hue, saturation, min(1.0, v))
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )
        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the rainbow wave pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "wave":
            pattern_pixels = self._generate_wave(params)
        elif variation == "ripple":
            pattern_pixels = self._generate_ripple(params)
        elif variation == "spiral":
            pattern_pixels = self._generate_spiral(params)
        elif variation == "pulse":
            pattern_pixels = self._generate_pulse(params)
        else:  # flow
            pattern_pixels = self._generate_flow(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
