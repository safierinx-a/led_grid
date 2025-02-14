import random
import numpy as np
import math
from typing import Dict, Any, List
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class Fire(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="fire",
            description="Enhanced fire effects optimized for 24x25 LED grid with bold variations",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="inferno",
                    description="Fire variation (inferno, phoenix, ember, torch, wildfire)",
                ),
                Parameter(
                    name="intensity",
                    type=float,
                    default=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    description="Overall fire intensity",
                ),
                Parameter(
                    name="cooling",
                    type=float,
                    default=0.7,
                    min_value=0.1,
                    max_value=2.0,
                    description="Fire cooling rate",
                ),
                Parameter(
                    name="sparking",
                    type=float,
                    default=0.95,
                    min_value=0.5,
                    max_value=1.0,
                    description="Spark generation probability",
                ),
                Parameter(
                    name="wind",
                    type=float,
                    default=0.0,
                    min_value=-1.0,
                    max_value=1.0,
                    description="Wind effect (-1 left, 1 right)",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="classic",
                    description="Color palette (classic, neon, purple, blue, green)",
                ),
                Parameter(
                    name="block_size",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=3,
                    description="Size of fire blocks (1-3 pixels)",
                ),
                Parameter(
                    name="turbulence",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Amount of flame distortion",
                ),
            ],
            category="animations",
            tags=["fire", "particles", "natural"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        # Create heat map with extra bottom row for spark generation
        self.heat = np.zeros((self.height + 1, self.width), dtype=float)
        self._step = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._sources = []  # For wildfire variation

    def _get_classic_color(
        self, temperature: float, intensity: float
    ) -> tuple[int, int, int]:
        """Classic fire colors: black -> red -> yellow -> white"""
        temp = min(1.0, temperature * intensity)
        if temp < 0.2:
            return (0, 0, 0)
        elif temp < 0.4:
            t = (temp - 0.2) * 5
            return (int(255 * t), 0, 0)
        elif temp < 0.6:
            t = (temp - 0.4) * 5
            return (255, int(255 * t), 0)
        else:
            t = (temp - 0.6) * 2.5
            return (255, 255, int(255 * t))

    def _get_neon_color(
        self, temperature: float, intensity: float
    ) -> tuple[int, int, int]:
        """Neon fire colors: purple -> pink -> white"""
        temp = min(1.0, temperature * intensity)
        if temp < 0.2:
            return (0, 0, 0)
        elif temp < 0.4:
            t = (temp - 0.2) * 5
            return (int(255 * t), 0, int(128 * t))
        elif temp < 0.6:
            t = (temp - 0.4) * 5
            return (255, int(128 * t), 255)
        else:
            t = (temp - 0.6) * 2.5
            return (255, int(255 * t), 255)

    def _get_purple_color(
        self, temperature: float, intensity: float
    ) -> tuple[int, int, int]:
        """Purple fire colors: dark purple -> bright purple -> white"""
        temp = min(1.0, temperature * intensity)
        if temp < 0.2:
            return (0, 0, 0)
        elif temp < 0.5:
            t = (temp - 0.2) * 3.33
            return (int(128 * t), 0, int(255 * t))
        else:
            t = (temp - 0.5) * 2
            return (int(128 + 127 * t), int(255 * t), 255)

    def _get_blue_color(
        self, temperature: float, intensity: float
    ) -> tuple[int, int, int]:
        """Blue fire colors: dark blue -> bright blue -> white"""
        temp = min(1.0, temperature * intensity)
        if temp < 0.2:
            return (0, 0, 0)
        elif temp < 0.5:
            t = (temp - 0.2) * 3.33
            return (0, int(128 * t), int(255 * t))
        else:
            t = (temp - 0.5) * 2
            return (int(255 * t), int(128 + 127 * t), 255)

    def _get_green_color(
        self, temperature: float, intensity: float
    ) -> tuple[int, int, int]:
        """Green fire colors: dark green -> bright green -> white"""
        temp = min(1.0, temperature * intensity)
        if temp < 0.2:
            return (0, 0, 0)
        elif temp < 0.5:
            t = (temp - 0.2) * 3.33
            return (0, int(255 * t), 0)
        else:
            t = (temp - 0.5) * 2
            return (int(255 * t), 255, int(255 * t))

    def get_fire_color(
        self, temperature: float, color_mode: str, intensity: float
    ) -> tuple[int, int, int]:
        """Get fire color based on temperature and color mode"""
        if color_mode == "neon":
            return self._get_neon_color(temperature, intensity)
        elif color_mode == "purple":
            return self._get_purple_color(temperature, intensity)
        elif color_mode == "blue":
            return self._get_blue_color(temperature, intensity)
        elif color_mode == "green":
            return self._get_green_color(temperature, intensity)
        else:  # classic
            return self._get_classic_color(temperature, intensity)

    def _apply_turbulence(self, x: int, y: int, turbulence: float) -> tuple[int, int]:
        """Apply turbulence to coordinates"""
        angle = (self._step * 0.1 + (x + y) * 0.2) * turbulence
        dx = int(math.sin(angle) * 2 * turbulence)
        dy = int(math.cos(angle) * 2 * turbulence)
        return ((x + dx) % self.width, max(0, min(self.height, y + dy)))

    def _generate_inferno(self, params: Dict[str, Any]) -> None:
        """Classic inferno with enhanced intensity"""
        cooling = params["cooling"]
        sparking = params["sparking"]
        wind = params["wind"]
        turbulence = params["turbulence"]

        # Cool down every cell with variable rate
        cooling_map = np.random.uniform(0.8, 1.2, self.heat.shape) * cooling
        self.heat = self.heat * (1 - cooling_map * 0.02)

        # Generate intense sparks at the bottom
        for x in range(self.width):
            if random.random() < sparking:
                self.heat[-1, x] = random.uniform(0.95, 1.0)

        # Move heat upwards with turbulence
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                # Apply wind and turbulence
                wind_offset = int(wind * 2 * (1 - y / self.height))
                src_x, src_y = self._apply_turbulence(
                    (x - wind_offset) % self.width, y, turbulence
                )

                # Enhanced heat diffusion
                total = 0
                count = 0
                for dy in range(4):  # Look at 4 cells below
                    for dx in [-1, 0, 1]:  # And adjacent cells
                        ny = src_y + dy
                        nx = (src_x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            total += self.heat[ny, nx]
                            count += 1

                if count > 0:
                    new_heat[y, x] = total / count * 1.1  # Increased intensity

        self.heat = new_heat

    def _generate_phoenix(self, params: Dict[str, Any]) -> None:
        """Colorful fire with rising patterns"""
        cooling = params["cooling"]
        sparking = params["sparking"]
        turbulence = params["turbulence"]

        # Gentle cooling
        self.heat = self.heat * (1 - cooling * 0.015)

        # Generate sparks in patterns
        phase = self._step * 0.1
        for x in range(self.width):
            if random.random() < sparking:
                intensity = 0.8 + 0.2 * math.sin(x * 0.5 + phase)
                self.heat[-1, x] = random.uniform(0.8, 1.0) * intensity

        # Move heat with swirling effect
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                # Create swirling motion
                angle = (y / self.height) * math.pi * 2 + phase
                dx = int(math.sin(angle) * 2 * turbulence)
                src_x = (x + dx) % self.width

                # Gather heat from below with wider spread
                total = 0
                count = 0
                for dy in range(3):
                    spread = int(1 + dy * turbulence)
                    for dx in range(-spread, spread + 1):
                        ny = y + dy
                        nx = (src_x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            total += self.heat[ny, nx]
                            count += 1

                if count > 0:
                    new_heat[y, x] = total / count

        self.heat = new_heat

    def _generate_ember(self, params: Dict[str, Any]) -> None:
        """Glowing ember effect with pulsing"""
        cooling = params["cooling"]
        sparking = params["sparking"]
        turbulence = params["turbulence"]

        # Slower cooling for ember effect
        self.heat = self.heat * (1 - cooling * 0.01)

        # Generate random hot spots
        for _ in range(int(sparking * 10)):
            x = random.randint(0, self.width - 1)
            y = random.randint(self.height - 3, self.height - 1)
            self.heat[y, x] = random.uniform(0.7, 1.0)

        # Add pulsing effect
        pulse = 0.1 * math.sin(self._step * 0.1)
        self.heat = np.clip(self.heat + pulse, 0, 1)

        # Smooth heat distribution
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                total = 0
                count = 0
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        ny = y + dy
                        nx = (x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            total += self.heat[ny, nx]
                            count += 1

                if count > 0:
                    new_heat[y, x] = total / count

        self.heat = new_heat

    def _generate_torch(self, params: Dict[str, Any]) -> None:
        """Focused torch flame effect"""
        cooling = params["cooling"]
        sparking = params["sparking"]
        wind = params["wind"]
        turbulence = params["turbulence"]

        # Apply cooling with focus on center
        for x in range(self.width):
            distance = abs(x - self._center_x)
            cooling_factor = cooling * (1 + distance / self._center_x)
            self.heat[:, x] *= 1 - cooling_factor * 0.02

        # Generate sparks at bottom center
        center_range = int(self.width * 0.3)
        start_x = int(self._center_x - center_range // 2)
        for x in range(start_x, start_x + center_range):
            if random.random() < sparking:
                self.heat[-1, x] = random.uniform(0.9, 1.0)

        # Move heat upwards with focused spread
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                # Calculate spread based on height
                spread = int(1 + (y / self.height) * 2)

                # Apply wind and turbulence
                wind_offset = int(wind * 2 * (1 - y / self.height))
                src_x, src_y = self._apply_turbulence(
                    (x - wind_offset) % self.width, y, turbulence
                )

                # Gather heat with focused spread
                total = 0
                count = 0
                for dy in range(3):
                    for dx in range(-spread, spread + 1):
                        ny = src_y + dy
                        nx = (src_x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            dist_factor = 1 - abs(dx) / (spread + 1)
                            total += self.heat[ny, nx] * dist_factor
                            count += dist_factor

                if count > 0:
                    new_heat[y, x] = total / count

        self.heat = new_heat

    def _generate_wildfire(self, params: Dict[str, Any]) -> None:
        """Chaotic wildfire with multiple sources"""
        cooling = params["cooling"]
        sparking = params["sparking"]
        turbulence = params["turbulence"]

        # Update existing fire sources
        new_sources = []
        for x, y, intensity in self._sources:
            if intensity > 0.2:
                new_sources.append((x, y, intensity * 0.99))

        # Add new sources
        if random.random() < sparking and len(new_sources) < 5:
            x = random.randint(0, self.width - 1)
            y = random.randint(self.height - 3, self.height - 1)
            new_sources.append((x, y, 1.0))

        self._sources = new_sources

        # Apply cooling with random variations
        cooling_map = np.random.uniform(0.8, 1.2, self.heat.shape) * cooling
        self.heat = self.heat * (1 - cooling_map * 0.02)

        # Update heat from sources
        for x, y, intensity in self._sources:
            radius = int(4 * intensity)
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    ny = y + dy
                    nx = (x + dx) % self.width
                    if 0 <= ny < self.heat.shape[0]:
                        dist = math.sqrt(dx * dx + dy * dy)
                        if dist <= radius:
                            heat_val = intensity * (1 - dist / radius)
                            self.heat[ny, nx] = max(self.heat[ny, nx], heat_val)

        # Apply turbulent diffusion
        new_heat = np.zeros_like(self.heat)
        for y in range(self.height):
            for x in range(self.width):
                src_x, src_y = self._apply_turbulence(x, y, turbulence)

                total = 0
                count = 0
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        ny = src_y + dy
                        nx = (src_x + dx) % self.width
                        if 0 <= ny < self.heat.shape[0]:
                            total += self.heat[ny, nx]
                            count += 1

                if count > 0:
                    new_heat[y, x] = total / count

        self.heat = new_heat

    def _draw_block(
        self, x: int, y: int, size: int, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw a block of pixels with the given color"""
        pixels = []
        for dy in range(size):
            for dx in range(size):
                px, py = x + dx, y + dy
                if px < self.width and py < self.height:
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
        """Generate a frame of the fire pattern"""
        params = self.validate_params(params)
        variation = params["variation"]

        # Generate pattern based on variation
        pattern_pixels = []
        if variation == "classic":
            pattern_pixels = self._generate_classic(params)
        elif variation == "plasma":
            pattern_pixels = self._generate_plasma(params)
        elif variation == "ember":
            pattern_pixels = self._generate_ember(params)
        elif variation == "inferno":
            pattern_pixels = self._generate_inferno(params)
        else:  # spark
            pattern_pixels = self._generate_spark(params)

        self._step += 1
        return self._ensure_all_pixels_handled(pattern_pixels)
