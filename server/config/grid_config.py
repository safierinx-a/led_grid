from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class GridDirection(Enum):
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"


class RowDirection(Enum):
    BOTTOM_TO_TOP = "bottom_to_top"
    TOP_TO_BOTTOM = "top_to_bottom"


@dataclass
class GridConfig:
    width: int = 25
    height: int = 24
    start_corner: Tuple[int, int] = (24, 0)  # (row, col) - bottom right
    first_row_direction: GridDirection = GridDirection.RIGHT_TO_LEFT
    row_progression: RowDirection = RowDirection.BOTTOM_TO_TOP
    serpentine: bool = True

    def xy_to_index(self, x: int, y: int) -> int:
        """Convert x,y coordinates to LED strip index based on configuration"""
        # Normalize y coordinate based on row progression
        if self.row_progression == RowDirection.BOTTOM_TO_TOP:
            y = self.height - 1 - y

        # Handle serpentine pattern
        if self.serpentine and y % 2 == 1:
            # Odd rows run opposite to first_row_direction
            x = self.width - 1 - x

        # Handle base direction
        elif self.first_row_direction == GridDirection.RIGHT_TO_LEFT:
            x = self.width - 1 - x

        return y * self.width + x

    def index_to_xy(self, index: int) -> Tuple[int, int]:
        """Convert LED strip index to x,y coordinates based on configuration"""
        y = index // self.width
        x = index % self.width

        # Normalize y coordinate based on row progression
        if self.row_progression == RowDirection.BOTTOM_TO_TOP:
            y = self.height - 1 - y

        # Handle serpentine pattern
        if self.serpentine and y % 2 == 1:
            # Odd rows run opposite to first_row_direction
            x = self.width - 1 - x

        # Handle base direction
        elif self.first_row_direction == GridDirection.RIGHT_TO_LEFT:
            x = self.width - 1 - x

        return (x, y)


# Default configuration for our setup
DEFAULT_CONFIG = GridConfig()
