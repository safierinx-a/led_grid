import math
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class DepthTunnel(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="depth_tunnel",
            description="Optical illusion of infinite depth with moving geometric patterns",
            parameters=[
                Parameter(
                    name="shape",
                    type=str,
                    default="circle",
                    description="Shape of the tunnel (circle, square, triangle, hexagon)",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="direction",
                    type=str,
                    default="in",
                    description="Animation direction (in, out, pulse)",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="rainbow",
                    description="Color scheme (rainbow, contrast, monochrome, gradient)",
                ),
                Parameter(
                    name="line_width",
                    type=int,
                    default=1,
                    min_value=1,
                    max_value=3,
                    description="Width of lines (1-3 pixels)",
                ),
                Parameter(
                    name="pattern_density",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    description="Density of patterns (0.5-2.0)",
                ),
            ],
            category="illusions",
            tags=["optical", "depth", "tunnel", "illusion"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._step = 0
        self._max_radius = max(self.width, self.height) / 2

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

    def _get_layer_color(
        self, layer: int, total_layers: int, color_mode: str
    ) -> Tuple[int, int, int]:
        """Get color for a specific layer based on color mode"""
        if color_mode == "rainbow":
            # Rainbow colors cycling
            hue = (layer / total_layers + self._step * 0.01) % 1.0
            return self._hsv_to_rgb(hue, 0.9, 1.0)

        elif color_mode == "contrast":
            # Alternating high contrast colors
            if layer % 2 == 0:
                return (255, 255, 255)  # White
            else:
                return (0, 0, 0)  # Black

        elif color_mode == "monochrome":
            # Single color with varying brightness
            brightness = 0.3 + 0.7 * (layer / total_layers)
            hue = (self._step * 0.01) % 1.0
            return self._hsv_to_rgb(hue, 0.8, brightness)

        elif color_mode == "gradient":
            # Gradient between two colors
            t = layer / total_layers
            hue1 = (self._step * 0.01) % 1.0
            hue2 = (hue1 + 0.5) % 1.0
            hue = hue1 * (1 - t) + hue2 * t
            return self._hsv_to_rgb(hue, 0.9, 0.9)

        else:
            # Default: white
            return (255, 255, 255)

    def _is_on_shape_edge(
        self,
        x: int,
        y: int,
        center_x: float,
        center_y: float,
        radius: float,
        shape: str,
        line_width: int,
    ) -> bool:
        """Check if a point is on the edge of the specified shape"""
        # Calculate distance from center
        dx = x - center_x
        dy = y - center_y
        distance = math.sqrt(dx**2 + dy**2)

        if shape == "circle":
            # Circle: check if distance is within line_width of radius
            return abs(distance - radius) < line_width

        elif shape == "square":
            # Square: calculate the maximum coordinate distance
            max_coord = max(abs(dx), abs(dy))
            # Check if point is on the square edge
            return abs(max_coord - radius) < line_width

        elif shape == "triangle":
            # Equilateral triangle
            # Convert to polar coordinates
            angle = math.atan2(dy, dx)
            if angle < 0:
                angle += 2 * math.pi

            # Normalize angle to which side of triangle
            side = int(angle / (2 * math.pi / 3))
            angle_within_side = angle - side * (2 * math.pi / 3)

            # Distance to edge varies with angle
            edge_distance = radius / math.cos(
                min(abs(angle_within_side - math.pi / 3), math.pi / 3)
            )

            # Check if point is on the triangle edge
            return abs(distance - edge_distance) < line_width

        elif shape == "hexagon":
            # Regular hexagon
            angle = math.atan2(dy, dx)
            if angle < 0:
                angle += 2 * math.pi

            # Normalize angle to which side of hexagon
            side = int(angle / (math.pi / 3))
            angle_within_side = angle - side * (math.pi / 3)

            # Distance to edge varies with angle
            edge_distance = radius / math.cos(
                min(abs(angle_within_side - math.pi / 6), math.pi / 6)
            )

            # Check if point is on the hexagon edge
            return abs(distance - edge_distance) < line_width

        else:
            # Default to circle
            return abs(distance - radius) < line_width

    def _get_animation_phase(self, direction: str, speed: float) -> float:
        """Calculate animation phase based on direction and speed"""
        base_phase = self._step * 0.05 * speed

        if direction == "in":
            # Moving inward (positive phase)
            return base_phase
        elif direction == "out":
            # Moving outward (negative phase)
            return -base_phase
        elif direction == "pulse":
            # Oscillating in and out
            return math.sin(base_phase) * 5
        else:
            # Default to inward
            return base_phase

    def _draw_layer(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        shape: str,
        color: Tuple[int, int, int],
        line_width: int,
    ) -> List[Dict[str, int]]:
        """Draw a single layer of the tunnel with the specified shape and radius"""
        pixels = []

        # Optimization: only check pixels that could potentially be part of the shape
        start_x = max(0, int(center_x - radius - line_width))
        end_x = min(self.width, int(center_x + radius + line_width + 1))
        start_y = max(0, int(center_y - radius - line_width))
        end_y = min(self.height, int(center_y + radius + line_width + 1))

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                if self._is_on_shape_edge(
                    x, y, center_x, center_y, radius, shape, line_width
                ):
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": color[0],
                            "g": color[1],
                            "b": color[2],
                        }
                    )

        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the depth tunnel pattern"""
        # Validate parameters
        params = self.validate_params(params)
        shape = params["shape"]
        speed = params["speed"]
        direction = params["direction"]
        color_mode = params["color_mode"]
        line_width = params["line_width"]
        pattern_density = params["pattern_density"]

        # Animation phase affects the visual depth effect
        phase = self._get_animation_phase(direction, speed)

        # Center of the grid
        center_x = self.width / 2
        center_y = self.height / 2

        # Calculate number of layers based on density
        # More density means more concentric shapes
        num_layers = int(10 * pattern_density)

        # Draw all layers
        all_pixels = []

        for i in range(num_layers):
            # Calculate radius for this layer
            # The modulo operation creates the looping tunnel effect
            layer_phase = (i + phase) % num_layers
            # Map layer_phase (0 to num_layers) to a radius (min_radius to max_radius)
            min_radius = 1
            radius = min_radius + (self._max_radius - min_radius) * (
                layer_phase / num_layers
            )

            # Get color for this layer
            color = self._get_layer_color(i, num_layers, color_mode)

            # Draw the layer
            layer_pixels = self._draw_layer(
                center_x, center_y, radius, shape, color, line_width
            )
            all_pixels.extend(layer_pixels)

        self._step += 1
        return all_pixels
