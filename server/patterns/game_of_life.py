import random
import numpy as np
from typing import Dict, Any, List
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class GameOfLife(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="game_of_life",
            description="Conway's Game of Life with colorful cells",
            parameters=[
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
                    default="age",
                    description="Color mode (age/inheritance/rainbow)",
                ),
                Parameter(
                    name="update_rate",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Generation update rate",
                ),
            ],
            category="cellular",
            tags=["game of life", "cellular automata", "simulation"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.grid = None
        self.colors = None  # RGB colors for each cell
        self.ages = None  # Cell ages for age-based coloring
        self._steps = 0
        self._update_counter = 0

    def init_grid(self, density: float):
        """Initialize random grid and colors"""
        self.grid = np.random.choice(
            [0, 1], size=(self.height, self.width), p=[1 - density, density]
        )
        self.colors = np.random.randint(0, 255, size=(self.height, self.width, 3))
        self.ages = np.zeros((self.height, self.width), dtype=int)

    def count_neighbors(self, y: int, x: int) -> int:
        """Count live neighbors of a cell"""
        total = 0
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                ny = (y + dy) % self.height
                nx = (x + dx) % self.width
                total += self.grid[ny, nx]
        return total

    def get_cell_color(self, y: int, x: int, color_mode: str) -> tuple[int, int, int]:
        """Get cell color based on mode"""
        if not self.grid[y, x]:
            return (0, 0, 0)

        if color_mode == "age":
            # Color based on cell age
            age = self.ages[y, x]
            hue = (age * 10) % 255
            return self.hsv_to_rgb(hue / 255, 1.0, 1.0)

        elif color_mode == "inheritance":
            # Use inherited color
            return tuple(self.colors[y, x])

        else:  # rainbow
            # Color based on position and time
            hue = (x + y + self._steps * 5) % 255
            return self.hsv_to_rgb(hue / 255, 1.0, 1.0)

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

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        density = params["density"]
        color_mode = params["color_mode"]
        update_rate = params["update_rate"]

        # Initialize if needed
        if self.grid is None:
            self.init_grid(density)

        # Update counter
        self._update_counter += update_rate * 0.05

        # Update grid state when counter reaches 1
        if self._update_counter >= 1:
            self._update_counter = 0
            self._steps += 1

            # Calculate next generation
            new_grid = np.zeros_like(self.grid)
            new_colors = np.copy(self.colors)
            new_ages = np.copy(self.ages)

            for y in range(self.height):
                for x in range(self.width):
                    neighbors = self.count_neighbors(y, x)
                    current = self.grid[y, x]

                    # Apply Game of Life rules
                    if current and neighbors in [2, 3]:
                        new_grid[y, x] = 1
                        new_ages[y, x] += 1
                    elif not current and neighbors == 3:
                        new_grid[y, x] = 1
                        # Inherit average color from neighbors
                        neighbor_colors = []
                        for dy in [-1, 0, 1]:
                            for dx in [-1, 0, 1]:
                                if dx == 0 and dy == 0:
                                    continue
                                ny = (y + dy) % self.height
                                nx = (x + dx) % self.width
                                if self.grid[ny, nx]:
                                    neighbor_colors.append(self.colors[ny, nx])
                        if neighbor_colors:
                            new_colors[y, x] = np.mean(neighbor_colors, axis=0)
                    else:
                        new_grid[y, x] = 0
                        new_ages[y, x] = 0

            self.grid = new_grid
            self.colors = new_colors
            self.ages = new_ages

        # Generate frame
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y, x]:
                    r, g, b = self.get_cell_color(y, x, color_mode)
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": r,
                            "g": g,
                            "b": b,
                        }
                    )

        return pixels
