import math
import random
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ShadowTheater(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="shadow_theater",
            description="Animated shadow theater with silhouettes telling stories against colorful backgrounds",
            parameters=[
                Parameter(
                    name="story",
                    type=str,
                    default="hero_journey",
                    description="Story to animate (hero_journey, nature_cycle, adventure, random)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=3.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="background_color",
                    type=str,
                    default="sunset",
                    description="Background color style (sunset, night, dawn, rainbow)",
                ),
                Parameter(
                    name="silhouette_mode",
                    type=str,
                    default="black",
                    description="Silhouette coloring (black, gradient_edge, semi_transparent)",
                ),
                Parameter(
                    name="size",
                    type=float,
                    default=0.7,
                    min_value=0.3,
                    max_value=1.0,
                    description="Size of silhouettes (0.3-1.0)",
                ),
            ],
            category="silhouettes",
            tags=["silhouette", "story", "animation", "theater"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
        self._scene_progress = 0.0
        self._current_scene_index = 0

        # Define silhouette forms for the shadow theater
        self._silhouettes = {
            "hero": self._create_hero_silhouette(),
            "monster": self._create_monster_silhouette(),
            "tree": self._create_tree_silhouette(),
            "mountain": self._create_mountain_silhouette(),
            "bird": self._create_bird_silhouette(),
            "sun": self._create_sun_silhouette(),
            "moon": self._create_moon_silhouette(),
            "cloud": self._create_cloud_silhouette(),
        }

        # Define story scenes with actors, positions, and transitions
        self._stories = {
            "hero_journey": self._create_hero_journey_scenes(),
            "nature_cycle": self._create_nature_cycle_scenes(),
            "adventure": self._create_adventure_scenes(),
            "random": self._create_random_scenes(),
        }

        self._active_story = []
        self._current_story = ""
        self._current_scene = {}
        self._next_scene = {}

    def _create_hero_silhouette(self) -> np.ndarray:
        """Create a hero silhouette with a cape"""
        height, width = 10, 8
        matrix = np.zeros((height, width))

        # Head
        for y in range(0, 2):
            for x in range(3, 5):
                matrix[y, x] = 1

        # Body
        for y in range(2, 6):
            for x in range(3, 5):
                matrix[y, x] = 1

        # Arms (one raised)
        for y in range(2, 4):
            for x in range(5, 7):
                matrix[y, x] = 1

        for y in range(3, 5):
            for x in range(1, 3):
                matrix[y, x] = 1

        # Legs
        for y in range(6, 10):
            for x in range(2, 4):
                matrix[y, x] = 1

        for y in range(6, 10):
            for x in range(4, 6):
                matrix[y, x] = 1

        # Cape
        for y in range(1, 7):
            for x in range(0, 2):
                if abs(y - 4) + abs(x - 1) < 4:
                    matrix[y, x] = 1

        return matrix

    def _create_monster_silhouette(self) -> np.ndarray:
        """Create a monster/creature silhouette"""
        height, width = 10, 8
        matrix = np.zeros((height, width))

        # Body
        for y in range(3, 8):
            for x in range(2, 6):
                matrix[y, x] = 1

        # Head with horns
        for y in range(0, 3):
            for x in range(3, 5):
                matrix[y, x] = 1

        # Horns
        for y in range(0, 2):
            for x in range(1, 3):
                if x == 1 and y < 1:
                    matrix[y, x] = 1
                if x == 2 and y < 2:
                    matrix[y, x] = 1

        for y in range(0, 2):
            for x in range(5, 7):
                if x == 6 and y < 1:
                    matrix[y, x] = 1
                if x == 5 and y < 2:
                    matrix[y, x] = 1

        # Arms/claws
        for y in range(4, 6):
            for x in range(0, 2):
                matrix[y, x] = 1

        for y in range(4, 6):
            for x in range(6, 8):
                matrix[y, x] = 1

        # Legs
        for y in range(8, 10):
            for x in range(1, 3):
                matrix[y, x] = 1

        for y in range(8, 10):
            for x in range(5, 7):
                matrix[y, x] = 1

        return matrix

    def _create_tree_silhouette(self) -> np.ndarray:
        """Create a tree silhouette"""
        height, width = 10, 8
        matrix = np.zeros((height, width))

        # Trunk
        for y in range(5, 10):
            for x in range(3, 5):
                matrix[y, x] = 1

        # Foliage (triangle shape)
        for y in range(0, 6):
            for x in range(0, 8):
                # Calculate distance from center-top
                if y < 6 and abs(x - 4) <= y:
                    matrix[y, x] = 1

        return matrix

    def _create_mountain_silhouette(self) -> np.ndarray:
        """Create a mountain silhouette"""
        height, width = 10, 12
        matrix = np.zeros((height, width))

        # Mountain shape (triangle)
        for y in range(0, height):
            for x in range(0, width):
                # Left mountain
                if y >= height - (height * (x / (width / 2))) and x < width / 2:
                    matrix[y, x] = 1
                # Right mountain
                if (
                    y >= height - (height * ((width - x) / (width / 2)))
                    and x >= width / 2
                ):
                    matrix[y, x] = 1

        # Snow cap
        for y in range(0, 3):
            for x in range(4, 8):
                if abs(x - 6) + y < 3:
                    matrix[y, x] = 1

        return matrix

    def _create_bird_silhouette(self) -> np.ndarray:
        """Create a bird silhouette (smaller than the metamorphosis one)"""
        height, width = 6, 8
        matrix = np.zeros((height, width))

        # Body
        for y in range(2, 4):
            for x in range(3, 6):
                matrix[y, x] = 1

        # Wings
        for y in range(1, 5):
            for x in range(1, 7):
                if (y == 1 or y == 4) and (x > 2 and x < 6):
                    matrix[y, x] = 1
                if (y == 2 or y == 3) and (x < 3 or x > 5):
                    matrix[y, x] = 1

        # Head
        for y in range(1, 3):
            for x in range(6, 8):
                if (y - 2) ** 2 + (x - 7) ** 2 < 2:
                    matrix[y, x] = 1

        # Tail
        for y in range(2, 4):
            for x in range(0, 2):
                if (y - 3) ** 2 + (x - 1) ** 2 < 2:
                    matrix[y, x] = 1

        return matrix

    def _create_sun_silhouette(self) -> np.ndarray:
        """Create a sun silhouette"""
        height, width = 10, 10
        matrix = np.zeros((height, width))

        # Center circle
        center_x, center_y = width // 2, height // 2
        radius = 3

        for y in range(height):
            for x in range(width):
                # Circle
                if (x - center_x) ** 2 + (y - center_y) ** 2 < radius**2:
                    matrix[y, x] = 1

                # Rays
                for ray in range(8):
                    angle = ray * math.pi / 4
                    ray_x = center_x + 4.5 * math.cos(angle)
                    ray_y = center_y + 4.5 * math.sin(angle)
                    # Check if point is on the ray line
                    if (
                        (
                            (x - center_x) * math.cos(angle)
                            + (y - center_y) * math.sin(angle)
                        )
                        > radius
                        and abs(
                            (x - center_x) * math.sin(angle)
                            - (y - center_y) * math.cos(angle)
                        )
                        < 0.5
                        and (x - center_x) ** 2 + (y - center_y) ** 2 < 25
                    ):
                        matrix[y, x] = 1

        return matrix

    def _create_moon_silhouette(self) -> np.ndarray:
        """Create a crescent moon silhouette"""
        height, width = 10, 10
        matrix = np.zeros((height, width))

        center_x, center_y = width // 2, height // 2
        outer_radius = 4
        inner_radius = 3
        offset_x = 2  # Offset for inner circle to create crescent

        for y in range(height):
            for x in range(width):
                # Outside circle
                dist_outer = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                # Inside circle (offset to create crescent)
                dist_inner = math.sqrt(
                    (x - (center_x + offset_x)) ** 2 + (y - center_y) ** 2
                )

                # Points inside outer circle but outside inner circle
                if dist_outer < outer_radius and dist_inner > inner_radius:
                    matrix[y, x] = 1

        return matrix

    def _create_cloud_silhouette(self) -> np.ndarray:
        """Create a cloud silhouette"""
        height, width = 6, 10
        matrix = np.zeros((height, width))

        # Multiple overlapping circles to create cloud shape
        circles = [
            (2, 2, 2),  # (x, y, radius)
            (5, 2, 2.5),
            (8, 2, 1.5),
            (3, 4, 1.5),
            (6, 4, 2),
        ]

        for y in range(height):
            for x in range(width):
                # Check if point is in any of the circles
                for circle_x, circle_y, radius in circles:
                    if (x - circle_x) ** 2 + (y - circle_y) ** 2 < radius**2:
                        matrix[y, x] = 1
                        break

        return matrix

    def _create_hero_journey_scenes(self) -> List[Dict[str, Any]]:
        """Create scenes for the hero journey story"""
        scenes = [
            {
                # Scene 1: Hero in peaceful setting
                "actors": [
                    {"form": "hero", "start_pos": (0.3, 0.5), "end_pos": (0.3, 0.5)},
                    {"form": "tree", "start_pos": (0.7, 0.5), "end_pos": (0.7, 0.5)},
                    {"form": "sun", "start_pos": (0.8, 0.2), "end_pos": (0.8, 0.2)},
                ],
                "background": "dawn",
                "duration": 1.0,
            },
            {
                # Scene 2: Monster appears
                "actors": [
                    {"form": "hero", "start_pos": (0.3, 0.5), "end_pos": (0.4, 0.5)},
                    {"form": "monster", "start_pos": (1.2, 0.5), "end_pos": (0.8, 0.5)},
                    {"form": "tree", "start_pos": (0.7, 0.5), "end_pos": (0.7, 0.5)},
                ],
                "background": "sunset",
                "duration": 1.5,
            },
            {
                # Scene 3: Battle
                "actors": [
                    {"form": "hero", "start_pos": (0.4, 0.5), "end_pos": (0.45, 0.5)},
                    {"form": "monster", "start_pos": (0.8, 0.5), "end_pos": (0.6, 0.5)},
                ],
                "background": "night",
                "duration": 2.0,
            },
            {
                # Scene 4: Victory
                "actors": [
                    {"form": "hero", "start_pos": (0.45, 0.5), "end_pos": (0.5, 0.5)},
                    {"form": "monster", "start_pos": (0.6, 0.5), "end_pos": (0.6, 0.8)},
                ],
                "background": "night",
                "duration": 1.0,
            },
            {
                # Scene 5: Return to peace
                "actors": [
                    {"form": "hero", "start_pos": (0.5, 0.5), "end_pos": (0.7, 0.5)},
                    {"form": "sun", "start_pos": (0.3, 0.2), "end_pos": (0.5, 0.2)},
                    {"form": "tree", "start_pos": (0.9, 0.5), "end_pos": (0.9, 0.5)},
                ],
                "background": "dawn",
                "duration": 1.5,
            },
        ]
        return scenes

    def _create_nature_cycle_scenes(self) -> List[Dict[str, Any]]:
        """Create scenes for the nature cycle story"""
        scenes = [
            {
                # Scene 1: Dawn with sun rising
                "actors": [
                    {"form": "sun", "start_pos": (0.2, 0.8), "end_pos": (0.5, 0.2)},
                    {"form": "tree", "start_pos": (0.7, 0.6), "end_pos": (0.7, 0.6)},
                    {
                        "form": "mountain",
                        "start_pos": (0.3, 0.7),
                        "end_pos": (0.3, 0.7),
                    },
                ],
                "background": "dawn",
                "duration": 1.5,
            },
            {
                # Scene 2: Day with birds
                "actors": [
                    {"form": "sun", "start_pos": (0.5, 0.2), "end_pos": (0.8, 0.2)},
                    {"form": "tree", "start_pos": (0.7, 0.6), "end_pos": (0.7, 0.6)},
                    {"form": "bird", "start_pos": (0.3, 0.3), "end_pos": (0.6, 0.4)},
                    {"form": "bird", "start_pos": (0.2, 0.4), "end_pos": (0.5, 0.3)},
                ],
                "background": "sunset",
                "duration": 1.5,
            },
            {
                # Scene 3: Sunset
                "actors": [
                    {"form": "sun", "start_pos": (0.8, 0.2), "end_pos": (0.9, 0.8)},
                    {"form": "tree", "start_pos": (0.7, 0.6), "end_pos": (0.7, 0.6)},
                    {
                        "form": "mountain",
                        "start_pos": (0.3, 0.7),
                        "end_pos": (0.3, 0.7),
                    },
                    {"form": "cloud", "start_pos": (0.4, 0.3), "end_pos": (0.6, 0.3)},
                ],
                "background": "sunset",
                "duration": 1.5,
            },
            {
                # Scene 4: Night with moon
                "actors": [
                    {"form": "moon", "start_pos": (0.3, 0.2), "end_pos": (0.6, 0.2)},
                    {"form": "tree", "start_pos": (0.7, 0.6), "end_pos": (0.7, 0.6)},
                    {
                        "form": "mountain",
                        "start_pos": (0.3, 0.7),
                        "end_pos": (0.3, 0.7),
                    },
                ],
                "background": "night",
                "duration": 1.5,
            },
            {
                # Scene 5: Return to dawn
                "actors": [
                    {"form": "sun", "start_pos": (0.2, 0.8), "end_pos": (0.4, 0.3)},
                    {"form": "moon", "start_pos": (0.6, 0.2), "end_pos": (0.9, 0.2)},
                    {"form": "tree", "start_pos": (0.7, 0.6), "end_pos": (0.7, 0.6)},
                    {
                        "form": "mountain",
                        "start_pos": (0.3, 0.7),
                        "end_pos": (0.3, 0.7),
                    },
                ],
                "background": "dawn",
                "duration": 1.5,
            },
        ]
        return scenes

    def _create_adventure_scenes(self) -> List[Dict[str, Any]]:
        """Create scenes for the adventure story"""
        scenes = [
            {
                # Scene 1: Start of journey
                "actors": [
                    {"form": "hero", "start_pos": (0.2, 0.5), "end_pos": (0.3, 0.5)},
                    {
                        "form": "mountain",
                        "start_pos": (0.7, 0.6),
                        "end_pos": (0.7, 0.6),
                    },
                    {"form": "sun", "start_pos": (0.8, 0.2), "end_pos": (0.8, 0.2)},
                ],
                "background": "dawn",
                "duration": 1.0,
            },
            {
                # Scene 2: Climbing mountain
                "actors": [
                    {"form": "hero", "start_pos": (0.4, 0.6), "end_pos": (0.5, 0.4)},
                    {
                        "form": "mountain",
                        "start_pos": (0.6, 0.6),
                        "end_pos": (0.6, 0.6),
                    },
                    {"form": "cloud", "start_pos": (0.7, 0.3), "end_pos": (0.8, 0.3)},
                ],
                "background": "sunset",
                "duration": 1.5,
            },
            {
                # Scene 3: Finding treasure
                "actors": [
                    {"form": "hero", "start_pos": (0.5, 0.4), "end_pos": (0.6, 0.5)},
                    {"form": "tree", "start_pos": (0.8, 0.5), "end_pos": (0.8, 0.5)},
                    {"form": "moon", "start_pos": (0.3, 0.2), "end_pos": (0.3, 0.2)},
                ],
                "background": "night",
                "duration": 1.5,
            },
            {
                # Scene 4: Monster appears
                "actors": [
                    {"form": "hero", "start_pos": (0.6, 0.5), "end_pos": (0.4, 0.5)},
                    {"form": "monster", "start_pos": (1.1, 0.5), "end_pos": (0.7, 0.5)},
                    {"form": "tree", "start_pos": (0.8, 0.5), "end_pos": (0.8, 0.5)},
                ],
                "background": "night",
                "duration": 1.5,
            },
            {
                # Scene 5: Return home victorious
                "actors": [
                    {"form": "hero", "start_pos": (0.4, 0.5), "end_pos": (0.2, 0.5)},
                    {"form": "bird", "start_pos": (0.6, 0.3), "end_pos": (0.7, 0.2)},
                    {"form": "sun", "start_pos": (0.8, 0.2), "end_pos": (0.8, 0.2)},
                ],
                "background": "dawn",
                "duration": 1.0,
            },
        ]
        return scenes

    def _create_random_scenes(self) -> List[Dict[str, Any]]:
        """Create a completely random sequence of scenes"""
        scenes = []
        forms = list(self._silhouettes.keys())
        backgrounds = ["dawn", "sunset", "night", "rainbow"]

        num_scenes = random.randint(4, 6)
        for i in range(num_scenes):
            # Random selection of forms and positions
            num_actors = random.randint(2, 4)
            actors = []

            for j in range(num_actors):
                form = random.choice(forms)
                start_x = random.uniform(0.2, 0.8)
                start_y = random.uniform(0.3, 0.7)
                end_x = min(1.0, max(0.0, start_x + random.uniform(-0.3, 0.3)))
                end_y = min(1.0, max(0.0, start_y + random.uniform(-0.2, 0.2)))

                actors.append(
                    {
                        "form": form,
                        "start_pos": (start_x, start_y),
                        "end_pos": (end_x, end_y),
                    }
                )

            scenes.append(
                {
                    "actors": actors,
                    "background": random.choice(backgrounds),
                    "duration": random.uniform(1.0, 2.0),
                }
            )

        return scenes

    def _interpolate_position(
        self,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float],
        progress: float,
    ) -> Tuple[float, float]:
        """Interpolate between two positions based on progress (0.0-1.0)"""
        return (
            start_pos[0] + (end_pos[0] - start_pos[0]) * progress,
            start_pos[1] + (end_pos[1] - start_pos[1]) * progress,
        )

    def _get_silhouette_color(
        self, value: float, mode: str, x: int, y: int, edge_dist: float = 0
    ) -> Tuple[int, int, int]:
        """Get silhouette color based on value and mode"""
        if value == 0:
            return (0, 0, 0)  # Transparent

        if mode == "black":
            return (0, 0, 0)  # Pure black silhouette
        elif mode == "gradient_edge":
            if edge_dist < 0.2:  # Close to edge
                h = (self._step * 0.01) % 1.0
                s = 0.9
                v = 0.5 + 0.5 * edge_dist / 0.2
                return self._hsv_to_rgb(h, s, v)
            else:
                return (0, 0, 0)
        elif mode == "semi_transparent":
            alpha = 0.7  # Transparency factor
            h = (x / self.width + y / self.height) % 1.0
            s = 0.7
            v = 0.3
            r, g, b = self._hsv_to_rgb(h, s, v)
            return (int(r * alpha), int(g * alpha), int(b * alpha))
        else:
            return (0, 0, 0)

    def _get_background_color(
        self, x: int, y: int, bg_type: str, progress: float
    ) -> Tuple[int, int, int]:
        """Get background color based on position and background type"""
        if bg_type == "sunset":
            # Gradient from orange/red at bottom to purple/dark blue at top
            normalized_y = 1.0 - y / self.height
            if normalized_y < 0.5:
                # Bottom half: orange/red
                t = normalized_y * 2
                r = int(255 * (1.0 - 0.3 * t))
                g = int(100 * (1.0 - t))
                b = int(50 * (1.0 - t))
            else:
                # Top half: purple to dark blue
                t = (normalized_y - 0.5) * 2
                r = int(255 * (0.7 - 0.7 * t))
                g = int(50 * (1.0 - t))
                b = int(100 + 100 * t)
            return (r, g, b)

        elif bg_type == "night":
            # Dark blue with stars
            is_star = random.random() < 0.003  # Sparse stars
            if is_star:
                brightness = random.randint(180, 255)
                return (brightness, brightness, brightness)
            else:
                # Dark blue gradient
                normalized_y = y / self.height
                r = int(0 + 30 * normalized_y)
                g = int(0 + 30 * normalized_y)
                b = int(50 + 30 * normalized_y)
                return (r, g, b)

        elif bg_type == "dawn":
            # Soft gradient from light blue at top to light yellow/orange at bottom
            normalized_y = 1.0 - y / self.height
            if normalized_y < 0.6:
                # Bottom: yellow/orange
                t = normalized_y / 0.6
                r = int(255 - 100 * t)
                g = int(200 - 50 * t)
                b = int(100 + 100 * t)
            else:
                # Top: light blue
                t = (normalized_y - 0.6) / 0.4
                r = int(155 - 55 * t)
                g = int(150 + 50 * t)
                b = int(200 + 55 * t)
            return (r, g, b)

        elif bg_type == "rainbow":
            # Rainbow gradient that shifts over time
            angle = math.atan2(y - self.height / 2, x - self.width / 2)
            normalized_angle = (angle + math.pi) / (2 * math.pi)
            hue = (normalized_angle + progress * 0.1) % 1.0
            return self._hsv_to_rgb(hue, 0.8, 0.7)

        else:
            # Default black background
            return (0, 0, 0)

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

    def _apply_actor_to_grid(
        self,
        form: np.ndarray,
        pos_x: float,
        pos_y: float,
        silhouette_mode: str,
        size: float,
    ) -> List[Dict[str, Tuple[int, int]]]:
        """Apply an actor form to the grid and return pixel positions (not colors)"""
        form_height, form_width = form.shape

        # Scale and position
        scale = size
        center_x = int(pos_x * self.width)
        center_y = int(pos_y * self.height)

        start_x = center_x - int(form_width * scale / 2)
        start_y = center_y - int(form_height * scale / 2)

        pixel_positions = []

        for y in range(form_height):
            for x in range(form_width):
                if form[y, x] > 0:
                    # Calculate grid position
                    grid_x = int(start_x + x * scale)
                    grid_y = int(start_y + y * scale)

                    # Ensure within grid bounds
                    if 0 <= grid_x < self.width and 0 <= grid_y < self.height:
                        # Calculate distance from edge for edge effects
                        edge_dist = 0.0
                        if (
                            x == 0
                            or x == form_width - 1
                            or y == 0
                            or y == form_height - 1
                        ):
                            edge_dist = 0.0
                        else:
                            # Check neighbors to determine edge proximity
                            neighbors = [
                                (x - 1, y),
                                (x + 1, y),
                                (x, y - 1),
                                (x, y + 1),
                                (x - 1, y - 1),
                                (x + 1, y - 1),
                                (x - 1, y + 1),
                                (x + 1, y + 1),
                            ]
                            empty_neighbors = sum(
                                1
                                for nx, ny in neighbors
                                if 0 <= nx < form_width
                                and 0 <= ny < form_height
                                and form[ny, nx] == 0
                            )
                            edge_dist = 1.0 - (empty_neighbors / 8.0)

                        pixel_positions.append(
                            {
                                "index": self.grid_config.xy_to_index(grid_x, grid_y),
                                "coords": (grid_x, grid_y),
                                "edge_dist": edge_dist,
                            }
                        )

        return pixel_positions

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the shadow theater pattern"""
        # Validate parameters
        params = self.validate_params(params)
        story = params["story"]
        speed = params["speed"]
        background_color = params["background_color"]
        silhouette_mode = params["silhouette_mode"]
        size = params["size"]

        # Initialize or update the story if needed
        if not self._active_story or story != self._current_story:
            self._current_story = story
            self._active_story = self._stories.get(story, self._stories["hero_journey"])
            if story == "random":
                self._active_story = self._create_random_scenes()
            self._current_scene_index = 0
            self._scene_progress = 0.0
            self._current_scene = self._active_story[0]
            self._next_scene = self._active_story[1 % len(self._active_story)]

        # Update scene progress
        total_scene_time = self._current_scene["duration"]
        self._scene_progress += 0.01 * speed / total_scene_time

        if self._scene_progress >= 1.0:
            self._scene_progress = 0.0
            self._current_scene_index = (self._current_scene_index + 1) % len(
                self._active_story
            )
            self._current_scene = self._active_story[self._current_scene_index]
            self._next_scene = self._active_story[
                (self._current_scene_index + 1) % len(self._active_story)
            ]

        # Prepare pixel array for full grid
        pixels = []
        for y in range(self.height):
            for x in range(self.width):
                # Get background color based on scene's background type
                bg_type = self._current_scene["background"]
                if background_color != "scene_defined":
                    bg_type = background_color

                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(x, y),
                        "r": 0,
                        "g": 0,
                        "b": 0,
                        "is_actor": False,  # Flag to track if this pixel belongs to an actor
                    }
                )

        # Create dictionary for easy pixel access
        pixel_dict = {pixel["index"]: i for i, pixel in enumerate(pixels)}

        # Draw all actors in the current scene
        actors = self._current_scene["actors"]
        for actor in actors:
            form_name = actor["form"]
            start_pos = actor["start_pos"]
            end_pos = actor["end_pos"]

            # Get interpolated position based on scene progress
            current_pos = self._interpolate_position(
                start_pos, end_pos, self._scene_progress
            )

            # Get the silhouette form
            form = self._silhouettes.get(form_name)
            if form is None:
                continue

            # Apply actor to grid
            actor_pixels = self._apply_actor_to_grid(
                form, current_pos[0], current_pos[1], silhouette_mode, size
            )

            # Set pixel colors for this actor
            for actor_pixel in actor_pixels:
                idx = actor_pixel["index"]
                if idx in pixel_dict:
                    i = pixel_dict[idx]
                    x, y = actor_pixel["coords"]
                    edge_dist = actor_pixel["edge_dist"]
                    pixels[i]["r"], pixels[i]["g"], pixels[i]["b"] = (
                        self._get_silhouette_color(
                            1.0, silhouette_mode, x, y, edge_dist
                        )
                    )
                    pixels[i]["is_actor"] = True

        # Fill in background for non-actor pixels
        scene_progress_normalized = self._current_scene_index / len(
            self._active_story
        ) + self._scene_progress / len(self._active_story)
        for i, pixel in enumerate(pixels):
            if not pixel["is_actor"]:
                # Get grid coordinates from index
                x = self.grid_config.index_to_xy(pixel["index"])[0]
                y = self.grid_config.index_to_xy(pixel["index"])[1]

                # Set background color
                bg_type = self._current_scene["background"]
                if background_color != "scene_defined":
                    bg_type = background_color

                pixels[i]["r"], pixels[i]["g"], pixels[i]["b"] = (
                    self._get_background_color(x, y, bg_type, scene_progress_normalized)
                )

        # Clean up output format
        output_pixels = []
        for pixel in pixels:
            output_pixels.append(
                {
                    "index": pixel["index"],
                    "r": pixel["r"],
                    "g": pixel["g"],
                    "b": pixel["b"],
                }
            )

        self._step += 1
        return output_pixels
