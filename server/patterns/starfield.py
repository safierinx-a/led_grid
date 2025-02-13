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
            description="3D starfield effect with perspective",
            parameters=[
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
                    default=50,
                    min_value=10,
                    max_value=200,
                    description="Number of stars",
                ),
                Parameter(
                    name="direction",
                    type=str,
                    default="forward",
                    description="Movement direction (forward/backward/spiral)",
                ),
            ],
            category="animations",
            tags=["stars", "space", "3D"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.stars = []  # List of (x, y, z) coordinates
        self._center_x = self.width / 2
        self._center_y = self.height / 2

    def init_stars(self, num_stars: int):
        """Initialize star positions"""
        self.stars = []
        for _ in range(num_stars):
            # Random 3D position
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            z = random.uniform(0, 1)
            self.stars.append([x, y, z])

    def project_star(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Project 3D coordinates to 2D screen space with perspective"""
        if z <= 0:
            z = 0.001  # Prevent division by zero

        # Apply perspective projection
        factor = 0.5 / z
        screen_x = self._center_x + x * factor * self.width
        screen_y = self._center_y + y * factor * self.height

        # Brightness based on distance (closer = brighter)
        brightness = 1.0 - z

        return screen_x, screen_y, brightness

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        speed = params["speed"]
        num_stars = params["num_stars"]
        direction = params["direction"]

        # Initialize stars if needed
        if len(self.stars) != num_stars:
            self.init_stars(num_stars)

        pixels = []
        new_stars = []

        for star in self.stars:
            x, y, z = star

            # Update star position based on direction
            if direction == "forward":
                z -= speed * 0.02
            elif direction == "backward":
                z += speed * 0.02
            elif direction == "spiral":
                z -= speed * 0.02
                angle = z * math.pi
                x = math.cos(angle) * star[0] - math.sin(angle) * star[1]
                y = math.sin(angle) * star[0] + math.cos(angle) * star[1]

            # Reset star if it goes out of bounds
            if z <= 0 or z >= 1:
                x = random.uniform(-1, 1)
                y = random.uniform(-1, 1)
                z = 1 if z <= 0 else 0

            new_stars.append([x, y, z])

            # Project star to screen space
            screen_x, screen_y, brightness = self.project_star(x, y, z)

            # Add star to frame if it's within bounds
            if 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                # Calculate color (white with distance-based brightness)
                intensity = int(brightness * 255)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(
                            int(screen_x), int(screen_y)
                        ),
                        "r": intensity,
                        "g": intensity,
                        "b": intensity,
                    }
                )

        self.stars = new_stars
        return pixels
