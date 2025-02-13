import random
import math
import numpy as np
from typing import Dict, Any, List
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class GenerativeArt(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="generative",
            description="Abstract generative art patterns",
            parameters=[
                Parameter(
                    name="algorithm",
                    type=str,
                    default="flow_field",
                    description="Algorithm type (flow_field/voronoi/maze/fractal)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="complexity",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Pattern complexity",
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
            category="art",
            tags=["generative", "abstract", "art"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._noise_scale = 0.1
        self._particles = []
        self._voronoi_points = []
        self._maze = None
        self._fractal_buffer = None

    def init_particles(self, num_particles: int):
        """Initialize particles for flow field"""
        self._particles = []
        for _ in range(num_particles):
            self._particles.append(
                {
                    "x": random.uniform(0, self.width),
                    "y": random.uniform(0, self.height),
                    "age": random.uniform(0, 1),
                }
            )

    def init_voronoi(self, num_points: int):
        """Initialize Voronoi points"""
        self._voronoi_points = []
        for _ in range(num_points):
            self._voronoi_points.append(
                {
                    "x": random.uniform(0, self.width),
                    "y": random.uniform(0, self.height),
                    "hue": random.random(),
                }
            )

    def init_maze(self):
        """Initialize maze grid"""
        self._maze = np.zeros((self.height, self.width), dtype=int)
        # Create simple maze pattern
        for y in range(self.height):
            for x in range(self.width):
                if (x + y) % 2 == 0:
                    self._maze[y, x] = 1

    def init_fractal(self):
        """Initialize fractal buffer"""
        self._fractal_buffer = np.zeros((self.height, self.width), dtype=float)

    def get_flow_field_value(
        self, x: float, y: float, time: float, complexity: float
    ) -> float:
        """Calculate flow field angle at position"""
        nx = x * complexity * 0.1
        ny = y * complexity * 0.1
        angle = (
            math.sin(nx + time) * math.cos(ny - time * 0.5) * math.pi
            + math.sin(nx * 0.5 - time * 0.2)
            * math.cos(ny * 0.8 + time * 0.3)
            * math.pi
        )
        return angle

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

    def generate_flow_field(
        self, speed: float, complexity: float, color_shift: float
    ) -> List[Dict[str, int]]:
        """Generate flow field pattern"""
        if not self._particles:
            self.init_particles(50)

        pixels = []
        new_particles = []

        for particle in self._particles:
            x, y = particle["x"], particle["y"]
            if 0 <= x < self.width and 0 <= y < self.height:
                # Get flow direction
                angle = self.get_flow_field_value(x, y, self._time, complexity)

                # Update position
                dx = math.cos(angle) * speed
                dy = math.sin(angle) * speed
                new_x = (x + dx) % self.width
                new_y = (y + dy) % self.height

                # Update age and add pixel
                age = particle["age"]
                hue = (age + self._time * 0.1 + color_shift) % 1.0
                r, g, b = self.hsv_to_rgb(hue, 1.0, age)

                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(int(x), int(y)),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

                new_particles.append(
                    {"x": new_x, "y": new_y, "age": max(0, age - 0.01)}
                )

            if particle["age"] <= 0:
                # Respawn particle
                new_particles.append(
                    {
                        "x": random.uniform(0, self.width),
                        "y": random.uniform(0, self.height),
                        "age": 1.0,
                    }
                )

        self._particles = new_particles
        return pixels

    def generate_voronoi(
        self, speed: float, complexity: float, color_shift: float
    ) -> List[Dict[str, int]]:
        """Generate Voronoi pattern"""
        if not self._voronoi_points:
            self.init_voronoi(int(5 + complexity * 5))

        pixels = []
        # Move points in circular patterns
        for point in self._voronoi_points:
            angle = self._time * speed
            point["x"] = (point["x"] + math.cos(angle) * 0.1) % self.width
            point["y"] = (point["y"] + math.sin(angle) * 0.1) % self.height

        # Generate pixels
        for y in range(self.height):
            for x in range(self.width):
                # Find closest point
                min_dist = float("inf")
                closest_hue = 0
                for point in self._voronoi_points:
                    dx = x - point["x"]
                    dy = y - point["y"]
                    dist = dx * dx + dy * dy
                    if dist < min_dist:
                        min_dist = dist
                        closest_hue = point["hue"]

                # Calculate color
                hue = (closest_hue + self._time * 0.1 + color_shift) % 1.0
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

    def generate_maze(
        self, speed: float, complexity: float, color_shift: float
    ) -> List[Dict[str, int]]:
        """Generate animated maze pattern"""
        if self._maze is None:
            self.init_maze()

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                if self._maze[y, x]:
                    # Calculate color based on position and time
                    dist = math.sqrt(
                        (x - self.width / 2) ** 2 + (y - self.height / 2) ** 2
                    )
                    hue = (dist * 0.1 + self._time * speed + color_shift) % 1.0
                    r, g, b = self.hsv_to_rgb(hue, 1.0, 1.0)
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": r,
                            "g": g,
                            "b": b,
                        }
                    )

        # Randomly change some cells
        if random.random() < 0.1 * speed:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self._maze[y, x] = 1 - self._maze[y, x]

        return pixels

    def generate_fractal(
        self, speed: float, complexity: float, color_shift: float
    ) -> List[Dict[str, int]]:
        """Generate fractal pattern"""
        if self._fractal_buffer is None:
            self.init_fractal()

        pixels = []
        scale = complexity * 0.1

        for y in range(self.height):
            for x in range(self.width):
                # Generate fractal value using multiple sine waves
                nx = x * scale
                ny = y * scale
                value = math.sin(nx + self._time) * math.cos(ny - self._time * 0.5)
                value += (
                    math.sin(nx * 2 + self._time * 0.7)
                    * math.cos(ny * 2 - self._time * 0.3)
                    * 0.5
                )
                value += (
                    math.sin(nx * 4 + self._time * 0.3)
                    * math.cos(ny * 4 - self._time * 0.7)
                    * 0.25
                )

                # Normalize and convert to color
                value = (value + 2) / 4
                hue = (value + self._time * speed * 0.1 + color_shift) % 1.0
                r, g, b = self.hsv_to_rgb(hue, 1.0, value)

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
        params = self.validate_params(params)
        algorithm = params["algorithm"]
        speed = params["speed"]
        complexity = params["complexity"]
        color_shift = params["color_shift"]

        self._time += 0.05 * speed

        if algorithm == "flow_field":
            return self.generate_flow_field(speed, complexity, color_shift)
        elif algorithm == "voronoi":
            return self.generate_voronoi(speed, complexity, color_shift)
        elif algorithm == "maze":
            return self.generate_maze(speed, complexity, color_shift)
        else:  # fractal
            return self.generate_fractal(speed, complexity, color_shift)
