import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Emoji(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="emoji",
            description="Bold animated emoji faces optimized for 24x25 LED grid with dynamic expressions",
            parameters=[
                Parameter(
                    name="expression",
                    type=str,
                    default="happy",
                    description="Expression (happy, wink, love, surprised, cool, excited, sad, angry, sleepy, party)",
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
                    description="Color style (classic, rainbow, neon, pastel, sunset, cyber)",
                ),
                Parameter(
                    name="size",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=1.5,
                    description="Emoji size multiplier",
                ),
                Parameter(
                    name="tilt",
                    type=float,
                    default=0.0,
                    min_value=-30.0,
                    max_value=30.0,
                    description="Head tilt angle in degrees",
                ),
                Parameter(
                    name="bounce",
                    type=float,
                    default=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Bounce animation intensity",
                ),
                Parameter(
                    name="glow",
                    type=float,
                    default=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    description="Glow effect intensity",
                ),
            ],
            category="fun",
            tags=["emoji", "face", "animation", "interactive"],
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

    def get_face_color(
        self, color_style: str, glow: float = 0.0
    ) -> tuple[int, int, int]:
        """Get face color based on style with optional glow effect"""
        if color_style == "classic":
            base = (255, 220, 0)  # Classic yellow
        elif color_style == "rainbow":
            hue = (self._time * 0.2) % 1.0
            base = self.hsv_to_rgb(hue, 0.7, 1.0)
        elif color_style == "neon":
            base = self.hsv_to_rgb(0.3, 1.0, 1.0)  # Neon green
        elif color_style == "pastel":
            hue = (self._time * 0.1) % 1.0
            base = self.hsv_to_rgb(hue, 0.4, 1.0)
        elif color_style == "sunset":
            phase = (math.sin(self._time * 0.5) + 1) / 2
            hue = 0.05 + phase * 0.1  # Shift between orange and pink
            base = self.hsv_to_rgb(hue, 0.8, 1.0)
        else:  # cyber
            # Cyberpunk-style color shifting
            hue = 0.6 + math.sin(self._time) * 0.1
            sat = 0.8 + math.sin(self._time * 2) * 0.2
            base = self.hsv_to_rgb(hue, sat, 1.0)

        # Apply glow effect
        if glow > 0:
            glow_factor = 0.3 * glow * (math.sin(self._time * 4) * 0.5 + 0.5)
            return tuple(min(255, int(c * (1 + glow_factor))) for c in base)
        return base

    def apply_transform(
        self, x: float, y: float, tilt: float, bounce: float
    ) -> tuple[float, float]:
        """Apply transformations (tilt and bounce) to coordinates"""
        if bounce > 0:
            y += math.sin(self._time * 3) * 2 * bounce

        if tilt != 0:
            # Rotate point around center
            rad = math.radians(tilt)
            dx = x - self._center_x
            dy = y - self._center_y
            rx = dx * math.cos(rad) - dy * math.sin(rad)
            ry = dx * math.sin(rad) + dy * math.cos(rad)
            return (self._center_x + rx, self._center_y + ry)

        return (x, y)

    def draw_glow(
        self,
        x: float,
        y: float,
        radius: float,
        color: tuple[int, int, int],
        intensity: float,
    ) -> List[Dict[str, int]]:
        """Draw a glowing effect around a point"""
        pixels = []
        glow_radius = radius * 2
        for dy in range(-int(glow_radius), int(glow_radius) + 1):
            for dx in range(-int(glow_radius), int(glow_radius) + 1):
                px, py = int(x + dx), int(y + dy)
                if 0 <= px < self.width and 0 <= py < self.height:
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= glow_radius:
                        glow_factor = (1 - dist / glow_radius) * intensity
                        glow_color = tuple(int(c * glow_factor) for c in color)
                        pixels.append(
                            {
                                "index": self.grid_config.xy_to_index(px, py),
                                "r": glow_color[0],
                                "g": glow_color[1],
                                "b": glow_color[2],
                            }
                        )
        return pixels

    def draw_circle(
        self,
        cx: float,
        cy: float,
        radius: float,
        color: tuple[int, int, int],
        tilt: float = 0.0,
        bounce: float = 0.0,
        block_size: int = 1,
    ) -> List[Dict[str, int]]:
        """Draw a filled circle with transformations"""
        pixels = []
        cx, cy = self.apply_transform(cx, cy, tilt, bounce)

        for by in range(
            max(0, int(cy - radius)),
            min(self.height, int(cy + radius + block_size)),
            block_size,
        ):
            for bx in range(
                max(0, int(cx - radius)),
                min(self.width, int(cx + radius + block_size)),
                block_size,
            ):
                # Check if block center is within circle
                block_cx = bx + block_size / 2
                block_cy = by + block_size / 2
                dx = block_cx - cx
                dy = block_cy - cy
                if dx * dx + dy * dy <= radius * radius:
                    # Draw block
                    for dy in range(block_size):
                        for dx in range(block_size):
                            px, py = bx + dx, by + dy
                            if 0 <= px < self.width and 0 <= py < self.height:
                                pixels.append(
                                    {
                                        "index": self.grid_config.xy_to_index(px, py),
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
        tilt: float = 0.0,
        bounce: float = 0.0,
        block_size: int = 1,
    ) -> List[Dict[str, int]]:
        """Draw an arc with transformations"""
        pixels = []
        cx, cy = self.apply_transform(cx, cy, tilt, bounce)

        # Adjust angles for tilt
        if tilt != 0:
            rad = math.radians(tilt)
            start_angle += rad
            end_angle += rad

        # Draw thicker blocks for better visibility
        thickness = max(thickness, block_size)
        step = max(1, int(thickness / 2))  # Smaller step for smoother arcs

        for angle in range(
            int(start_angle * 180 / math.pi), int(end_angle * 180 / math.pi), step
        ):
            rad = angle * math.pi / 180
            for r in range(int(radius - thickness), int(radius + thickness), step):
                bx = int(cx + r * math.cos(rad))
                by = int(cy + r * math.sin(rad))

                # Draw block
                for dy in range(block_size):
                    for dx in range(block_size):
                        px, py = bx + dx, by + dy
                        if 0 <= px < self.width and 0 <= py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
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
        size = params["size"]
        tilt = params["tilt"]
        bounce = params["bounce"]
        glow = params["glow"]

        self._time += 0.05 * animation_speed
        pixels = []

        # Calculate scaled radius
        base_radius = min(self.width, self.height) * 0.4
        radius = base_radius * size

        # Draw face with glow effect if enabled
        face_color = self.get_face_color(color_style, glow)
        if glow > 0:
            pixels.extend(
                self.draw_glow(
                    self._center_x, self._center_y, radius, face_color, glow * 0.5
                )
            )
        pixels.extend(
            self.draw_circle(
                self._center_x,
                self._center_y,
                radius,
                face_color,
                tilt,
                bounce,
                2,  # Use block size 2 for bolder appearance
            )
        )

        # Common positions
        eye_y = self._center_y - radius * 0.2
        left_eye_x = self._center_x - radius * 0.3
        right_eye_x = self._center_x + radius * 0.3
        mouth_y = self._center_y + radius * 0.2

        # Draw features based on expression
        if expression == "excited":
            # Sparkling eyes
            star_scale = math.sin(self._time * 5) * 0.3 + 0.7
            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                # Draw star-shaped eyes
                for i in range(8):
                    angle = i * math.pi / 4 + self._time * 2
                    x = eye_x + math.cos(angle) * 3 * star_scale
                    y = eye_y + math.sin(angle) * 3 * star_scale
                    pixels.extend(self.draw_circle(x, y, 1, (0, 0, 0), tilt, bounce, 1))

            # Wide bouncing smile
            smile_scale = math.sin(self._time * 3) * 0.2 + 1.2
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y,
                    radius * 0.4 * smile_scale,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "sad":
            # Droopy eyes
            tear_phase = (math.sin(self._time * 2) + 1) / 2
            for side in [-1, 1]:
                # Eye
                eye_x = self._center_x + side * radius * 0.3
                pixels.extend(
                    self.draw_arc(
                        eye_x,
                        eye_y,
                        3,
                        math.pi * 1.2,
                        math.pi * 1.8,
                        (0, 0, 0),
                        2,
                        tilt,
                        bounce,
                        2,
                    )
                )
                # Tear drop
                if side == -1:  # Only on one side
                    tear_y = eye_y + 4 + tear_phase * 4
                    pixels.extend(
                        self.draw_circle(
                            eye_x,
                            tear_y,
                            2,
                            (100, 149, 237),  # Cornflower blue
                            tilt,
                            bounce,
                            1,
                        )
                    )

            # Sad mouth
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y + radius * 0.1,
                    radius * 0.3,
                    math.pi * 1.2,
                    math.pi * 1.8,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "angry":
            # Angled eyebrows and sharp eyes
            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                # Angry eyebrow
                brow_angle = math.sin(self._time * 4) * 0.1
                pixels.extend(
                    self.draw_arc(
                        eye_x,
                        eye_y - 4,
                        4,
                        math.pi * (1.1 - side * 0.3 + brow_angle),
                        math.pi * (1.9 - side * 0.3 + brow_angle),
                        (0, 0, 0),
                        2,
                        tilt,
                        bounce,
                        2,
                    )
                )
                # Sharp eye
                pixels.extend(
                    self.draw_circle(eye_x, eye_y + 2, 2, (0, 0, 0), tilt, bounce, 2)
                )

            # Angry mouth
            mouth_phase = math.sin(self._time * 3) * 0.1
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y,
                    radius * 0.3,
                    math.pi * (1.2 + mouth_phase),
                    math.pi * (1.8 - mouth_phase),
                    (0, 0, 0),
                    3,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "happy":
            # Eyes with occasional blinks
            blink = math.sin(self._time * 0.5) > 0.95
            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                if not blink:
                    pixels.extend(
                        self.draw_circle(
                            eye_x, eye_y, radius * 0.1, (0, 0, 0), tilt, bounce, 2
                        )
                    )
                else:
                    pixels.extend(
                        self.draw_arc(
                            eye_x,
                            eye_y,
                            radius * 0.1,
                            math.pi * 0.2,
                            math.pi * 0.8,
                            (0, 0, 0),
                            2,
                            tilt,
                            bounce,
                            2,
                        )
                    )

            # Animated smile
            smile_phase = math.sin(self._time * 2) * 0.2 + 0.8
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y,
                    radius * 0.3 * smile_phase,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "wink":
            # Left eye
            pixels.extend(
                self.draw_circle(
                    self._center_x - radius * 0.3,
                    eye_y,
                    radius * 0.1,
                    (0, 0, 0),
                    tilt,
                    bounce,
                    2,
                )
            )

            # Right eye (winking)
            wink_phase = (math.sin(self._time * 4) + 1) / 2
            if wink_phase < 0.5:
                pixels.extend(
                    self.draw_circle(
                        self._center_x + radius * 0.3,
                        eye_y,
                        radius * 0.1,
                        (0, 0, 0),
                        tilt,
                        bounce,
                        2,
                    )
                )
            else:
                pixels.extend(
                    self.draw_arc(
                        self._center_x + radius * 0.3,
                        eye_y,
                        radius * 0.1,
                        math.pi * 0.2,
                        math.pi * 0.8,
                        (0, 0, 0),
                        2,
                        tilt,
                        bounce,
                        2,
                    )
                )

            # Smirk with slight movement
            smirk_offset = math.sin(self._time * 2) * radius * 0.05
            pixels.extend(
                self.draw_arc(
                    self._center_x + smirk_offset,
                    mouth_y,
                    radius * 0.3,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "love":
            # Heart eyes with pulsing effect
            heart_scale = math.sin(self._time * 3) * 0.2 + 0.8
            heart_color = (255, 0, 0)  # Red base
            if glow > 0:
                # Add glow to hearts
                pixels.extend(
                    self.draw_glow(
                        self._center_x - radius * 0.3,
                        eye_y,
                        radius * 0.15,
                        heart_color,
                        glow,
                    )
                )
                pixels.extend(
                    self.draw_glow(
                        self._center_x + radius * 0.3,
                        eye_y,
                        radius * 0.15,
                        heart_color,
                        glow,
                    )
                )

            for side in [-1, 1]:
                center_x = self._center_x + side * radius * 0.3
                # Draw heart shape
                pixels.extend(
                    self.draw_circle(
                        center_x - radius * 0.06,
                        eye_y,
                        radius * 0.08 * heart_scale,
                        heart_color,
                        tilt,
                        bounce,
                        2,
                    )
                )
                pixels.extend(
                    self.draw_circle(
                        center_x + radius * 0.06,
                        eye_y,
                        radius * 0.08 * heart_scale,
                        heart_color,
                        tilt,
                        bounce,
                        2,
                    )
                )
                pixels.extend(
                    self.draw_arc(
                        center_x,
                        eye_y + radius * 0.08,
                        radius * 0.08 * heart_scale,
                        math.pi * 0.8,
                        math.pi * 1.2,
                        heart_color,
                        2,
                        tilt,
                        bounce,
                        2,
                    )
                )

            # Big bouncing smile
            smile_bounce = math.sin(self._time * 2) * radius * 0.05
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y + smile_bounce,
                    radius * 0.4,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    3,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "surprised":
            # Wide eyes with occasional blinks
            eye_scale = math.sin(self._time * 4) * 0.3 + 1.2
            blink = math.sin(self._time * 0.7) > 0.95

            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                if not blink:
                    pixels.extend(
                        self.draw_circle(
                            eye_x,
                            eye_y,
                            radius * 0.12 * eye_scale,
                            (0, 0, 0),
                            tilt,
                            bounce,
                            2,
                        )
                    )
                    # Add highlight
                    pixels.extend(
                        self.draw_circle(
                            eye_x - 1, eye_y - 1, 1, (255, 255, 255), tilt, bounce, 1
                        )
                    )
                else:
                    pixels.extend(
                        self.draw_arc(
                            eye_x,
                            eye_y,
                            radius * 0.12,
                            math.pi * 0.2,
                            math.pi * 0.8,
                            (0, 0, 0),
                            2,
                            tilt,
                            bounce,
                            2,
                        )
                    )

            # O-shaped mouth with slight movement
            mouth_scale = math.sin(self._time * 3) * 0.2 + 1.0
            mouth_y_offset = math.sin(self._time * 2) * radius * 0.05
            pixels.extend(
                self.draw_circle(
                    self._center_x,
                    mouth_y + mouth_y_offset,
                    radius * 0.15 * mouth_scale,
                    (0, 0, 0),
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "sleepy":
            # Closed sleepy eyes with "z"s
            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                # Closed eye
                pixels.extend(
                    self.draw_arc(
                        eye_x,
                        eye_y,
                        3,
                        math.pi * 0.2,
                        math.pi * 0.8,
                        (0, 0, 0),
                        2,
                        tilt,
                        bounce,
                        2,
                    )
                )

                if side == 1:  # "Z"s on right side
                    z_phase = (self._time * 2) % 3
                    for i in range(3):
                        z_y = eye_y - 6 - i * 4 + z_phase * 2
                        if z_y > 0:  # Only show when in bounds
                            z_x = eye_x + i * 3
                            pixels.extend(
                                self.draw_circle(
                                    z_x, z_y, 1, (0, 0, 0), tilt, bounce, 1
                                )
                            )

            # Peaceful smile
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y,
                    radius * 0.25,
                    math.pi * 0.3,
                    math.pi * 0.7,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        elif expression == "party":
            # Celebratory eyes
            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                # Star-shaped eyes
                star_scale = math.sin(self._time * 4 + side) * 0.2 + 1.0
                for i in range(5):
                    angle = i * math.pi * 2 / 5 + self._time * 2
                    x = eye_x + math.cos(angle) * 3 * star_scale
                    y = eye_y + math.sin(angle) * 3 * star_scale
                    pixels.extend(
                        self.draw_circle(
                            x,
                            y,
                            1,
                            (255, 215, 0),  # Gold
                            tilt,
                            bounce,
                            1,
                        )
                    )

            # Party hat
            hat_y = self._center_y - radius * 0.6
            hat_height = radius * 0.4
            hat_width = radius * 0.3
            # Draw hat cone
            for i in range(int(hat_height)):
                progress = i / hat_height
                width = hat_width * (1 - progress)
                y = hat_y + i
                pixels.extend(
                    self.draw_arc(
                        self._center_x,
                        y,
                        width,
                        0,
                        math.pi * 2,
                        self.hsv_to_rgb((self._time + progress) % 1.0, 1.0, 1.0),
                        1,
                        tilt,
                        bounce,
                        1,
                    )
                )

            # Big grin
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    mouth_y,
                    radius * 0.4,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        else:  # cool
            # Sunglasses with reflection
            pixels.extend(
                self.draw_arc(
                    self._center_x,
                    eye_y,
                    radius * 0.4,
                    math.pi * 0.2,
                    math.pi * 0.8,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

            for side in [-1, 1]:
                eye_x = self._center_x + side * radius * 0.3
                # Lens
                pixels.extend(
                    self.draw_circle(
                        eye_x, eye_y, radius * 0.12, (0, 0, 0), tilt, bounce, 2
                    )
                )
                # Reflection
                reflection_phase = (self._time + (side * 0.5)) % (math.pi * 2)
                ref_x = eye_x + math.cos(reflection_phase) * 2
                ref_y = eye_y + math.sin(reflection_phase) * 2
                pixels.extend(
                    self.draw_circle(ref_x, ref_y, 1, (255, 255, 255), tilt, bounce, 1)
                )

            # Cool smile with slight movement
            smile_phase = math.sin(self._time) * 0.1 + 1.0
            smile_offset = math.sin(self._time * 1.5) * radius * 0.05
            pixels.extend(
                self.draw_arc(
                    self._center_x + smile_offset,
                    mouth_y,
                    radius * 0.3 * smile_phase,
                    math.pi * 0.1,
                    math.pi * 0.9,
                    (0, 0, 0),
                    2,
                    tilt,
                    bounce,
                    2,
                )
            )

        return pixels
