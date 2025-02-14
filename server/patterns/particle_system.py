import random
import math
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ParticleSystem(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="particle_system",
            description="Bold particle system optimized for 24x25 LED grid with meaningful interactions",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="bold",
                    description="Particle variation (bold, grid, edge, constellation, quad)",
                ),
                Parameter(
                    name="num_particles",
                    type=int,
                    default=20,
                    min_value=5,
                    max_value=50,
                    description="Number of particles",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Particle movement speed",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="rainbow",
                    description="Color mode (rainbow, mono, heat, cool)",
                ),
                Parameter(
                    name="size",
                    type=int,
                    default=2,
                    min_value=2,
                    max_value=3,
                    description="Particle size (2-3 pixels)",
                ),
                Parameter(
                    name="trail_length",
                    type=int,
                    default=3,
                    min_value=0,
                    max_value=5,
                    description="Length of particle trails",
                ),
            ],
            category="animations",
            tags=["particles", "physics", "dynamic"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.particles = []  # List of (x, y, dx, dy, lifetime, size, trail)
        self.trails = []  # List of (x, y, lifetime, size) for trails
        self._step = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self._grid_points = self._create_grid_points()

    def _create_grid_points(self) -> List[Tuple[int, int]]:
        """Create grid intersection points for grid-based variations"""
        points = []
        for y in range(0, self.height, 4):  # Grid every 4 pixels
            for x in range(0, self.width, 4):
                points.append((x, y))
        return points

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
        """Convert HSV to RGB"""
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

    def _get_color(self, lifetime: float, color_mode: str) -> tuple[int, int, int]:
        """Get color based on lifetime and color mode"""
        if color_mode == "rainbow":
            hue = (self._step * 0.01 + lifetime) % 1.0
            return self._hsv_to_rgb(hue, 1.0, lifetime)
        elif color_mode == "mono":
            val = int(lifetime * 255)
            return (val, val, val)
        elif color_mode == "heat":
            # Red to yellow gradient
            r = int(255 * lifetime)
            g = int(255 * lifetime * 0.7)
            return (r, g, 0)
        else:  # cool
            # Blue to cyan gradient
            b = int(255 * lifetime)
            g = int(255 * lifetime * 0.7)
            return (0, g, b)

    def _create_bold_particle(self, speed: float) -> tuple:
        """Create large particle with trail for bold variation"""
        x = random.uniform(0, self.width)
        y = random.uniform(0, self.height)
        angle = random.uniform(0, 2 * math.pi)
        velocity = random.uniform(0.5, 1.5) * speed
        dx = math.cos(angle) * velocity
        dy = math.sin(angle) * velocity
        size = random.randint(2, 3)
        trail = []  # Store trail positions
        return (x, y, dx, dy, 1.0, size, trail)

    def _create_grid_particle(self, speed: float) -> tuple:
        """Create particle that moves between grid points"""
        start_point = random.choice(self._grid_points)
        target_point = random.choice(self._grid_points)
        dx = (target_point[0] - start_point[0]) * speed * 0.1
        dy = (target_point[1] - start_point[1]) * speed * 0.1
        return (start_point[0], start_point[1], dx, dy, 1.0, 2, [])

    def _create_edge_particle(self, speed: float) -> tuple:
        """Create particle that interacts with boundaries"""
        # Start from edge
        if random.random() < 0.5:
            x = random.choice([0, self.width - 1])
            y = random.uniform(0, self.height)
            dx = (1 if x == 0 else -1) * speed
            dy = random.uniform(-speed, speed)
        else:
            x = random.uniform(0, self.width)
            y = random.choice([0, self.height - 1])
            dx = random.uniform(-speed, speed)
            dy = (1 if y == 0 else -1) * speed
        return (x, y, dx, dy, 1.0, 2, [])

    def _create_constellation_particle(self, speed: float) -> tuple:
        """Create particle for constellation patterns"""
        x = random.uniform(0, self.width)
        y = random.uniform(0, self.height)
        # Slower movement for more stable constellations
        dx = random.uniform(-0.5, 0.5) * speed
        dy = random.uniform(-0.5, 0.5) * speed
        return (x, y, dx, dy, 1.0, 2, [])

    def _create_quad_particle(self, speed: float) -> tuple:
        """Create particle for quad space variation"""
        # Determine quadrant
        quad_x = random.randint(0, 1)
        quad_y = random.randint(0, 1)
        x = random.uniform(quad_x * self.width / 2, (quad_x + 1) * self.width / 2)
        y = random.uniform(quad_y * self.height / 2, (quad_y + 1) * self.height / 2)
        dx = random.uniform(-1, 1) * speed
        dy = random.uniform(-1, 1) * speed
        return (x, y, dx, dy, 1.0, 2, [])

    def _update_bold_particle(
        self, particle: tuple, speed: float, trail_length: int
    ) -> tuple:
        """Update bold particle with trail"""
        x, y, dx, dy, lifetime, size, trail = particle
        # Update trail
        trail.append((x, y))
        if len(trail) > trail_length:
            trail = trail[-trail_length:]
        # Add slight random movement
        dx += random.uniform(-0.1, 0.1) * speed
        dy += random.uniform(-0.1, 0.1) * speed
        # Bounce off edges
        new_x = x + dx
        new_y = y + dy
        if new_x < 0 or new_x > self.width - size:
            dx = -dx
        if new_y < 0 or new_y > self.height - size:
            dy = -dy
        return (x + dx, y + dy, dx, dy, lifetime * 0.99, size, trail)

    def _update_grid_particle(self, particle: tuple, speed: float) -> tuple:
        """Update particle moving between grid points"""
        x, y, dx, dy, lifetime, size, trail = particle
        # Check if close to any grid point
        for point in self._grid_points:
            dist = math.sqrt((x - point[0]) ** 2 + (y - point[1]) ** 2)
            if dist < 1.0:
                # Choose new target
                target = random.choice(self._grid_points)
                dx = (target[0] - x) * speed * 0.1
                dy = (target[1] - y) * speed * 0.1
                break
        return (x + dx, y + dy, dx, dy, lifetime * 0.99, size, trail)

    def _update_edge_particle(self, particle: tuple, speed: float) -> tuple:
        """Update particle with edge interactions"""
        x, y, dx, dy, lifetime, size, trail = particle
        # Bounce off edges with new random velocity
        new_x = x + dx
        new_y = y + dy
        if new_x < 0 or new_x > self.width - size:
            dx = -dx * random.uniform(0.8, 1.2)
            dy = random.uniform(-speed, speed)
        if new_y < 0 or new_y > self.height - size:
            dy = -dy * random.uniform(0.8, 1.2)
            dx = random.uniform(-speed, speed)
        return (x + dx, y + dy, dx, dy, lifetime * 0.99, size, trail)

    def _update_constellation_particle(self, particle: tuple, speed: float) -> tuple:
        """Update particle for constellation patterns"""
        x, y, dx, dy, lifetime, size, trail = particle
        # Find nearby particles to form constellations
        for other in self.particles:
            if other != particle:
                ox, oy = other[0], other[1]
                dist = math.sqrt((x - ox) ** 2 + (y - oy) ** 2)
                if dist < 6:  # Connection distance
                    # Add slight attraction
                    dx += (ox - x) * 0.01 * speed
                    dy += (oy - y) * 0.01 * speed
        # Add slight random movement
        dx += random.uniform(-0.05, 0.05) * speed
        dy += random.uniform(-0.05, 0.05) * speed
        # Normalize velocity
        mag = math.sqrt(dx * dx + dy * dy)
        if mag > speed:
            dx = dx / mag * speed
            dy = dy / mag * speed
        return (x + dx, y + dy, dx, dy, lifetime * 0.99, size, trail)

    def _update_quad_particle(self, particle: tuple, speed: float) -> tuple:
        """Update particle in quad space"""
        x, y, dx, dy, lifetime, size, trail = particle
        # Determine current quadrant
        quad_x = int(x / (self.width / 2))
        quad_y = int(y / (self.height / 2))
        # Keep particle in its quadrant
        new_x = x + dx
        new_y = y + dy
        if new_x < quad_x * self.width / 2 or new_x > (quad_x + 1) * self.width / 2:
            dx = -dx
        if new_y < quad_y * self.height / 2 or new_y > (quad_y + 1) * self.height / 2:
            dy = -dy
        return (x + dx, y + dy, dx, dy, lifetime * 0.99, size, trail)

    def _draw_particle(
        self, x: float, y: float, size: int, color: tuple, trail: list = None
    ) -> List[Dict[str, int]]:
        """Draw a particle with optional trail"""
        pixels = []

        # Draw trails first (dimmer)
        if trail:
            for i, (tx, ty) in enumerate(trail):
                fade = (i + 1) / len(trail)  # Fade trail based on position
                trail_color = tuple(int(c * fade * 0.5) for c in color)  # 50% dimmer
                for dx in range(size):
                    for dy in range(size):
                        px, py = int(tx + dx), int(ty + dy)
                        if 0 <= px < self.width and 0 <= py < self.height:
                            pixels.append(
                                {
                                    "index": self.grid_config.xy_to_index(px, py),
                                    "r": trail_color[0],
                                    "g": trail_color[1],
                                    "b": trail_color[2],
                                }
                            )

        # Draw main particle
        for dx in range(size):
            for dy in range(size):
                px, py = int(x + dx), int(y + dy)
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
        """Generate a frame of the particle system"""
        # Validate parameters
        params = self.validate_params(params)
        variation = params["variation"]
        num_particles = params["num_particles"]
        speed = params["speed"]
        color_mode = params["color_mode"]
        trail_length = params.get("trail_length", 0)

        # Create new particles if needed
        while len(self.particles) < num_particles:
            if variation == "grid":
                self.particles.append(self._create_grid_particle(speed))
            elif variation == "edge":
                self.particles.append(self._create_edge_particle(speed))
            elif variation == "constellation":
                self.particles.append(self._create_constellation_particle(speed))
            elif variation == "quad":
                self.particles.append(self._create_quad_particle(speed))
            else:  # bold
                self.particles.append(self._create_bold_particle(speed))

        # Update particles
        new_particles = []
        pixels = []

        # Draw constellation connections first
        if variation == "constellation":
            for i, p1 in enumerate(self.particles):
                for p2 in self.particles[i + 1 :]:
                    dist = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
                    if dist < 6:  # Connection distance
                        # Draw connection line
                        steps = int(dist * 2)
                        for t in range(steps):
                            progress = t / steps
                            x = p1[0] + (p2[0] - p1[0]) * progress
                            y = p1[1] + (p2[1] - p1[1]) * progress
                            connection_color = self._get_color(
                                0.3, color_mode
                            )  # Dimmer connections
                            pixels.extend(
                                self._draw_particle(x, y, 1, connection_color)
                            )

        # Update and draw particles
        for particle in self.particles:
            if particle[4] > 0.1:  # Check lifetime
                if variation == "grid":
                    new_particle = self._update_grid_particle(particle, speed)
                elif variation == "edge":
                    new_particle = self._update_edge_particle(particle, speed)
                elif variation == "constellation":
                    new_particle = self._update_constellation_particle(particle, speed)
                elif variation == "quad":
                    new_particle = self._update_quad_particle(particle, speed)
                else:  # bold
                    new_particle = self._update_bold_particle(
                        particle, speed, trail_length
                    )

                new_particles.append(new_particle)
                color = self._get_color(new_particle[4], color_mode)
                pixels.extend(
                    self._draw_particle(
                        new_particle[0],
                        new_particle[1],
                        new_particle[5],
                        color,
                        new_particle[6] if variation == "bold" else None,
                    )
                )

        self.particles = new_particles
        self._step += 1

        return self._ensure_all_pixels_handled(pixels)
