import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Emoji(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="emoji",
            description="Animated emoji faces",
            parameters=[
                Parameter(
                    name="expression",
                    type=str,
                    default="happy",
                    description="Facial expression (happy/wink/love/surprised/cool)",
                ),
                Parameter(
                    name="animation_speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Animation speed",
                ),
                Parameter(
                    name="color_style",
                    type=str,
                    default="classic",
                    description="Color style (classic/rainbow/neon)",
                ),
            ],
            category="fun",
            tags=["emoji", "face", "animation"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2

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

    def get_face_color(self, color_style: str) -> tuple[int, int, int]:
        """Get face color based on style"""
        if color_style == "classic":
            return (255, 220, 0)  # Classic yellow
        elif color_style == "rainbow":
            hue = (self._time * 0.2) % 1.0
            return self.hsv_to_rgb(hue, 0.7, 1.0)
        else:  # neon
            return self.hsv_to_rgb(0.3, 1.0, 1.0)  # Neon green

    def draw_circle(
        self, cx: float, cy: float, radius: float, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a filled circle"""
        pixels = []
        for y in range(
            max(0, int(cy - radius)), min(self.height, int(cy + radius + 1))
        ):
            for x in range(
                max(0, int(cx - radius)), min(self.width, int(cx + radius + 1))
            ):
                dx = x - cx
                dy = y - cy
                if dx * dx + dy * dy <= radius * radius:
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(x, y),
                            "r": color[0],
                            "g": color[1],
                            "b": color[2],
                        }
                    )
        return pixels

    def draw_arc(
        self,
        cx: float,
        cy: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        color: tuple[int, int, int],
        thickness: float = 1.0,
    ) -> List[Dict[str, int]]:
        """Draw an arc"""
        pixels = []
        for angle in range(
            int(start_angle * 180 / math.pi), int(end_angle * 180 / math.pi)
        ):
            rad = angle * math.pi / 180
            for r in range(int(radius - thickness), int(radius + thickness)):
                x = int(cx + r * math.cos(rad))
                y = int(cy + r * math.sin(rad))
                if 0 <= x < self.width and 0 <= y < self.height:
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
        params = self.validate_params(params)
        expression = params["expression"]
        animation_speed = params["animation_speed"]
        color_style = params["color_style"]

        self._time += 0.05 * animation_speed
        pixels = []

        # Draw face
        face_color = self.get_face_color(color_style)
        pixels.extend(
            self.draw_circle(
                self._center_x,
                self._center_y,
                min(self.width, self.height) * 0.4,
                face_color,
            )
        )

        # Draw features based on expression
        if expression == "happy":
            # Eyes
            eye_y = self._center_y - 2
            left_eye_x = self._center_x - 5
            right_eye_x = self._center_x + 5
            pixels.extend(self.draw_circle(left_eye_x, eye_y, 2, (0, 0, 0)))
            pixels.extend(self.draw_circle(right_eye_x, eye_y, 2, (0, 0, 0)))

            # Animated smile
            smile_y = self._center_y + 3
            smile_phase = math.sin(self._time * 2) * 0.2 + 0.8
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    smile_y,
                    6 * smile_phase,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    1.5,
                )
            )

        elif expression == "wink":
            # Left eye
            pixels.extend(
                self.draw_circle(self._center_x - 5, self._center_y - 2, 2, (0, 0, 0))
            )

            # Right eye (winking)
            wink_phase = (math.sin(self._time * 4) + 1) / 2
            if wink_phase < 0.5:
                pixels.extend(
                    self.draw_circle(
                        self._center_x + 5, self._center_y - 2, 2, (0, 0, 0)
                    )
                )
            else:
                pixels.extend(
                    self.draw_arc(
                        self._center_x + 5,
                        self._center_y - 2,
                        2,
                        math.pi * 0.8,
                        math.pi * 1.2,
                        (0, 0, 0),
                        1.0,
                    )
                )

            # Smirk
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    self._center_y + 3,
                    5,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    1.5,
                )
            )

        elif expression == "love":
            # Heart eyes
            heart_scale = math.sin(self._time * 3) * 0.2 + 0.8
            for side in [-1, 1]:
                center_x = self._center_x + side * 5
                center_y = self._center_y - 2
                # Draw heart shape
                pixels.extend(
                    self.draw_circle(
                        center_x - 1, center_y, 2 * heart_scale, (255, 0, 0)
                    )
                )
                pixels.extend(
                    self.draw_circle(
                        center_x + 1, center_y, 2 * heart_scale, (255, 0, 0)
                    )
                )
                pixels.extend(
                    self.draw_arc(
                        center_x,
                        center_y + 1,
                        2 * heart_scale,
                        math.pi * 0.8,
                        math.pi * 1.2,
                        (255, 0, 0),
                        1.0,
                    )
                )

            # Big smile
            smile_y = self._center_y + 4
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    smile_y,
                    7,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    2.0,
                )
            )

        elif expression == "surprised":
            # Wide eyes
            eye_scale = math.sin(self._time * 4) * 0.3 + 1.2
            pixels.extend(
                self.draw_circle(
                    self._center_x - 5, self._center_y - 2, 2.5 * eye_scale, (0, 0, 0)
                )
            )
            pixels.extend(
                self.draw_circle(
                    self._center_x + 5, self._center_y - 2, 2.5 * eye_scale, (0, 0, 0)
                )
            )

            # O-shaped mouth
            mouth_scale = math.sin(self._time * 3) * 0.2 + 1.0
            pixels.extend(
                self.draw_circle(
                    self._center_x, self._center_y + 4, 3 * mouth_scale, (0, 0, 0)
                )
            )

        else:  # cool
            # Sunglasses
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    self._center_y - 2,
                    8,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    1.5,
                )
            )
            pixels.extend(
                self.draw_circle(self._center_x - 5, self._center_y - 2, 2.5, (0, 0, 0))
            )
            pixels.extend(
                self.draw_circle(self._center_x + 5, self._center_y - 2, 2.5, (0, 0, 0))
            )

            # Cool smile
            smile_phase = math.sin(self._time) * 0.1 + 1.0
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    self._center_y + 3,
                    5 * smile_phase,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    1.5,
                )
            )

        return pixels
