import random
import numpy as np
from typing import Dict, Any, List
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Fire(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="fire",
            description="Realistic fire effect",
            parameters=[
                Parameter(
                    name="cooling",
                    type=float,
                    default=0.7,
                    min_value=0.1,
                    max_value=2.0,
                    description="Fire cooling rate",
                ),
                Parameter(
                    name="sparking",
                    type=float,
                    default=0.95,
                    min_value=0.5,
                    max_value=1.0,
                    description="Spark generation probability",
                ),
                Parameter(
                    name="wind",
                    type=float,
                    default=0.0,
                    min_value=-1.0,
                    max_value=1.0,
                    description="Wind effect (-1 left, 1 right)",
                ),
            ],
            category="animations",
            tags=["fire", "particles", "natural"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        # Create heat map with extra bottom row for spark generation
        self.heat = np.zeros((self.height + 1, self.width), dtype=float)

    def get_fire_color(self, temperature: float) -> tuple[int, int, int]:
        """Convert temperature (0-1) to fire color."""
        # Black to red to yellow to white
        if temperature < 0.2:
            return (0, 0, 0)
        elif temperature < 0.4:
            t = (temperature - 0.2) * 5
            return (int(255 * t), 0, 0)
        elif temperature < 0.6:
            t = (temperature - 0.4) * 5
            return (255, int(255 * t), 0)
        else:
            t = (temperature - 0.6) * 2.5
            return (255, 255, int(255 * t))

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        cooling = params["cooling"]
        sparking = params["sparking"]
        wind = params["wind"]

        # Cool down every cell a little
        self.heat = self.heat * (1 - cooling * 0.02)

        # Generate sparks at the bottom
        for x in range(self.width):
            if random.random() < sparking:
                self.heat[-1, x] = random.uniform(0.9, 1.0)

        # Move heat upwards and apply wind
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                # Calculate wind offset
                wind_offset = int(wind * 2 * (1 - y / self.height))
                src_x = (x - wind_offset) % self.width

                # Average heat from cells below
                total = 0
                count = 0
                for dy in range(3):  # Look at 3 cells below
                    for dx in [-1, 0, 1]:  # And adjacent cells
                        ny = y + dy
                        nx = (src_x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            total += self.heat[ny, nx]
                            count += 1

                if count > 0:
                    new_heat[y, x] = total / count

        self.heat = new_heat

        # Generate pixels
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.get_fire_color(self.heat[y, x])
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        return pixels
