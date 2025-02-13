import math
import time
from typing import Dict, Any, List
from server.modifiers.base import (
    Modifier,
    ModifierDefinition,
    ModifierRegistry,
    Parameter,
)


@ModifierRegistry.register
class BrightnessModifier(Modifier):
    """Adjusts the brightness of any pattern"""

    @classmethod
    def definition(cls) -> ModifierDefinition:
        return ModifierDefinition(
            name="brightness",
            description="Adjust the brightness of the pattern",
            parameters=[
                Parameter(
                    name="level",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Brightness level",
                )
            ],
            category="color",
            tags=["brightness", "dimming"],
        )

    def apply(
        self, pixels: List[Dict[str, int]], params: Dict[str, Any]
    ) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        level = params["level"]

        return [
            {
                "index": p["index"],
                "r": int(p["r"] * level),
                "g": int(p["g"] * level),
                "b": int(p["b"] * level),
            }
            for p in pixels
        ]


@ModifierRegistry.register
class StrobeModifier(Modifier):
    """Adds strobing effect to any pattern"""

    @classmethod
    def definition(cls) -> ModifierDefinition:
        return ModifierDefinition(
            name="strobe",
            description="Add strobing effect",
            parameters=[
                Parameter(
                    name="frequency",
                    type=float,
                    default=2.0,
                    min_value=0.1,
                    max_value=20.0,
                    description="Strobe frequency in Hz",
                ),
                Parameter(
                    name="duty_cycle",
                    type=float,
                    default=0.5,
                    min_value=0.1,
                    max_value=0.9,
                    description="Duty cycle (on-time ratio)",
                ),
            ],
            category="timing",
            tags=["strobe", "flash", "timing"],
        )

    def apply(
        self, pixels: List[Dict[str, int]], params: Dict[str, Any]
    ) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        frequency = params["frequency"]
        duty_cycle = params["duty_cycle"]

        # Calculate strobe state based on time
        period = 1.0 / frequency
        phase = (time.time() % period) / period
        is_on = phase < duty_cycle

        if not is_on:
            return [{"index": p["index"], "r": 0, "g": 0, "b": 0} for p in pixels]
        return pixels


@ModifierRegistry.register
class MirrorModifier(Modifier):
    """Mirrors the pattern across various axes"""

    @classmethod
    def definition(cls) -> ModifierDefinition:
        return ModifierDefinition(
            name="mirror",
            description="Mirror the pattern",
            parameters=[
                Parameter(
                    name="axis",
                    type=str,
                    default="horizontal",
                    description="Mirror axis (horizontal, vertical, or both)",
                )
            ],
            category="spatial",
            tags=["mirror", "symmetry", "spatial"],
        )

    def apply(
        self, pixels: List[Dict[str, int]], params: Dict[str, Any]
    ) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        axis = params["axis"]

        # Convert pixels to 2D grid for easier manipulation
        grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        for p in pixels:
            x, y = self.grid_config.index_to_xy(p["index"])
            grid[y][x] = (p["r"], p["g"], p["b"])

        result = []
        for y in range(self.height):
            for x in range(self.width):
                if axis in ["horizontal", "both"]:
                    mirror_x = self.width - 1 - x
                    if grid[y][mirror_x] is not None:
                        grid[y][x] = grid[y][mirror_x]

                if axis in ["vertical", "both"]:
                    mirror_y = self.height - 1 - y
                    if grid[mirror_y][x] is not None:
                        grid[y][x] = grid[mirror_y][x]

                if grid[y][x] is not None:
                    result.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": grid[y][x][0],
                            "g": grid[y][x][1],
                            "b": grid[y][x][2],
                        }
                    )

        return result


@ModifierRegistry.register
class TileModifier(Modifier):
    """Tiles the pattern multiple times"""

    @classmethod
    def definition(cls) -> ModifierDefinition:
        return ModifierDefinition(
            name="tile",
            description="Tile the pattern",
            parameters=[
                Parameter(
                    name="x_tiles",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=5,
                    description="Number of horizontal tiles",
                ),
                Parameter(
                    name="y_tiles",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=5,
                    description="Number of vertical tiles",
                ),
            ],
            category="spatial",
            tags=["tile", "repeat", "spatial"],
        )

    def apply(
        self, pixels: List[Dict[str, int]], params: Dict[str, Any]
    ) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        x_tiles = params["x_tiles"]
        y_tiles = params["y_tiles"]

        # Convert pixels to 2D grid
        base_grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        for p in pixels:
            x, y = self.grid_config.index_to_xy(p["index"])
            base_grid[y][x] = (p["r"], p["g"], p["b"])

        # Calculate tile sizes
        tile_width = self.width // x_tiles
        tile_height = self.height // y_tiles

        result = []
        for y in range(self.height):
            for x in range(self.width):
                # Map to base tile coordinates
                base_x = x % tile_width
                base_y = y % tile_height

                if base_grid[base_y][base_x] is not None:
                    result.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": base_grid[base_y][base_x][0],
                            "g": base_grid[base_y][base_x][1],
                            "b": base_grid[base_y][base_x][2],
                        }
                    )

        return result
