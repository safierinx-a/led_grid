import random
from typing import Dict, Any, List, Tuple
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class MatrixRain(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="matrix_rain",
            description="Matrix-style digital rain effect",
            parameters=[
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Speed of falling drops",
                ),
                Parameter(
                    name="density",
                    type=float,
                    default=0.1,
                    min_value=0.01,
                    max_value=0.5,
                    description="Density of drops",
                ),
                Parameter(
                    name="tail_length",
                    type=float,
                    default=0.8,
                    min_value=0.1,
                    max_value=0.99,
                    description="Length of drop tails (decay rate)",
                ),
            ],
            category="animations",
            tags=["matrix", "rain", "digital"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        # List of active drops: (x, y, intensity)
        self.drops: List[Tuple[int, float, float]] = []

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        speed = params["speed"]
        density = params["density"]
        tail_length = params["tail_length"]

        # Update existing drops
        new_drops = []
        for x, y, intensity in self.drops:
            if y < self.height:
                new_drops.append((x, y + speed, intensity * tail_length))

        # Add new drops
        if random.random() < density:
            x = random.randint(0, self.width - 1)
            new_drops.append((x, 0.0, 1.0))

        self.drops = new_drops

        # Generate frame
        pixels = []
        for x, y, intensity in self.drops:
            if 0 <= int(y) < self.height:  # Only show drops within grid
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, int(y)),
                        "r": 0,
                        "g": int(intensity * 255),
                        "b": 0,
                    }
                )

        return pixels
