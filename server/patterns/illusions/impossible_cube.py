import math
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ImpossibleCube(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="impossible_cube",
            description="3D impossible shapes that seem to defy spatial logic",
            parameters=[
                Parameter(
                    name="shape",
                    type=str,
                    default="cube",
                    description="Impossible shape to render (cube, penrose, staircase, triangle)",
                ),
                Parameter(
                    name="rotation_speed",
                    type=float,
                    default=1.0,
                    min_value=0.0,
                    max_value=3.0,
                    description="Speed of rotation (0.0-3.0)",
                ),
                Parameter(
                    name="size",
                    type=float,
                    default=0.8,
                    min_value=0.3,
                    max_value=1.0,
                    description="Size of shape (0.3-1.0)",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="edges",
                    description="Coloring style (edges, faces, rainbow, wireframe)",
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
            category="illusions",
            tags=["optical", "3D", "impossible", "cube"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0

        # Define shape models
        self._shapes = {
            "cube": self._create_impossible_cube(),
            "penrose": self._create_penrose_triangle(),
            "staircase": self._create_penrose_stairs(),
            "triangle": self._create_impossible_triangle(),
        }

    def _create_impossible_cube(self) -> Dict[str, Any]:
        """Create vertices and edges for an impossible cube"""
        # Basic cube vertices
        vertices = [
            [-1, -1, -1],  # 0: back-bottom-left
            [1, -1, -1],  # 1: back-bottom-right
            [1, 1, -1],  # 2: back-top-right
            [-1, 1, -1],  # 3: back-top-left
            [-1, -1, 1],  # 4: front-bottom-left
            [1, -1, 1],  # 5: front-bottom-right
            [1, 1, 1],  # 6: front-top-right
            [-1, 1, 1],  # 7: front-top-left
        ]

        # Normal edges that define a cube
        normal_edges = [
            # Back face
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            # Front face
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            # Connecting edges
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]

        # Special impossible edges that create the illusion
        impossible_edges = [
            # These edges create the impossible connections
            (1, 7),
            (3, 5),
            (0, 6),
        ]

        # Faces for coloring
        faces = [
            [0, 1, 2, 3],  # Back
            [4, 5, 6, 7],  # Front
            [0, 1, 5, 4],  # Bottom
            [2, 3, 7, 6],  # Top
            [0, 3, 7, 4],  # Left
            [1, 2, 6, 5],  # Right
        ]

        return {
            "vertices": vertices,
            "normal_edges": normal_edges,
            "impossible_edges": impossible_edges,
            "faces": faces,
        }

    def _create_penrose_triangle(self) -> Dict[str, Any]:
        """Create vertices and edges for a Penrose triangle"""
        # Define vertices for a Penrose triangle
        vertices = [
            [-1, -1, 0],  # 0: bottom-left
            [1, -1, 0],  # 1: bottom-right
            [1, 1, 0],  # 2: top-right
            [-1, 1, 0],  # 3: top-left
            [0, -0.5, 0.5],  # 4: middle front-bottom
            [0.5, 0, 0.5],  # 5: middle front-right
            [0, 0.5, 0.5],  # 6: middle front-top
            [-0.5, 0, 0.5],  # 7: middle front-left
        ]

        # Normal edges
        normal_edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),  # Outer square
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),  # Inner square
        ]

        # Impossible edges that create the illusion
        impossible_edges = [
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),  # Connect outer to inner in impossible way
        ]

        # Faces for coloring
        faces = [
            [0, 1, 5, 4],  # Bottom face
            [1, 2, 6, 5],  # Right face
            [2, 3, 7, 6],  # Top face
            [3, 0, 4, 7],  # Left face
        ]

        return {
            "vertices": vertices,
            "normal_edges": normal_edges,
            "impossible_edges": impossible_edges,
            "faces": faces,
        }

    def _create_penrose_stairs(self) -> Dict[str, Any]:
        """Create vertices and edges for Penrose stairs (impossible staircase)"""
        # Vertices for a square spiral staircase
        vertices = []
        steps = 8

        # Create vertices for each step in a spiral
        for i in range(steps):
            angle = i * 2 * math.pi / steps
            next_angle = (i + 1) * 2 * math.pi / steps

            # Inner corner of step
            x1 = 0.5 * math.cos(angle)
            y1 = 0.5 * math.sin(angle)
            z1 = i / steps

            # Outer corner (front)
            x2 = math.cos(angle)
            y2 = math.sin(angle)
            z2 = i / steps

            # Outer corner (back) - same level
            x3 = math.cos(next_angle)
            y3 = math.sin(next_angle)
            z3 = i / steps

            # Inner corner (next step)
            x4 = 0.5 * math.cos(next_angle)
            y4 = 0.5 * math.sin(next_angle)
            z4 = (i + 1) / steps

            vertices.extend([[x1, y1, z1], [x2, y2, z2], [x3, y3, z3], [x4, y4, z4]])

        # Normal edges connect adjacent vertices to form steps
        normal_edges = []
        for i in range(steps):
            base = i * 4
            # Connect the 4 corners of each step
            normal_edges.extend(
                [
                    (base, base + 1),  # Inner to outer front
                    (base + 1, base + 2),  # Outer front to outer back
                    (base + 2, base + 3),  # Outer back to next inner
                    (base + 3, (base + 4) % (steps * 4)),  # Inner to next inner
                ]
            )

        # Impossible edges create the continuous loop illusion
        impossible_edges = [(steps * 4 - 1, 0)]  # Connect last to first

        # Faces for coloring (top of each step)
        faces = []
        for i in range(steps):
            base = i * 4
            faces.append([base, base + 1, base + 2, base + 3])

        return {
            "vertices": vertices,
            "normal_edges": normal_edges,
            "impossible_edges": impossible_edges,
            "faces": faces,
        }

    def _create_impossible_triangle(self) -> Dict[str, Any]:
        """Create vertices and edges for an impossible triangle"""
        # Vertices for a more complex impossible triangle
        s = 0.8  # Size factor
        h = s * math.sqrt(3) / 2  # Height of equilateral triangle

        vertices = [
            # Bottom bar
            [-s, -h, 0],  # 0: bottom-left front
            [s, -h, 0],  # 1: bottom-right front
            [-s, -h, -0.5 * s],  # 2: bottom-left back
            [s, -h, -0.5 * s],  # 3: bottom-right back
            # Right bar
            [s, -h, 0],  # 4: right-bottom front
            [0, h, 0],  # 5: right-top front
            [s, -h, -0.5 * s],  # 6: right-bottom back
            [0, h, -0.5 * s],  # 7: right-top back
            # Left bar
            [-s, -h, 0],  # 8: left-bottom front
            [0, h, 0],  # 9: left-top front
            [-s, -h, -0.5 * s],  # 10: left-bottom back
            [0, h, 0.5 * s],  # 11: left-top "impossible" vertex
        ]

        # Normal edges
        normal_edges = [
            # Bottom bar
            (0, 1),
            (2, 3),
            (0, 2),
            (1, 3),
            # Right bar
            (4, 5),
            (6, 7),
            (4, 6),
            (5, 7),
            # Left bar
            (8, 9),
            (10, 11),
            (8, 10),
            (9, 11),
        ]

        # Impossible edges - create the illusion
        impossible_edges = [
            (3, 6),
            (7, 11),
            (11, 2),  # The "impossible" connections
        ]

        # Faces for coloring
        faces = [
            [0, 1, 3, 2],  # Bottom bar
            [4, 5, 7, 6],  # Right bar
            [8, 9, 11, 10],  # Left bar
        ]

        return {
            "vertices": vertices,
            "normal_edges": normal_edges,
            "impossible_edges": impossible_edges,
            "faces": faces,
        }

    def _rotate_point(
        self, point: List[float], angle_x: float, angle_y: float, angle_z: float
    ) -> List[float]:
        """Rotate a 3D point around all three axes"""
        x, y, z = point

        # Rotate around X-axis
        cos_x, sin_x = math.cos(angle_x), math.sin(angle_x)
        y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x

        # Rotate around Y-axis
        cos_y, sin_y = math.cos(angle_y), math.sin(angle_y)
        x, z = x * cos_y + z * sin_y, -x * sin_y + z * cos_y

        # Rotate around Z-axis
        cos_z, sin_z = math.cos(angle_z), math.sin(angle_z)
        x, y = x * cos_z - y * sin_z, x * sin_z + y * cos_z

        return [x, y, z]

    def _project_point(self, point: List[float]) -> Tuple[float, float]:
        """Project a 3D point to 2D with perspective"""
        x, y, z = point

        # Simple perspective projection
        scale = 5.0 / (5.0 + z)  # Larger number = less perspective distortion
        return x * scale, y * scale

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

    def _draw_line(
        self, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a line using Bresenham's algorithm"""
        pixels = []

        # Ensure coordinates are integers
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)

        # Check if line is completely out of bounds
        if (
            (x0 < 0 and x1 < 0)
            or (x0 >= self.width and x1 >= self.width)
            or (y0 < 0 and y1 < 0)
            or (y0 >= self.height and y1 >= self.height)
        ):
            return pixels

        steep = abs(y1 - y0) > abs(x1 - x0)
        if steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1

        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0

        dx = x1 - x0
        dy = abs(y1 - y0)
        error = dx // 2
        y = y0
        y_step = 1 if y0 < y1 else -1

        for x in range(x0, x1 + 1):
            if steep:
                px, py = y, x
            else:
                px, py = x, y

            # Only draw if within bounds
            if 0 <= px < self.width and 0 <= py < self.height:
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(px, py),
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

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the impossible cube pattern"""
        # Validate parameters
        params = self.validate_params(params)
        shape_name = params["shape"]
        rotation_speed = params["rotation_speed"]
        size = params["size"]
        color_mode = params["color_mode"]
        pos_x = params["position_x"]
        pos_y = params["position_y"]

        # Get shape definition
        shape_def = self._shapes.get(shape_name, self._shapes["cube"])

        # Calculate rotation angles based on step and speed
        angle_x = self._step * 0.02 * rotation_speed
        angle_y = self._step * 0.03 * rotation_speed
        angle_z = self._step * 0.01 * rotation_speed

        # Transform center position to pixel coordinates
        center_x = int(pos_x * self.width)
        center_y = int(pos_y * self.height)

        # Scale factor based on size parameter
        scale = min(self.width, self.height) * 0.4 * size

        # Rotate and project all vertices
        projected_vertices = []
        for vertex in shape_def["vertices"]:
            # Apply rotation
            rotated = self._rotate_point(vertex, angle_x, angle_y, angle_z)

            # Apply projection
            x2d, y2d = self._project_point(rotated)

            # Apply scaling and position
            screen_x = center_x + x2d * scale
            screen_y = center_y + y2d * scale

            projected_vertices.append((screen_x, screen_y))

        # Pixels for the entire shape
        pixels = []

        # Draw normal edges
        for start_idx, end_idx in shape_def["normal_edges"]:
            x0, y0 = projected_vertices[start_idx]
            x1, y1 = projected_vertices[end_idx]

            # Color based on color_mode
            if color_mode == "edges":
                # Unique color per edge
                hue = (start_idx + end_idx) / (len(shape_def["vertices"]))
                color = self._hsv_to_rgb(hue, 0.8, 1.0)
            elif color_mode == "rainbow":
                # Rainbow effect over time
                hue = (self._step * 0.01 + (start_idx + end_idx) / 20) % 1.0
                color = self._hsv_to_rgb(hue, 0.8, 1.0)
            else:
                # Default white
                color = (255, 255, 255)

            # Draw the line
            line_pixels = self._draw_line(x0, y0, x1, y1, color)
            pixels.extend(line_pixels)

        # Draw impossible edges with special colors
        for start_idx, end_idx in shape_def["impossible_edges"]:
            x0, y0 = projected_vertices[start_idx]
            x1, y1 = projected_vertices[end_idx]

            # Special color for impossible edges
            if color_mode == "wireframe":
                color = (255, 255, 255)  # White
            else:
                # Pulsing red for impossible edges
                intensity = (math.sin(self._step * 0.1) + 1) * 0.4 + 0.2
                color = (int(255 * intensity), 0, int(80 * intensity))

            # Draw the line
            line_pixels = self._draw_line(x0, y0, x1, y1, color)
            pixels.extend(line_pixels)

        self._step += 1
        return pixels
