import math
import numpy as np
from typing import Dict, Any, List, Tuple
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Cube3D(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="cube3d",
            description="3D rotating wireframe cube",
            parameters=[
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
                    description="Cube size",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="edges",
                    description="Color mode (edges/vertices/rainbow)",
                ),
            ],
            category="3d",
            tags=["3d", "cube", "wireframe"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        # Define cube vertices
        self.vertices = np.array(
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
        # Define edges as pairs of vertex indices
        self.edges = [
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
        self._center_x = self.width / 2
        self._center_y = self.height / 2

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
        params = self.validate_params(params)
        rotation_speed = params["rotation_speed"]
        size = params["size"]
        color_mode = params["color_mode"]

        self._time += 0.05 * rotation_speed

        # Scale and rotate vertices
        scaled_vertices = self.vertices * size
        rotated_points = self.rotate_points(
            scaled_vertices,
            self._time * 0.5,  # X rotation
            self._time * 0.7,  # Y rotation
            self._time * 0.3,  # Z rotation
        )

        # Project points to 2D
        projected_points = [self.project_point(p) for p in rotated_points]

        # Draw edges
        pixels = []
        for i, (v1, v2) in enumerate(self.edges):
            x1, y1 = projected_points[v1]
            x2, y2 = projected_points[v2]

            if color_mode == "edges":
                # Different color for each edge
                color = self.hsv_to_rgb(i / len(self.edges), 1.0, 1.0)
            elif color_mode == "vertices":
                # Color based on vertex positions
                color = self.hsv_to_rgb((v1 + v2) / 16, 1.0, 1.0)
            else:  # rainbow
                # Color changes over time
                color = self.hsv_to_rgb(
                    self._time * 0.1 + i / len(self.edges), 1.0, 1.0
                )

            pixels.extend(self.draw_line(x1, y1, x2, y2, color))

        return pixels
