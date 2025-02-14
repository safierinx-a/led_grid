import random
import numpy as np
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry
import math


@PatternRegistry.register
class GameOfLife(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="game_of_life",
            description="Enhanced Game of Life with bold visuals optimized for 24x25 LED grid",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="classic",
                    description="Rule variation (classic, bloom, maze, coral, chaos)",
                ),
                Parameter(
                    name="density",
                    type=float,
                    default=0.3,
                    min_value=0.1,
                    max_value=0.9,
                    description="Initial cell density",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="energy",
                    description="Color mode (energy, heat, neon, crystal, flow)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Generation update speed",
                ),
                Parameter(
                    name="size",
                    type=int,
                    default=1,
                    min_value=1,
                    max_value=2,
                    description="Cell size (1-2 pixels)",
                ),
            ],
            category="cellular",
            tags=["game of life", "cellular automata", "simulation"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.grid = None
        self.energy = None  # Cell energy levels
        self.colors = None  # RGB colors for each cell
        self.ages = None  # Cell ages for patterns
        self._step = 0
        self._update_counter = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2

    def _init_grid(self, density: float, variation: str):
        """Initialize grid with pattern based on variation"""
        self.grid = np.zeros((self.height, self.width), dtype=int)
        self.energy = np.zeros((self.height, self.width), dtype=float)
        self.colors = np.zeros((self.height, self.width, 3), dtype=int)
        self.ages = np.zeros((self.height, self.width), dtype=int)

        if variation == "bloom":
            # Create circular pattern
            for y in range(self.height):
                for x in range(self.width):
                    dx = x - self._center_x
                    dy = y - self._center_y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < min(self.width, self.height) / 4:
                        if random.random() < density * 1.5:
                            self.grid[y, x] = 1
                            self.energy[y, x] = 1.0

        elif variation == "maze":
            # Create maze-like initial pattern
            for y in range(0, self.height, 2):
                for x in range(0, self.width, 2):
                    if random.random() < density * 1.2:
                        self.grid[y, x] = 1
                        if y + 1 < self.height and random.random() < 0.7:
                            self.grid[y + 1, x] = 1
                        if x + 1 < self.width and random.random() < 0.7:
                            self.grid[y, x + 1] = 1
                        self.energy[y, x] = 1.0

        elif variation == "coral":
            # Start from edges
            for y in range(self.height):
                for x in range(self.width):
                    if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                        if random.random() < density * 2:
                            self.grid[y, x] = 1
                            self.energy[y, x] = 1.0

        elif variation == "chaos":
            # Create high-energy random pattern
            self.grid = np.random.choice(
                [0, 1],
                size=(self.height, self.width),
                p=[1 - density * 1.5, density * 1.5],
            )
            self.energy = np.random.uniform(0.5, 1.0, size=(self.height, self.width))
            self.energy *= self.grid

        else:  # classic
            # Random distribution
            self.grid = np.random.choice(
                [0, 1], size=(self.height, self.width), p=[1 - density, density]
            )
            self.energy = self.grid.astype(float)

    def _count_neighbors(self, y: int, x: int) -> tuple[int, float]:
        """Count live neighbors and their average energy"""
        count = 0
        total_energy = 0.0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                ny = (y + dy) % self.height
                nx = (x + dx) % self.width
                if self.grid[ny, nx]:
                    count += 1
                    total_energy += self.energy[ny, nx]
        return count, (total_energy / count if count > 0 else 0)

    def _apply_rules(
        self, y: int, x: int, neighbors: int, avg_energy: float, variation: str
    ) -> tuple[int, float]:
        """Apply rules based on variation"""
        current = self.grid[y, x]
        current_energy = self.energy[y, x]

        if variation == "bloom":
            # Favor growth patterns
            if current and neighbors in [2, 3, 4]:
                return 1, min(1.0, current_energy * 1.1)
            elif not current and neighbors in [3, 4]:
                return 1, avg_energy * 0.9
            return 0, 0.0

        elif variation == "maze":
            # Rules that tend to create maze-like patterns
            if current and neighbors in [1, 2, 3, 4]:
                return 1, min(1.0, current_energy * 1.05)
            elif not current and neighbors == 3:
                return 1, avg_energy * 0.95
            return 0, 0.0

        elif variation == "coral":
            # Rules for coral-like growth
            if current and neighbors in [2, 3, 4, 5]:
                return 1, min(1.0, current_energy * 1.02)
            elif not current and neighbors in [3]:
                return 1, avg_energy * 0.98
            return 0, 0.0

        elif variation == "chaos":
            # More dynamic rules
            if current and neighbors in [2, 3]:
                return 1, min(1.0, current_energy * 1.15)
            elif not current and neighbors in [2, 3, 4]:
                return 1, avg_energy * 0.85
            return 0, 0.0

        else:  # classic
            # Standard Game of Life rules
            if current and neighbors in [2, 3]:
                return 1, min(1.0, current_energy * 1.05)
            elif not current and neighbors == 3:
                return 1, avg_energy * 0.95
            return 0, 0.0

    def _get_cell_color(
        self, y: int, x: int, color_mode: str, cell_size: int
    ) -> tuple[int, int, int]:
        """Get enhanced cell color based on mode and energy"""
        if not self.grid[y, x]:
            return (0, 0, 0)

        energy = self.energy[y, x]
        age = self.ages[y, x]

        if color_mode == "energy":
            # Dynamic energy-based colors
            if energy > 0.8:
                # High energy: white to yellow
                v = (energy - 0.8) * 5  # Scale 0.8-1.0 to 0-1
                return (255, 255, int(255 * (1 - v)))
            else:
                # Lower energy: blue to white
                v = energy * 1.25  # Scale 0-0.8 to 0-1
                return (int(v * 255), int(v * 255), 255)

        elif color_mode == "heat":
            # Temperature-like colors
            if energy > 0.5:
                # Hot: red to yellow
                v = (energy - 0.5) * 2
                return (255, int(255 * v), 0)
            else:
                # Cool: blue to red
                v = energy * 2
                return (int(255 * v), 0, int(255 * (1 - v)))

        elif color_mode == "neon":
            # Bright neon colors
            hue = (energy + self._step * 0.01) % 1.0
            return self._hsv_to_rgb(hue, 1.0, energy * 0.5 + 0.5)

        elif color_mode == "crystal":
            # Crystalline effect
            base_hue = (x + y) / (self.width + self.height)
            hue = (base_hue + energy * 0.2) % 1.0
            return self._hsv_to_rgb(hue, energy, 1.0)

        else:  # flow
            # Flowing colors based on position and time
            dx = x - self._center_x
            dy = y - self._center_y
            angle = (math.atan2(dy, dx) / (2 * math.pi) + 0.5 + self._step * 0.01) % 1.0
            return self._hsv_to_rgb(angle, energy, 1.0)

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

    def _draw_cell(
        self, x: int, y: int, size: int, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a cell with given size"""
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

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        variation = params["variation"]
        density = params["density"]
        color_mode = params["color_mode"]
        speed = params["speed"]
        cell_size = params["size"]

        # Initialize if needed
        if self.grid is None:
            self._init_grid(density, variation)

        # Update counter
        self._update_counter += speed * 0.1

        # Update grid state when counter reaches 1
        if self._update_counter >= 1:
            self._update_counter = 0
            self._step += 1

            # Calculate next generation
            new_grid = np.zeros_like(self.grid)
            new_energy = np.zeros_like(self.energy)
            new_ages = np.copy(self.ages)

            for y in range(0, self.height, cell_size):
                for x in range(0, self.width, cell_size):
                    neighbors, avg_energy = self._count_neighbors(y, x)
                    state, energy = self._apply_rules(
                        y, x, neighbors, avg_energy, variation
                    )

                    # Apply state to all pixels in the cell
                    for dy in range(cell_size):
                        for dx in range(cell_size):
                            py, px = y + dy, x + dx
                            if px < self.width and py < self.height:
                                new_grid[py, px] = state
                                new_energy[py, px] = energy
                                if state:
                                    new_ages[py, px] += 1
                    else:
                        new_ages[py, px] = 0

            self.grid = new_grid
            self.energy = new_energy
            self.ages = new_ages

        # Generate frame
        pixels = []
        for y in range(0, self.height, cell_size):
            for x in range(0, self.width, cell_size):
                if self.grid[y, x]:
                    color = self._get_cell_color(y, x, color_mode, cell_size)
                    pixels.extend(self._draw_cell(x, y, cell_size, color))

        return pixels
