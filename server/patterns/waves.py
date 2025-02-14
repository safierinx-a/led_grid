import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Waves(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="waves",
            description="Bold wave patterns optimized for 24x25 LED grid with enhanced visual effects",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="pulse",
                    description="Wave variation (pulse, vortex, cross, crystal, cascade)",
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
                    name="scale",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    description="Wave scale/frequency",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="ocean",
                    description="Color mode (ocean, plasma, neon, mono, rainbow)",
                ),
                Parameter(
                    name="intensity",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    description="Wave intensity and contrast",
                ),
            ],
            category="animations",
            tags=["waves", "water", "physics"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._wave_sources = self._init_wave_sources()

    def _init_wave_sources(self) -> List[tuple[float, float, float]]:
        """Initialize wave source positions and phases"""
        sources = []
        # Corner sources
        sources.extend(
            [
                (0, 0, 0),
                (self.width - 1, 0, math.pi / 2),
                (0, self.height - 1, math.pi),
                (self.width - 1, self.height - 1, math.pi * 1.5),
            ]
        )
        # Center source
        sources.append((self._center_x, self._center_y, 0))
        return sources

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
        """Convert HSV color to RGB"""
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

    def _get_color(
        self, value: float, color_mode: str, intensity: float
    ) -> tuple[int, int, int]:
        """Get enhanced color based on wave value and color mode"""
        # Enhance contrast
        value = math.pow((value + 1) / 2, intensity)

        if color_mode == "ocean":
            # Deep ocean blues with white caps
            if value > 0.8:
                # White caps
                v = (value - 0.8) * 5  # Scale 0.8-1.0 to 0-1
                return (
                    int(200 * v + 55),
                    int(220 * v + 35),
                    int(255 * v),
                )
            else:
                # Deep blues
                v = value * 1.25  # Scale 0-0.8 to 0-1
                return (0, int(100 * v), int(200 * v + 55))

        elif color_mode == "plasma":
            # Hot plasma colors
            hue = value * 0.2  # Red to yellow range
            return self._hsv_to_rgb(hue, 0.8, value)

        elif color_mode == "neon":
            # Bright neon colors
            hue = (value * 0.5 + self._step * 0.01) % 1.0
            return self._hsv_to_rgb(hue, 1.0, value * 0.8 + 0.2)

        elif color_mode == "rainbow":
            # Full rainbow spectrum
            hue = value
            return self._hsv_to_rgb(hue, 1.0, 1.0)

        else:  # mono
            # High contrast monochrome
            v = int(value * 255)
            return (v, v, v)

    def _generate_pulse(self, x: float, y: float, params: Dict[str, Any]) -> float:
        """Generate pulsing wave pattern"""
        speed = params["speed"]
        scale = params["scale"]
        time = self._step * speed * 0.05

        # Calculate distance from center
        dx = x - self._center_x
        dy = y - self._center_y
        distance = math.sqrt(dx * dx + dy * dy)

        # Create multiple expanding rings
        value = 0
        for i in range(3):
            phase = time - i * math.pi / 2
            value += math.sin(distance * scale * 0.2 - phase) * (0.5 - i * 0.1)

        return value

    def _generate_vortex(self, x: float, y: float, params: Dict[str, Any]) -> float:
        """Generate spiral vortex pattern"""
        speed = params["speed"]
        scale = params["scale"]
        time = self._step * speed * 0.05

        # Calculate polar coordinates
        dx = x - self._center_x
        dy = y - self._center_y
        distance = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)

        # Create spiral wave
        spiral = math.sin(distance * scale * 0.2 + angle * 3 - time)
        rotation = math.sin(angle * 2 + time * 2)

        return (spiral + rotation) * 0.5

    def _generate_cross(self, x: float, y: float, params: Dict[str, Any]) -> float:
        """Generate crossing wave pattern"""
        speed = params["speed"]
        scale = params["scale"]
        time = self._step * speed * 0.05

        # Create perpendicular waves
        horizontal = math.sin(x * scale * 0.4 + time)
        vertical = math.sin(y * scale * 0.4 - time * 1.2)

        # Add diagonal waves
        diagonal1 = math.sin((x + y) * scale * 0.2 + time * 0.7) * 0.5
        diagonal2 = math.sin((x - y) * scale * 0.2 - time * 0.5) * 0.5

        return (horizontal + vertical + diagonal1 + diagonal2) * 0.25

    def _generate_crystal(self, x: float, y: float, params: Dict[str, Any]) -> float:
        """Generate crystalline pattern with sharp transitions"""
        speed = params["speed"]
        scale = params["scale"]
        time = self._step * speed * 0.05

        # Create angular pattern
        dx = x - self._center_x
        dy = y - self._center_y
        angle = math.atan2(dy, dx) * 6  # Six-fold symmetry
        distance = math.sqrt(dx * dx + dy * dy)

        # Combine angular and radial components
        angular = math.cos(angle)
        radial = math.sin(distance * scale * 0.2 - time)

        # Create sharp transitions
        value = angular * radial
        value = math.copysign(math.pow(abs(value), 0.7), value)  # Sharpen edges

        return value

    def _generate_cascade(self, x: float, y: float, params: Dict[str, Any]) -> float:
        """Generate cascading waves from multiple sources"""
        speed = params["speed"]
        scale = params["scale"]
        time = self._step * speed * 0.05

        value = 0
        for sx, sy, phase in self._wave_sources:
            # Calculate distance from source
            dx = x - sx
            dy = y - sy
            distance = math.sqrt(dx * dx + dy * dy)

            # Add wave from this source
            source_value = math.sin(distance * scale * 0.3 - time + phase)
            value += source_value * (1 - min(1, distance / (self.width * 0.7)))

        return value / len(self._wave_sources)

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        variation = params["variation"]
        color_mode = params["color_mode"]
        intensity = params["intensity"]

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Generate wave value based on variation
                if variation == "vortex":
                    value = self._generate_vortex(x, y, params)
                elif variation == "cross":
                    value = self._generate_cross(x, y, params)
                elif variation == "crystal":
                    value = self._generate_crystal(x, y, params)
                elif variation == "cascade":
                    value = self._generate_cascade(x, y, params)
                else:  # pulse
                    value = self._generate_pulse(x, y, params)

                # Get color and add pixel
                r, g, b = self._get_color(value, color_mode, intensity)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        self._step += 1
        return pixels
