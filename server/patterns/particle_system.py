import random
import math
from typing import Dict, Any, List, Tuple
from .base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class ParticleSystem(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="particle_system",
            description="Dynamic particle system with physics",
            parameters=[
                Parameter(
                    name="num_particles",
                    type=int,
                    default=50,
                    min_value=1,
                    max_value=200,
                    description="Number of particles",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=5.0,
                    description="Particle movement speed",
                ),
                Parameter(
                    name="decay",
                    type=float,
                    default=0.98,
                    min_value=0.8,
                    max_value=0.999,
                    description="Particle lifetime decay rate",
                ),
                Parameter(
                    name="spread",
                    type=float,
                    default=0.5,
                    min_value=0.1,
                    max_value=2.0,
                    description="Particle spread factor",
                ),
            ],
            category="animations",
            tags=["particles", "physics", "dynamic"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self.particles = []  # List of (x, y, dx, dy, lifetime)
        self.hue = 0  # For color cycling

    def create_particle(
        self, speed: float, spread: float
    ) -> Tuple[float, float, float, float, float]:
        """Create a new particle with random velocity"""
        # Start from center
        x = self.width / 2
        y = self.height / 2

        # Random angle and speed
        angle = random.uniform(0, 2 * math.pi)
        velocity = random.uniform(0.5, 1.5) * speed

        # Calculate velocity components
        dx = math.cos(angle) * velocity * spread
        dy = math.sin(angle) * velocity * spread

        return (x, y, dx, dy, 1.0)  # Full lifetime

    def update_particle(
        self,
        particle: Tuple[float, float, float, float, float],
        speed: float,
        decay: float,
    ) -> Tuple[float, float, float, float, float]:
        """Update particle position and lifetime"""
        x, y, dx, dy, lifetime = particle

        # Update position
        x += dx * speed
        y += dy * speed

        # Add some randomness to movement
        dx += random.uniform(-0.1, 0.1)
        dy += random.uniform(-0.1, 0.1)

        # Decay lifetime
        lifetime *= decay

        return (x, y, dx, dy, lifetime)

    def wheel(self, pos: int) -> tuple[int, int, int]:
        """Generate rainbow colors across 0-255 positions."""
        pos = pos % 255
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        params = self.validate_params(params)
        num_particles = params["num_particles"]
        speed = params["speed"]
        decay = params["decay"]
        spread = params["spread"]

        # Create new particles if needed
        while len(self.particles) < num_particles:
            self.particles.append(self.create_particle(speed, spread))

        # Update existing particles
        new_particles = []
        for particle in self.particles:
            x, y, dx, dy, lifetime = self.update_particle(particle, speed, decay)

            # Keep particle if still alive and in bounds
            if lifetime > 0.1 and 0 <= x < self.width and 0 <= y < self.height:
                new_particles.append((x, y, dx, dy, lifetime))

        self.particles = new_particles

        # Generate frame
        pixels = []
        self.hue = (self.hue + 1) % 255  # Cycle colors

        for x, y, _, _, lifetime in self.particles:
            if 0 <= int(x) < self.width and 0 <= int(y) < self.height:
                r, g, b = self.wheel(self.hue)
                intensity = lifetime
                pixels.append(
                    {
                        "index": self.grid_config.xy_to_index(int(x), int(y)),
                        "r": int(r * intensity),
                        "g": int(g * intensity),
                        "b": int(b * intensity),
                    }
                )

        return pixels
