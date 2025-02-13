from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class RainbowWave(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="rainbow_wave",
            description="A flowing rainbow pattern across the grid",
            parameters=[
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=10.0,
                    description="Speed of the wave movement",
                ),
                Parameter(
                    name="saturation",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Color saturation",
                ),
                Parameter(
                    name="direction",
                    type=str,
                    default="diagonal",
                    description="Wave direction (diagonal, horizontal, or vertical)",
                ),
            ],
            category="animations",
            tags=["rainbow", "wave", "colorful"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0

    def wheel(self, pos: int, saturation: float = 1.0) -> tuple[int, int, int]:
        """Generate rainbow colors across 0-255 positions."""
        pos = pos % 255
        if pos < 85:
            return (int(pos * 3 * saturation), int((255 - pos * 3) * saturation), 0)
        elif pos < 170:
            pos -= 85
            return (int((255 - pos * 3) * saturation), 0, int(pos * 3 * saturation))
        else:
            pos -= 170
            return (0, int(pos * 3 * saturation), int((255 - pos * 3) * saturation))

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        # Validate and get parameters
        params = self.validate_params(params)
        speed = params["speed"]
        saturation = params["saturation"]
        direction = params["direction"]

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Calculate hue based on direction
                if direction == "horizontal":
                    hue = (x + self._step) % 255
                elif direction == "vertical":
                    hue = (y + self._step) % 255
                else:  # diagonal
                    hue = (x + y + self._step) % 255

                # Get color and create pixel
                r, g, b = self.wheel(hue, saturation)
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": r,
                        "g": g,
                        "b": b,
                    }
                )

        # Update step for next frame
        self._step = (self._step + speed) % 255

        return pixels
