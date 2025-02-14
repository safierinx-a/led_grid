import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ColorCycle(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="color_cycle",
            description="Dynamic color cycling patterns with multiple artistic variations",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="radial",
                    description="Pattern variation (radial, wave, spiral, blocks, gradient, ripple, vortex, pulse, mosaic)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Color cycling speed",
                ),
                Parameter(
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=3.0,
                    description="Pattern scale factor",
                ),
                Parameter(
                    name="palette",
                    type=str,
                    default="rainbow",
                    description="Color palette (rainbow, sunset, ocean, neon)",
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
                    name="block_size",
                    type=int,
                    default=4,
                    min_value=2,
                    max_value=8,
                    description="Block size for block-based variations",
                ),
                Parameter(
                    name="symmetry",
                    type=int,
                    default=4,
                    min_value=1,
                    max_value=8,
                    description="Symmetry factor for symmetrical variations",
                ),
                Parameter(
                    name="blend",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Blend factor for combining patterns",
                ),
            ],
            category="animations",
            tags=["color", "cycle", "waves"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
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

    def _get_palette_color(
        self, value: float, palette: str, contrast: float
    ) -> tuple[int, int, int]:
        """Get color from selected palette"""
        value = (value * contrast) % 1.0

        if palette == "rainbow":
            return self._hsv_to_rgb(value, 1.0, 1.0)
        elif palette == "sunset":
            # Cycle through red-orange-purple
            if value < 0.5:
                # Red to orange
                return self._hsv_to_rgb(value * 0.2, 1.0, 1.0)
            else:
                # Orange to purple
                return self._hsv_to_rgb(0.1 + (value - 0.5) * 0.6, 1.0, 1.0)
        elif palette == "ocean":
            # Cycle through blue-green-cyan
            return self._hsv_to_rgb(0.5 + value * 0.3, 1.0, 1.0)
        else:  # neon
            # Cycle through vibrant neon colors
            hue = value * 0.8 + 0.1  # Avoid pure red
            return self._hsv_to_rgb(hue, 1.0, 1.0)

    def _generate_radial(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced radial color pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                x = bx + block_size / 2
                y = by + block_size / 2

                # Calculate distance from center with symmetry
                dx = x - self._center_x
                dy = y - self._center_y
                distance = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Create radial pattern with symmetrical variations
                base = (distance * scale * 0.2 + time) % 1.0
                wave = math.sin(angle * symmetry + time * 2) * blend * 0.5

                value = (base + wave) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_wave(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced diagonal wave pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                x = bx + block_size / 2
                y = by + block_size / 2

                # Create multiple interfering waves
                wave1 = math.sin((x + y) * scale * 0.1 + time)
                wave2 = math.sin((x - y) * scale * 0.1 - time * 1.2)

                # Blend waves with enhanced contrast
                value = (
                    (wave1 * (1 - blend) + wave2 * blend + 2) / 4 + time * 0.1
                ) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_spiral(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced spiral pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                x = bx + block_size / 2
                y = by + block_size / 2

                # Calculate polar coordinates
                dx = x - self._center_x
                dy = y - self._center_y
                angle = math.atan2(dy, dx)
                distance = math.sqrt(dx * dx + dy * dy)

                # Create spiral with symmetrical arms
                base_spiral = (
                    angle * symmetry / (2 * math.pi) + distance * scale * 0.1 + time
                ) % 1.0
                wave = math.sin(distance * scale * 0.2 - time * 2) * blend * 0.5

                value = (base_spiral + wave) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_blocks(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced block pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05
        pattern_size = max(2, int(4 * scale))

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate pattern coordinates
                px = bx // pattern_size
                py = by // pattern_size

                # Create checkerboard with temporal variation
                pattern1 = ((px + py) * 0.5 + time) % 1.0
                pattern2 = math.sin(px * scale + time) * math.cos(
                    py * scale + time * 1.2
                )

                value = (pattern1 * (1 - blend) + (pattern2 + 1) * 0.5 * blend) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_gradient(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced gradient pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate normalized coordinates
                nx = bx / self.width
                ny = by / self.height

                # Create dynamic gradients
                grad1 = (ny * scale + time) % 1.0
                grad2 = (nx * scale - time * 1.2) % 1.0
                grad3 = ((nx + ny) * scale * 0.5 + time * 0.7) % 1.0

                # Blend gradients with smooth transitions
                value = (
                    grad1 * (1 - blend) * 0.4
                    + grad2 * blend * 0.4
                    + grad3 * 0.2
                    + time * 0.1
                ) % 1.0

                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_ripple(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate enhanced ripple pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        # Create multiple ripple sources
        sources = []
        for i in range(symmetry):
            angle = i * 2 * math.pi / symmetry
            radius = self.width * 0.3
            x = self._center_x + math.cos(angle + time) * radius
            y = self._center_y + math.sin(angle + time) * radius
            sources.append((x, y))

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate block center
                x = bx + block_size / 2
                y = by + block_size / 2

                # Combine ripples from all sources
                value = 0
                for sx, sy in sources:
                    dx = x - sx
                    dy = y - sy
                    distance = math.sqrt(dx * dx + dy * dy)
                    value += math.sin(distance * scale * 0.2 - time * 2)

                # Normalize and enhance
                value = ((value / len(sources) + 1) * 0.5 + time * 0.1) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _draw_block(
        self, x: int, y: int, size: int, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a block of pixels with the given color"""
        pixels = []
        for dy in range(size):
            for dx in range(size):
                px, py = x + dx, y + dy
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

    def _generate_vortex(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate dynamic vortex pattern"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate center of block
                x = bx + block_size / 2
                y = by + block_size / 2

                # Calculate polar coordinates
                dx = x - self._center_x
                dy = y - self._center_y
                distance = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Create vortex effect with symmetry
                base_value = (
                    angle / (2 * math.pi) * symmetry + distance * scale * 0.1 + time
                ) % 1.0

                # Add turbulence
                turbulence = math.sin(distance * 0.2 + time * 2) * blend

                value = (base_value + turbulence) % 1.0
                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_pulse(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate pulsing pattern with symmetrical waves"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate center of block
                x = bx + block_size / 2
                y = by + block_size / 2

                # Calculate polar coordinates
                dx = x - self._center_x
                dy = y - self._center_y
                distance = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Create pulsing waves
                wave1 = math.sin(distance * scale * 0.2 - time * 2)
                wave2 = math.sin(angle * symmetry + time)

                # Combine waves with blend
                value = (
                    (wave1 * (1 - blend) + wave2 * blend + 2) / 4 + time * 0.1
                ) % 1.0

                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def _generate_mosaic(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate mosaic pattern with dynamic tiles"""
        speed = params["speed"]
        scale = params["scale"]
        palette = params["palette"]
        contrast = params["contrast"]
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        time = self._step * speed * 0.05
        tile_size = max(2, int(4 * scale))

        for by in range(0, self.height, block_size):
            for bx in range(0, self.width, block_size):
                # Calculate tile coordinates
                tile_x = bx // tile_size
                tile_y = by // tile_size

                # Create mosaic pattern
                pattern1 = math.sin(tile_x * symmetry + time)
                pattern2 = math.sin(tile_y * symmetry + time * 1.5)
                pattern3 = math.sin((tile_x + tile_y) * symmetry * 0.5 + time * 0.7)

                # Combine patterns with blend
                value = (
                    pattern1 * (1 - blend) * 0.5
                    + pattern2 * blend * 0.5
                    + pattern3 * 0.5
                    + time * 0.1
                ) % 1.0

                color = self._get_palette_color(value, palette, contrast)
                pixels.extend(self._draw_block(bx, by, block_size, color))

        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the color cycle pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "rainbow":
            pattern_pixels = self._generate_rainbow(params)
        elif variation == "gradient":
            pattern_pixels = self._generate_gradient(params)
        elif variation == "pulse":
            pattern_pixels = self._generate_pulse(params)
        elif variation == "wave":
            pattern_pixels = self._generate_wave(params)
        else:  # spectrum
            pattern_pixels = self._generate_spectrum(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
