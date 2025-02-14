import random
import math
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import (
    Pattern,
    PatternDefinition,
    Parameter,
    PatternRegistry,
    Point,
)
import time


@PatternRegistry.register
class GenerativeArt(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="generative",
            description="Bold generative art patterns optimized for 24x25 LED grid with dynamic algorithms",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="flow_field",
                    description="Pattern variation (flow_field, voronoi, maze, fractal, cellular, swarm, crystal, circuit)",
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
                    name="color_mode",
                    type=str,
                    default="rainbow",
                    description="Color mode (rainbow, neon, mono, heat, cyber)",
                ),
                Parameter(
                    name="color_shift",
                    type=float,
                    default=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color shift amount",
                ),
                Parameter(
                    name="block_size",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=3,
                    description="Size of pattern blocks (1-3 pixels)",
                ),
                Parameter(
                    name="symmetry",
                    type=int,
                    default=4,
                    min_value=1,
                    max_value=8,
                    description="Pattern symmetry (1-8 fold)",
                ),
                Parameter(
                    name="blend",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Pattern blending factor",
                ),
            ],
            category="art",
            tags=["generative", "abstract", "art", "algorithmic"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.step = 0
        self.particles = []
        self.voronoi_points = []
        self.maze_buffer = None
        self.fractal_buffer = None
        self.cellular_buffer = None
        self.swarm_agents = []
        self.crystal_points = []
        self.circuit_paths = []
        self.color_buffer = {}
        self.last_update = time.time()
        self._particles = []  # Initialize particles list

    def _get_color(self, x: float, y: float, t: float, mode: str) -> tuple:
        """Get color based on position, time and color mode."""
        if mode == "rainbow":
            hue = (x + y + t) % 1.0
            sat = 1.0
            val = 1.0
        elif mode == "neon":
            hue = (x + t * 2) % 1.0
            sat = 0.8 + math.sin(y * math.pi) * 0.2
            val = 0.9 + math.sin((x + y) * math.pi) * 0.1
        elif mode == "mono":
            hue = t % 1.0
            sat = 0.1
            val = 0.5 + (math.sin(x * math.pi) + math.cos(y * math.pi)) * 0.25
        elif mode == "heat":
            hue = 0.05 + (math.sin(x * math.pi) + math.cos(y * math.pi)) * 0.1
            sat = 0.8 + math.sin(t * math.pi) * 0.2
            val = 0.7 + math.cos((x + y) * math.pi) * 0.3
        else:  # cyber
            hue = (0.6 + math.sin(t * math.pi) * 0.1) % 1.0
            sat = 0.9
            val = 0.7 + math.sin((x - y) * math.pi) * 0.3

        return self._hsv_to_rgb(hue, sat, val)

    def _apply_symmetry(self, x: int, y: int, symmetry: int) -> list:
        """Generate symmetric points based on input coordinates."""
        points = [(x, y)]
        if symmetry > 1:
            center_x = self.width // 2
            center_y = self.height // 2
            dx = x - center_x
            dy = y - center_y
            angle = 2 * math.pi / symmetry

            for i in range(1, symmetry):
                rot = angle * i
                new_dx = dx * math.cos(rot) - dy * math.sin(rot)
                new_dy = dx * math.sin(rot) + dy * math.cos(rot)
                new_x = int(center_x + new_dx)
                new_y = int(center_y + new_dy)
                if 0 <= new_x < self.width and 0 <= new_y < self.height:
                    points.append((new_x, new_y))

        return points

    def _draw_block(
        self, x: int, y: int, color: tuple[int, int, int], block_size: int, blend: float
    ) -> List[Dict[str, int]]:
        """Draw a block of pixels with blending."""
        pixels = []
        for dx in range(block_size):
            for dy in range(block_size):
                px = x + dx
                py = y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    if blend < 1.0 and (px, py) in self.color_buffer:
                        old_color = self.color_buffer[(px, py)]
                        new_color = tuple(
                            int(old * (1 - blend) + new * blend)
                            for old, new in zip(old_color, color)
                        )
                    else:
                        new_color = color
                    self.color_buffer[(px, py)] = new_color
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(px, py),
                            "r": new_color[0],
                            "g": new_color[1],
                            "b": new_color[2],
                        }
                    )
        return pixels

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
        """Generate a frame of the pattern."""
        # Validate parameters
        params = self.validate_params(params)

        # Get current time
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time

        # Update step counter
        self.step += dt

        # Generate pattern based on selected variation
        variation = params["variation"]
        if variation == "flow_field":
            return self.generate_flow_field(
                params["speed"], params["complexity"], params["color_shift"]
            )
        elif variation == "voronoi":
            return self.generate_voronoi(
                params["speed"], params["complexity"], params["color_shift"]
            )
        elif variation == "maze":
            return self.generate_maze(
                params["speed"], params["complexity"], params["color_shift"]
            )
        elif variation == "fractal":
            return self.generate_fractal(
                params["speed"], params["complexity"], params["color_shift"]
            )
        elif variation == "cellular":
            return self._generate_cellular(params)
        elif variation == "swarm":
            return self._generate_swarm(params)
        elif variation == "crystal":
            return self._generate_crystal(params)
        else:  # circuit
            return self._generate_circuit(params)

    def clear_frame(self) -> List[Dict[str, int]]:
        """Clear the current frame."""
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": 0,
                        "g": 0,
                        "b": 0,
                    }
                )
        return pixels

    def _generate_flow_field(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate flow field pattern with enhanced features."""
        if not self.particles:
            self.init_particles(int(20 * params["complexity"]))

        pixels = []
        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        for particle in self.particles:
            x, y = particle["pos"]
            angle = (math.sin(x * 0.1 + t) + math.cos(y * 0.1 + t)) * math.pi
            dx = math.cos(angle) * params["speed"]
            dy = math.sin(angle) * params["speed"]

            new_x = (x + dx) % self.width
            new_y = (y + dy) % self.height
            particle["pos"] = (new_x, new_y)

            color = self._get_color(
                new_x / self.width, new_y / self.height, t, params["color_mode"]
            )
            points = self._apply_symmetry(int(new_x), int(new_y), symmetry)
            for px, py in points:
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

    def _generate_cellular(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate cellular automaton pattern."""
        if self.cellular_buffer is None:
            self.cellular_buffer = np.random.choice(
                [0, 1], (self.height, self.width), p=[0.6, 0.4]
            )

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        blend = params["blend"]

        new_buffer = np.copy(self.cellular_buffer)
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                neighbors = sum(
                    self.cellular_buffer[(y + dy) % self.height, (x + dx) % self.width]
                    for dx in [-1, 0, 1]
                    for dy in [-1, 0, 1]
                    if dx != 0 or dy != 0
                )
                if self.cellular_buffer[y, x] == 1:
                    new_buffer[y, x] = 1 if 2 <= neighbors <= 3 else 0
                else:
                    new_buffer[y, x] = 1 if neighbors == 3 else 0

                if new_buffer[y, x]:
                    color = self._get_color(
                        x / self.width, y / self.height, t, params["color_mode"]
                    )
                    pixels.extend(self._draw_block(x, y, color, block_size, blend))

        self.cellular_buffer = new_buffer
        return pixels

    def _generate_swarm(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate swarm behavior pattern."""
        if not self.swarm_agents:
            num_agents = int(15 * params["complexity"])
            for _ in range(num_agents):
                self.swarm_agents.append(
                    {
                        "pos": (
                            random.random() * self.width,
                            random.random() * self.height,
                        ),
                        "vel": (random.random() * 2 - 1, random.random() * 2 - 1),
                    }
                )

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        for agent in self.swarm_agents:
            # Update velocity based on neighbors
            cx, cy = 0, 0
            count = 0
            for other in self.swarm_agents:
                if other != agent:
                    dx = other["pos"][0] - agent["pos"][0]
                    dy = other["pos"][1] - agent["pos"][1]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 5:
                        cx += dx / dist
                        cy += dy / dist
                        count += 1

            if count > 0:
                agent["vel"] = (
                    agent["vel"][0] * 0.9 + cx / count * 0.1,
                    agent["vel"][1] * 0.9 + cy / count * 0.1,
                )

            # Update position
            agent["pos"] = (
                (agent["pos"][0] + agent["vel"][0] * params["speed"]) % self.width,
                (agent["pos"][1] + agent["vel"][1] * params["speed"]) % self.height,
            )

            color = self._get_color(
                agent["pos"][0] / self.width,
                agent["pos"][1] / self.height,
                t,
                params["color_mode"],
            )
            points = self._apply_symmetry(
                int(agent["pos"][0]), int(agent["pos"][1]), symmetry
            )
            for px, py in points:
                pixels.extend(self._draw_block(px, py, color, block_size, blend))

        return pixels

    def _generate_crystal(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate crystalline growth pattern."""
        if not self.crystal_points:
            num_seeds = int(3 * params["complexity"])
            for _ in range(num_seeds):
                self.crystal_points.append(
                    (
                        random.randint(0, self.width - 1),
                        random.randint(0, self.height - 1),
                    )
                )

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        growth_points = []
        for x in range(0, self.width, block_size):
            for y in range(0, self.height, block_size):
                min_dist = float("inf")
                for cx, cy in self.crystal_points:
                    dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    min_dist = min(min_dist, dist)

                if min_dist < 3 and random.random() < 0.1 * params["complexity"]:
                    growth_points.append((x, y))

        pixels = []
        for x, y in growth_points:
            self.crystal_points.append((x, y))
            color = self._get_color(
                x / self.width, y / self.height, t, params["color_mode"]
            )
            points = self._apply_symmetry(x, y, symmetry)
            for px, py in points:
                pixels.extend(self._draw_block(px, py, color, block_size, blend))

        return pixels

    def _generate_circuit(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate circuit-like pattern."""
        if not self.circuit_paths:
            num_paths = int(5 * params["complexity"])
            for _ in range(num_paths):
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                self.circuit_paths.append(
                    {
                        "pos": (x, y),
                        "dir": random.choice([(0, 1), (1, 0), (0, -1), (-1, 0)]),
                    }
                )

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        pixels = []
        for path in self.circuit_paths:
            x, y = path["pos"]
            dx, dy = path["dir"]

            new_x = (x + dx * block_size) % self.width
            new_y = (y + dy * block_size) % self.height

            if random.random() < 0.1:
                path["dir"] = random.choice([(0, 1), (1, 0), (0, -1), (-1, 0)])
                if random.random() < 0.3 * params["complexity"]:
                    self.circuit_paths.append(
                        {
                            "pos": (new_x, new_y),
                            "dir": random.choice([(0, 1), (1, 0), (0, -1), (-1, 0)]),
                        }
                    )

            color = self._get_color(
                new_x / self.width, new_y / self.height, t, params["color_mode"]
            )
            points = self._apply_symmetry(int(new_x), int(new_y), symmetry)
            for px, py in points:
                pixels.extend(self._draw_block(px, py, color, block_size, blend))

            path["pos"] = (new_x, new_y)

        if len(self.circuit_paths) > 20 * params["complexity"]:
            self.circuit_paths = self.circuit_paths[: int(20 * params["complexity"])]

        return pixels

    def _generate_voronoi(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate Voronoi pattern with enhanced features."""
        if not self.voronoi_points:
            num_points = int(5 * params["complexity"])
            for _ in range(num_points):
                self.voronoi_points.append(
                    {
                        "pos": (
                            random.random() * self.width,
                            random.random() * self.height,
                        ),
                        "vel": (random.random() * 2 - 1, random.random() * 2 - 1),
                    }
                )

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        # Update point positions
        for point in self.voronoi_points:
            x, y = point["pos"]
            dx, dy = point["vel"]
            new_x = (x + dx * params["speed"]) % self.width
            new_y = (y + dy * params["speed"]) % self.height
            point["pos"] = (new_x, new_y)

        # Draw Voronoi regions
        pixels = []
        for y in range(0, self.height, block_size):
            for x in range(0, self.width, block_size):
                min_dist = float("inf")
                closest_point = None

                for point in self.voronoi_points:
                    px, py = point["pos"]
                    dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        closest_point = point

                if closest_point:
                    px, py = closest_point["pos"]
                    color = self._get_color(
                        px / self.width, py / self.height, t, params["color_mode"]
                    )
                    points = self._apply_symmetry(x, y, symmetry)
                    for sx, sy in points:
                        pixels.extend(
                            self._draw_block(sx, sy, color, block_size, blend)
                        )

        return pixels

    def _generate_maze(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate maze pattern with enhanced features."""
        if self.maze_buffer is None:
            size = max(self.width, self.height) // 2
            self.maze_buffer = np.zeros((size, size), dtype=int)
            stack = [(0, 0)]
            visited = {(0, 0)}

            while stack:
                x, y = stack[-1]
                neighbors = []
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx * 2, y + dy * 2
                    if 0 <= nx < size and 0 <= ny < size and (nx, ny) not in visited:
                        neighbors.append((nx, ny, dx, dy))

                if neighbors:
                    nx, ny, dx, dy = random.choice(neighbors)
                    self.maze_buffer[y + dy, x + dx] = 1
                    self.maze_buffer[ny, nx] = 1
                    stack.append((nx, ny))
                    visited.add((nx, ny))
                else:
                    stack.pop()

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        # Draw maze with animation
        size = self.maze_buffer.shape[0]
        scale_x = self.width / (size * 2)
        scale_y = self.height / (size * 2)

        pixels = []
        for y in range(size):
            for x in range(size):
                if self.maze_buffer[y, x]:
                    px = int(x * scale_x * 2)
                    py = int(y * scale_y * 2)
                    phase = (x + y) / (size * 2) + t
                    color = self._get_color(phase, 0.5, t, params["color_mode"])
                    points = self._apply_symmetry(px, py, symmetry)
                    for sx, sy in points:
                        pixels.extend(
                            self._draw_block(sx, sy, color, block_size, blend)
                        )

        return pixels

    def _generate_fractal(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate fractal pattern with enhanced features."""
        if self.fractal_buffer is None:
            size = max(self.width, self.height)
            self.fractal_buffer = np.zeros((size, size), dtype=float)
            self._generate_mandelbrot(self.fractal_buffer)

        t = self.step * params["speed"] * 0.1
        block_size = params["block_size"]
        symmetry = params["symmetry"]
        blend = params["blend"]

        # Draw fractal with animation
        zoom = 1.0 + math.sin(t * 0.5) * 0.2
        center_x = self.width / 2 + math.cos(t) * self.width * 0.1
        center_y = self.height / 2 + math.sin(t) * self.height * 0.1

        pixels = []
        for y in range(0, self.height, block_size):
            for x in range(0, self.width, block_size):
                fx = (x - center_x) * zoom + self.width / 2
                fy = (y - center_y) * zoom + self.height / 2

                if 0 <= fx < self.width and 0 <= fy < self.height:
                    value = self.fractal_buffer[int(fy), int(fx)]
                    phase = value + t
                    color = self._get_color(phase, value, t, params["color_mode"])
                    points = self._apply_symmetry(x, y, symmetry)
                    for sx, sy in points:
                        pixels.extend(
                            self._draw_block(sx, sy, color, block_size, blend)
                        )

        return pixels

    def _generate_mandelbrot(self, buffer: np.ndarray) -> None:
        """Generate Mandelbrot set."""
        size = buffer.shape[0]
        max_iter = 100

        for y in range(size):
            for x in range(size):
                zx = 0
                zy = 0
                cx = (x - size / 2) * 4.0 / size
                cy = (y - size / 2) * 4.0 / size

                for i in range(max_iter):
                    zx_new = zx * zx - zy * zy + cx
                    zy = 2 * zx * zy + cy
                    zx = zx_new

                    if zx * zx + zy * zy > 4:
                        buffer[y, x] = i / max_iter
                        break
