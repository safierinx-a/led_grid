import math
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Polyhedra3D(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="polyhedra3d",
            description="Bold 3D geometric shapes optimized for 24x25 LED grid with dynamic transformations",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="cube",
                    description="Pattern variation (cube, tetra, octa, star, prism, diamond)",
                ),
                Parameter(
                    name="rotation_speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Rotation speed",
                ),
                Parameter(
                    name="size",
                    type=float,
                    default=0.8,
                    min_value=0.1,
                    max_value=2.0,
                    description="Shape size",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="neon",
                    description="Color mode (neon, pulse, cyber, rainbow, energy)",
                ),
                Parameter(
                    name="glow",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Edge glow intensity",
                ),
                Parameter(
                    name="transform",
                    type=str,
                    default="spin",
                    description="Transform mode (spin, morph, pulse, wave, bounce)",
                ),
            ],
            category="3d",
            tags=["3d", "geometric", "wireframe", "bold"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._shape_buffers = {
            "cube": self._init_cube(),
            "tetra": self._init_tetrahedron(),
            "octa": self._init_octahedron(),
            "star": self._init_star(),
            "prism": self._init_prism(),
            "diamond": self._init_diamond(),
        }
        self._current_vertices = None
        self._current_edges = None
        self._prev_shape = None
        self._morph_progress = 0.0

    def _init_cube(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize cube with bold proportions"""
        vertices = np.array(
            [
                [-1, -1, -1],
                [1, -1, -1],
                [1, 1, -1],
                [-1, 1, -1],
                [-1, -1, 1],
                [1, -1, 1],
                [1, 1, 1],
                [-1, 1, 1],
            ],
            dtype=float,
        )
        edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),  # Bottom face
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),  # Top face
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),  # Vertical edges
        ]
        return vertices, edges

    def _init_tetrahedron(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize tetrahedron with bold proportions"""
        vertices = np.array(
            [
                [0, -1, -1 / math.sqrt(2)],
                [-1, 1, -1 / math.sqrt(2)],
                [1, 1, -1 / math.sqrt(2)],
                [0, 0, math.sqrt(2)],
            ],
            dtype=float,
        )
        edges = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
        return vertices * 1.5, edges  # Scale up for better visibility

    def _init_octahedron(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize octahedron with bold proportions"""
        vertices = np.array(
            [
                [0, 0, 1.5],
                [1.5, 0, 0],
                [0, 1.5, 0],
                [-1.5, 0, 0],
                [0, -1.5, 0],
                [0, 0, -1.5],
            ],
            dtype=float,
        )
        edges = [
            (0, 1),
            (0, 2),
            (0, 3),
            (0, 4),  # Top vertex connections
            (5, 1),
            (5, 2),
            (5, 3),
            (5, 4),  # Bottom vertex connections
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 1),  # Middle square
        ]
        return vertices, edges

    def _init_star(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize star-shaped polyhedron"""
        vertices = []
        phi = (1 + math.sqrt(5)) / 2  # Golden ratio
        scale = 1.2  # Increased scale for visibility

        # Create star points
        for i in range(12):
            angle = i * math.pi / 6
            vertices.append(
                [
                    math.cos(angle) * scale,
                    math.sin(angle) * scale,
                    phi * scale if i % 2 == 0 else -phi * scale,
                ]
            )

        vertices = np.array(vertices, dtype=float)
        edges = []
        # Connect star points
        for i in range(12):
            edges.append((i, (i + 1) % 12))
            edges.append((i, (i + 2) % 12))

        return vertices, edges

    def _init_prism(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize triangular prism with bold proportions"""
        vertices = np.array(
            [
                [-1, -1, -1],
                [1, -1, -1],
                [0, 1.5, -1],  # Bottom triangle
                [-1, -1, 1],
                [1, -1, 1],
                [0, 1.5, 1],  # Top triangle
            ],
            dtype=float,
        )
        edges = [
            (0, 1),
            (1, 2),
            (2, 0),  # Bottom face
            (3, 4),
            (4, 5),
            (5, 3),  # Top face
            (0, 3),
            (1, 4),
            (2, 5),  # Vertical edges
        ]
        return vertices * 1.2, edges  # Scale up for better visibility

    def _init_diamond(self) -> tuple[np.ndarray, List[tuple[int, int]]]:
        """Initialize diamond shape with bold proportions"""
        vertices = np.array(
            [
                [0, 0, 2],  # Top point
                [1, 1, 0],
                [-1, 1, 0],
                [-1, -1, 0],
                [1, -1, 0],  # Middle points
                [0, 0, -2],  # Bottom point
            ],
            dtype=float,
        )
        edges = [
            (0, 1),
            (0, 2),
            (0, 3),
            (0, 4),  # Top to middle
            (5, 1),
            (5, 2),
            (5, 3),
            (5, 4),  # Bottom to middle
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 1),  # Middle square
        ]
        return vertices, edges

    def _get_glow_color(
        self, base_color: tuple[int, int, int], intensity: float, phase: float
    ) -> tuple[int, int, int]:
        """Get glowing color effect"""
        glow = (math.sin(phase) * 0.5 + 0.5) * intensity
        return tuple(min(255, int(c * (1 + glow))) for c in base_color)

    def _get_color(self, index: float, mode: str, time: float) -> tuple[int, int, int]:
        """Get enhanced color based on mode"""
        if mode == "neon":
            # Bright neon colors
            hue = (index * 0.2 + time * 0.1) % 1.0
            return self.hsv_to_rgb(hue, 1.0, 1.0)
        elif mode == "pulse":
            # Pulsing color effect
            pulse = math.sin(time * 2 + index * math.pi) * 0.3 + 0.7
            hue = (index * 0.1 + time * 0.05) % 1.0
            return self.hsv_to_rgb(hue, 1.0, pulse)
        elif mode == "cyber":
            # Cyberpunk-inspired colors
            hue = 0.6 + math.sin(time + index) * 0.1
            sat = 0.8 + math.sin(time * 2 + index) * 0.2
            return self.hsv_to_rgb(hue, sat, 1.0)
        elif mode == "rainbow":
            # Smooth rainbow transitions
            hue = (time * 0.1 + index / 8) % 1.0
            return self.hsv_to_rgb(hue, 1.0, 1.0)
        else:  # energy
            # Energy level visualization
            energy = math.sin(time * 3 + index * math.pi) * 0.5 + 0.5
            return self.hsv_to_rgb(energy * 0.3, 1.0, 1.0)

    def _apply_transform(
        self, points: np.ndarray, transform: str, time: float
    ) -> np.ndarray:
        """Apply dynamic transformations"""
        transformed = points.copy()

        if transform == "spin":
            # Enhanced spinning effect
            angle = time * 2
            transformed = self.rotate_points(
                transformed,
                time * 0.5,  # X rotation
                time * 0.7,  # Y rotation
                time * 0.3,  # Z rotation
            )
        elif transform == "morph":
            # Morphing between shapes
            if self._prev_shape and self._prev_shape != self._current_vertices:
                transformed = (
                    transformed * (1 - self._morph_progress)
                    + self._prev_shape * self._morph_progress
                )
                self._morph_progress = min(1.0, self._morph_progress + 0.05)
        elif transform == "pulse":
            # Pulsing size effect
            scale = math.sin(time * 2) * 0.2 + 1.0
            transformed *= scale
        elif transform == "wave":
            # Wave deformation
            for i in range(len(transformed)):
                transformed[i, 2] += math.sin(time * 2 + transformed[i, 0]) * 0.3
        elif transform == "bounce":
            # Bouncing effect
            bounce = abs(math.sin(time * 1.5)) * 0.5
            transformed[:, 1] += bounce

        return transformed

    def rotate_points(
        self, points: np.ndarray, rx: float, ry: float, rz: float
    ) -> np.ndarray:
        """Apply 3D rotation to points"""
        # Rotation matrices
        rot_x = np.array(
            [
                [1, 0, 0],
                [0, math.cos(rx), -math.sin(rx)],
                [0, math.sin(rx), math.cos(rx)],
            ]
        )
        rot_y = np.array(
            [
                [math.cos(ry), 0, math.sin(ry)],
                [0, 1, 0],
                [-math.sin(ry), 0, math.cos(ry)],
            ]
        )
        rot_z = np.array(
            [
                [math.cos(rz), -math.sin(rz), 0],
                [math.sin(rz), math.cos(rz), 0],
                [0, 0, 1],
            ]
        )

        # Apply rotations
        points = points @ rot_x @ rot_y @ rot_z
        return points

    def project_point(self, point: np.ndarray) -> Tuple[float, float]:
        """Project 3D point to 2D screen space"""
        z = point[2] + 3  # Move cube away from camera
        if z <= 0:
            z = 0.001
        # Apply perspective projection
        factor = 1.0 / z
        x = point[0] * factor * self.width * 0.4 + self._center_x
        y = point[1] * factor * self.height * 0.4 + self._center_y
        return x, y

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a line using Bresenham's algorithm"""
        pixels = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        steep = dy > dx

        if steep:
            x1, y1 = y1, x1
            x2, y2 = y2, x2

        if x1 > x2:
            x1, x2 = x2, x1
            y1, y2 = y2, y1

        dx = x2 - x1
        dy = abs(y2 - y1)
        error = dx / 2
        y = y1
        y_step = 1 if y1 < y2 else -1

        for x in range(int(x1), int(x2) + 1):
            if steep:
                px, py = y, x
            else:
                px, py = x, y

            if 0 <= px < self.width and 0 <= py < self.height:
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(int(px), int(py)),
                        "r": color[0],
                        "g": color[1],
                        "b": color[2],
                    }
                )

            error -= dy
            if error < 0:
                y += y_step
                error += dx

        return pixels

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
        """Generate a frame of the 3D cube pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "cube":
            pattern_pixels = self._generate_cube(params)
        elif variation == "sphere":
            pattern_pixels = self._generate_sphere(params)
        elif variation == "pyramid":
            pattern_pixels = self._generate_pyramid(params)
        elif variation == "helix":
            pattern_pixels = self._generate_helix(params)
        else:  # torus
            pattern_pixels = self._generate_torus(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
