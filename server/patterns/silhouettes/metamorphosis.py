import math
import random
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Metamorphosis(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="metamorphosis",
            description="Silhouette shapes that transform between different forms with smooth transitions",
            parameters=[
                Parameter(
                    name="form_sequence",
                    type=str,
                    default="random",
                    description="Sequence of forms to morph between (bird_fish, cat_human, tree_animal, random, custom)",
                ),
                Parameter(
                    name="transition_speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Speed of transition between forms",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="silhouette",
                    description="Color mode (silhouette, gradient, aura, rainbow)",
                ),
                Parameter(
                    name="size",
                    type=float,
                    default=0.8,
                    min_value=0.3,
                    max_value=1.0,
                    description="Size of silhouette (0.3-1.0)",
                ),
                Parameter(
                    name="position_x",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Horizontal position (0.0-1.0)",
                ),
                Parameter(
                    name="position_y",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Vertical position (0.0-1.0)",
                ),
            ],
            category="silhouettes",
            tags=["silhouette", "transformation", "animation"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
        self._transition_progress = 0.0
        self._current_form_index = 0

        # Create silhouette matrices for different forms
        self._silhouettes = {
            "bird": self._create_bird_silhouette(),
            "fish": self._create_fish_silhouette(),
            "cat": self._create_cat_silhouette(),
            "human": self._create_human_silhouette(),
            "tree": self._create_tree_silhouette(),
            "person": self._create_person_silhouette(),
            "animal": self._create_animal_silhouette(),
        }

        # Define form sequences
        self._form_sequences = {
            "bird_fish": ["bird", "fish"],
            "cat_human": ["cat", "human"],
            "tree_animal": ["tree", "animal"],
            "random": list(self._silhouettes.keys()),
            "custom": ["bird", "cat", "fish", "human", "tree"],
        }

        self._active_sequence = []
        self._current_form = ""
        self._next_form = ""

    def _create_bird_silhouette(self) -> np.ndarray:
        """Create a simple bird silhouette matrix"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Body
        for y in range(4, 8):
            for x in range(4, 12):
                matrix[y, x] = 1

        # Wings
        for y in range(2, 6):
            for x in range(2, 14):
                if abs(y - 4) + abs(x - 8) < 7:
                    matrix[y, x] = 1

        # Head and beak
        for y in range(3, 7):
            for x in range(12, 15):
                if abs(y - 5) + abs(x - 13) < 3:
                    matrix[y, x] = 1

        # Tail
        for y in range(3, 9):
            for x in range(1, 4):
                if abs(y - 6) + abs(x - 2) < 3:
                    matrix[y, x] = 1

        return matrix

    def _create_fish_silhouette(self) -> np.ndarray:
        """Create a simple fish silhouette matrix"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Body
        for y in range(3, 9):
            for x in range(4, 13):
                if (y - 6) ** 2 + (x - 8) ** 2 / 2 < 10:
                    matrix[y, x] = 1

        # Tail
        for y in range(2, 10):
            for x in range(1, 5):
                if abs(y - 6) < (x + 1) / 1.5:
                    matrix[y, x] = 1

        # Fins
        for y in range(1, 4):
            for x in range(7, 11):
                if abs(y - 3) + abs(x - 9) < 3:
                    matrix[y, x] = 1

        for y in range(8, 11):
            for x in range(7, 11):
                if abs(y - 9) + abs(x - 9) < 3:
                    matrix[y, x] = 1

        return matrix

    def _create_cat_silhouette(self) -> np.ndarray:
        """Create a simple cat silhouette matrix"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Body
        for y in range(5, 10):
            for x in range(4, 12):
                matrix[y, x] = 1

        # Head
        for y in range(2, 7):
            for x in range(10, 15):
                if (y - 4.5) ** 2 + (x - 12.5) ** 2 < 7:
                    matrix[y, x] = 1

        # Ears
        for y in range(0, 3):
            for x in range(10, 15):
                if abs(y - 2) + abs(x - 11) < 3 or abs(y - 2) + abs(x - 14) < 3:
                    matrix[y, x] = 1

        # Tail
        for y in range(3, 6):
            for x in range(0, 6):
                if abs(y - 5) + abs(x - 3) / 1.5 < 4:
                    matrix[y, x] = 1

        return matrix

    def _create_human_silhouette(self) -> np.ndarray:
        """Create a simple human silhouette matrix"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Head
        for y in range(0, 4):
            for x in range(7, 11):
                if (y - 2) ** 2 + (x - 9) ** 2 < 5:
                    matrix[y, x] = 1

        # Body
        for y in range(4, 10):
            for x in range(7, 11):
                matrix[y, x] = 1

        # Arms
        for y in range(4, 7):
            for x in range(3, 15):
                if y > 4 and y < 7 and (x < 7 or x > 10):
                    matrix[y, x] = 1

        # Legs
        for y in range(10, 12):
            for x in range(6, 8):
                matrix[y, x] = 1

        for y in range(10, 12):
            for x in range(10, 12):
                matrix[y, x] = 1

        return matrix

    def _create_tree_silhouette(self) -> np.ndarray:
        """Create a simple tree silhouette matrix"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Trunk
        for y in range(6, 12):
            for x in range(7, 10):
                matrix[y, x] = 1

        # Foliage
        for y in range(0, 7):
            for x in range(3, 14):
                if (y - 3) ** 2 + (x - 8) ** 2 < 23:
                    matrix[y, x] = 1

        return matrix

    def _create_person_silhouette(self) -> np.ndarray:
        """Create a simple person in motion silhouette"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Head
        for y in range(1, 4):
            for x in range(9, 12):
                if (y - 2.5) ** 2 + (x - 10.5) ** 2 < 2.5:
                    matrix[y, x] = 1

        # Body (leaning)
        for y in range(4, 9):
            for x in range(7, 10):
                if abs(y - 6.5) + abs(x - (8.5 - (y - 6) * 0.3)) < 3:
                    matrix[y, x] = 1

        # Arms (one up, one down)
        for y in range(4, 8):
            for x in range(6, 13):
                if (y < 6 and x > 9) or (y > 5 and x < 7):
                    if abs(y - (5.5 + (x - 9) * 0.3)) < 1.5:
                        matrix[y, x] = 1

        # Legs (one forward, one back)
        for y in range(8, 12):
            for x in range(4, 12):
                if (x < 8 and abs(y - (9 + (x - 6) * 0.5)) < 1) or (
                    x > 7 and abs(y - (10 - (x - 8) * 0.5)) < 1
                ):
                    matrix[y, x] = 1

        return matrix

    def _create_animal_silhouette(self) -> np.ndarray:
        """Create a simple quadruped animal silhouette"""
        height, width = 12, 16
        matrix = np.zeros((height, width))

        # Body
        for y in range(4, 8):
            for x in range(3, 11):
                matrix[y, x] = 1

        # Head
        for y in range(3, 8):
            for x in range(10, 15):
                if (y - 5.5) ** 2 + (x - 12.5) ** 2 < 6:
                    matrix[y, x] = 1

        # Legs
        for y in range(8, 12):
            for x in range(3, 5):
                matrix[y, x] = 1

        for y in range(8, 12):
            for x in range(9, 11):
                matrix[y, x] = 1

        # Tail
        for y in range(2, 5):
            for x in range(0, 4):
                if abs(y - 3.5) + abs(x - 2) < 3:
                    matrix[y, x] = 1

        return matrix

    def _interpolate_forms(
        self, form1: np.ndarray, form2: np.ndarray, progress: float
    ) -> np.ndarray:
        """Interpolate between two form matrices based on progress (0.0-1.0)"""
        return form1 * (1 - progress) + form2 * progress

    def _get_color(
        self, value: float, color_mode: str, x: int, y: int
    ) -> Tuple[int, int, int]:
        """Get color based on value and color mode"""
        if color_mode == "silhouette":
            return (0, 0, 0) if value == 0 else (255, 255, 255)
        elif color_mode == "gradient":
            if value == 0:
                return (0, 0, 0)
            h = (self._step * 0.01) % 1.0
            s = 1.0
            v = 0.8 + 0.2 * value
            return self._hsv_to_rgb(h, s, v)
        elif color_mode == "aura":
            if value == 0:
                return (0, 0, 0)
            h = (self._transition_progress * 0.5) % 1.0
            s = 0.8
            v = 0.7 + 0.3 * value
            return self._hsv_to_rgb(h, s, v)
        elif color_mode == "rainbow":
            if value == 0:
                return (0, 0, 0)
            h = (x / self.width + y / self.height + self._step * 0.01) % 1.0
            s = 0.9
            v = 0.7 + 0.3 * value
            return self._hsv_to_rgb(h, s, v)
        else:
            return (0, 0, 0) if value == 0 else (255, 255, 255)

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> Tuple[int, int, int]:
        """Convert HSV (0-1) to RGB (0-255)"""
        if s == 0:
            return (int(v * 255), int(v * 255), int(v * 255))

        i = int(h * 6)
        f = (h * 6) - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))

        i %= 6
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q

        return (int(r * 255), int(g * 255), int(b * 255))

    def _apply_form_to_grid(
        self, form: np.ndarray, size: float, pos_x: float, pos_y: float, color_mode: str
    ) -> List[Dict[str, int]]:
        """Apply a form to the grid with specified size and position"""
        form_height, form_width = form.shape

        # Calculate scaling and positioning
        scale = size
        center_x = int(pos_x * self.width)
        center_y = int(pos_y * self.height)

        start_x = center_x - int(form_width * scale / 2)
        start_y = center_y - int(form_height * scale / 2)

        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Calculate corresponding position in the form
                form_x = int((x - start_x) / scale)
                form_y = int((y - start_y) / scale)

                value = 0
                if 0 <= form_x < form_width and 0 <= form_y < form_height:
                    value = form[form_y, form_x]

                r, g, b = self._get_color(value, color_mode, x, y)

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
        """Generate a frame of the metamorphosis pattern"""
        # Validate parameters
        params = self.validate_params(params)
        form_sequence = params["form_sequence"]
        transition_speed = params["transition_speed"]
        color_mode = params["color_mode"]
        size = params["size"]
        pos_x = params["position_x"]
        pos_y = params["position_y"]

        # Initialize or update the sequence if needed
        if not self._active_sequence or form_sequence != self._current_sequence:
            self._current_sequence = form_sequence
            self._active_sequence = self._form_sequences.get(
                form_sequence, self._form_sequences["random"]
            )
            if form_sequence == "random":
                random.shuffle(self._active_sequence)
            self._current_form_index = 0
            self._current_form = self._active_sequence[0]
            self._next_form = self._active_sequence[
                (self._current_form_index + 1) % len(self._active_sequence)
            ]
            self._transition_progress = 0.0

        # Update transition progress
        self._transition_progress += 0.01 * transition_speed
        if self._transition_progress >= 1.0:
            self._transition_progress = 0.0
            self._current_form_index = (self._current_form_index + 1) % len(
                self._active_sequence
            )
            self._current_form = self._active_sequence[self._current_form_index]
            self._next_form = self._active_sequence[
                (self._current_form_index + 1) % len(self._active_sequence)
            ]

        # Get the current and next form silhouettes
        current_form_matrix = self._silhouettes[self._current_form]
        next_form_matrix = self._silhouettes[self._next_form]

        # Interpolate between forms
        interpolated_form = self._interpolate_forms(
            current_form_matrix, next_form_matrix, self._transition_progress
        )

        # Apply the interpolated form to the grid
        pixels = self._apply_form_to_grid(
            interpolated_form, size, pos_x, pos_y, color_mode
        )

        self._step += 1
        return pixels
