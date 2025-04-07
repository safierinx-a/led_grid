"""
Simple test pattern to verify the pattern system is working correctly.
"""

from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry
from server.config.grid_config import GridConfig


@PatternRegistry.register
class TestPattern(Pattern):
    """A simple test pattern that displays a solid color."""

    def __init__(self, grid_config: GridConfig):
        super().__init__(grid_config)
        self.id = "test_pattern"  # Add id attribute

    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="test_pattern",
            description="A simple test pattern that displays a solid color",
            parameters=[
                Parameter(
                    name="red",
                    type=int,
                    default=255,
                    min_value=0,
                    max_value=255,
                    description="Red component (0-255)",
                ),
                Parameter(
                    name="green",
                    type=int,
                    default=0,
                    min_value=0,
                    max_value=255,
                    description="Green component (0-255)",
                ),
                Parameter(
                    name="blue",
                    type=int,
                    default=0,
                    min_value=0,
                    max_value=255,
                    description="Blue component (0-255)",
                ),
            ],
            category="test",
            tags=["test", "debug"],
        )

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a solid color frame."""
        # Get default values from pattern definition
        default_params = {
            param.name: param.default for param in self.definition().parameters
        }

        # Merge provided params with defaults
        merged_params = default_params.copy()
        if params:
            merged_params.update(params)

        # Get color components with defaults
        r = merged_params.get("red", 255)
        g = merged_params.get("green", 0)
        b = merged_params.get("blue", 0)

        # Create pixels
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                index = self.grid_config.xy_to_index(x, y)
                pixels.append({"index": index, "r": r, "g": g, "b": b})

        return pixels
