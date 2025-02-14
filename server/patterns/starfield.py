import random
import math
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Starfield(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="starfield",
            description="Bold 3D starfield effect optimized for 24x25 LED grid with enhanced depth and movement",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="warp",
                    description="Pattern variation (warp, nebula, vortex, pulse, shower)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Star movement speed",
                ),
                Parameter(
                    name="num_stars",
                    type=int,
                    default=30,
                    min_value=10,
                    max_value=50,
                    description="Number of stars (reduced for clearer visuals)",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="white",
                    description="Star color mode (white, rainbow, heat, cool)",
                ),
                Parameter(
                    name="size",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=3,
                    description="Maximum star size (1-3 pixels)",
                ),
            ],
            category="animations",
            tags=["stars", "space", "3D"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.stars = []  # List of (x, y, z, size) coordinates
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._step = 0

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

    def _get_star_color(
        self, brightness: float, color_mode: str, z: float
    ) -> tuple[int, int, int]:
        """Get star color based on color mode and brightness"""
        if color_mode == "rainbow":
            hue = (z + self._step * 0.01) % 1.0
            return self._hsv_to_rgb(hue, 0.5, brightness)
        elif color_mode == "heat":
            # Red to yellow gradient
            r = int(255 * brightness)
            g = int(255 * brightness * (1 - z * 0.7))
            return (r, g, 0)
        elif color_mode == "cool":
            # Blue to cyan gradient
            b = int(255 * brightness)
            g = int(255 * brightness * (1 - z * 0.7))
            return (0, g, b)
        else:  # white
            val = int(brightness * 255)
            return (val, val, val)

    def init_stars(self, num_stars: int, max_size: int):
        """Initialize star positions with size"""
        self.stars = []
        for _ in range(num_stars):
            # Random 3D position and size
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            z = random.uniform(0, 1)
            size = random.randint(1, max_size)
            self.stars.append([x, y, z, size])

    def project_star(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Project 3D coordinates to 2D screen space with enhanced perspective"""
        if z <= 0:
            z = 0.001  # Prevent division by zero

        # Apply enhanced perspective projection
        factor = 0.6 / z  # Increased factor for more dramatic perspective
        screen_x = self._center_x + x * factor * self.width
        screen_y = self._center_y + y * factor * self.height

        # Enhanced brightness calculation
        brightness = math.pow(1.0 - z, 1.2)  # Added curve for more contrast

        return screen_x, screen_y, brightness

    def _update_warp(self, star: List[float], speed: float) -> List[float]:
        """Warp speed effect with slight curve"""
        x, y, z, size = star
        z -= speed * 0.02
        # Add slight curve to movement
        angle = z * math.pi * 0.2
        x += math.sin(angle) * 0.01
        y += math.cos(angle) * 0.01
        return [x, y, z, size]

    def _update_nebula(self, star: List[float], speed: float) -> List[float]:
        """Nebula-like swirling movement"""
        x, y, z, size = star
        z -= speed * 0.015
        angle = self._step * speed * 0.01
        x = math.cos(angle) * star[0] - math.sin(angle) * star[1]
        y = math.sin(angle) * star[0] + math.cos(angle) * star[1]
        return [x, y, z, size]

    def _update_vortex(self, star: List[float], speed: float) -> List[float]:
        """Vortex-like spiral movement"""
        x, y, z, size = star
        z -= speed * 0.02
        strength = (1 - z) * 2  # Stronger effect as stars get closer
        angle = z * math.pi * strength
        x = math.cos(angle) * star[0] - math.sin(angle) * star[1]
        y = math.sin(angle) * star[0] + math.cos(angle) * star[1]
        return [x, y, z, size]

    def _update_pulse(self, star: List[float], speed: float) -> List[float]:
        """Pulsing movement with size variation"""
        x, y, z, size = star
        z -= speed * 0.02
        # Add subtle size pulsing
        pulse = math.sin(self._step * speed * 0.1 + z * math.pi) * 0.5 + 0.5
        new_size = max(1, min(3, size * (0.8 + pulse * 0.4)))
        return [x, y, z, new_size]

    def _update_shower(self, star: List[float], speed: float) -> List[float]:
        """Meteor shower effect with diagonal movement"""
        x, y, z, size = star
        z -= speed * 0.02
        x += speed * 0.01  # Diagonal movement
        y += speed * 0.01
        return [x, y, z, size]

    def _draw_star(
        self, x: int, y: int, size: int, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a star with the given size"""
        pixels = []
        for dy in range(size):
            for dx in range(size):
                px, py = x + dx, y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(px, py),
                            "r": color[0],
                            "g": color[1],
                            "b": color[2],
                        }
                    )
        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the starfield pattern"""
        params = self.validate_params(params)
        variation = params["variation"]
        speed = params["speed"]
        num_stars = params["num_stars"]
        color_mode = params["color_mode"]
        max_size = params["size"]

        # Initialize stars if needed
        if len(self.stars) != num_stars:
            self.init_stars(num_stars, max_size)

        pixels = []
        new_stars = []

        for star in self.stars:
            # Update star position based on variation
            if variation == "nebula":
                new_star = self._update_nebula(star, speed)
            elif variation == "vortex":
                new_star = self._update_vortex(star, speed)
            elif variation == "pulse":
                new_star = self._update_pulse(star, speed)
            elif variation == "shower":
                new_star = self._update_shower(star, speed)
            else:  # warp
                new_star = self._update_warp(star, speed)

            x, y, z, size = new_star

            # Reset star if it goes out of bounds
            if z <= 0 or z >= 1 or x < -2 or x > 2 or y < -2 or y > 2:
                x = random.uniform(-1, 1)
                y = random.uniform(-1, 1)
                z = 1
                size = random.randint(1, max_size)
                new_star = [x, y, z, size]

            new_stars.append(new_star)

            # Project star to screen space
            screen_x, screen_y, brightness = self.project_star(x, y, z)

            # Add star to frame if it's within bounds
            if (
                0 <= screen_x < self.width - size + 1
                and 0 <= screen_y < self.height - size + 1
            ):
                color = self._get_star_color(brightness, color_mode, z)
                pixels.extend(
                    self._draw_star(int(screen_x), int(screen_y), int(size), color)
                )

        self.stars = new_stars
        self._step += 1
        return self._ensure_all_pixels_handled(pixels)
