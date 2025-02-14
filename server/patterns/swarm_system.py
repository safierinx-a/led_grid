import random
import math
import numpy as np
from typing import Dict, Any, List, Tuple
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry


@PatternRegistry.register
class SwarmSystem(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="swarm_system",
            description="Bold swarm behavior patterns optimized for 24x25 LED grid with dynamic interactions",
            parameters=[
                Parameter(
                    name="variation",
                    type=str,
                    default="flock",
                    description="Pattern variation (flock, predator, school, spiral, scatter, orbit)",
                ),
                Parameter(
                    name="num_agents",
                    type=int,
                    default=20,
                    min_value=5,
                    max_value=50,
                    description="Number of swarm agents",
                ),
                Parameter(
                    name="speed",
                    type=float,
                    default=1.0,
                    min_value=0.1,
                    max_value=3.0,
                    description="Movement speed",
                ),
                Parameter(
                    name="cohesion",
                    type=float,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Group cohesion strength",
                ),
                Parameter(
                    name="color_mode",
                    type=str,
                    default="energy",
                    description="Color mode (energy, flow, trail, pulse, group)",
                ),
                Parameter(
                    name="trail_length",
                    type=int,
                    default=4,
                    min_value=0,
                    max_value=8,
                    description="Length of agent trails",
                ),
                Parameter(
                    name="size",
                    type=int,
                    default=2,
                    min_value=1,
                    max_value=3,
                    description="Agent size (1-3 pixels)",
                ),
            ],
            category="animations",
            tags=["swarm", "particles", "dynamic", "interactive"],
        )

    def __init__(self, grid_config):
        super().__init__(grid_config)
        self._time = 0
        self._center_x = self.width / 2
        self._center_y = self.height / 2
        self.agents = []  # List of {pos: (x,y), vel: (dx,dy), energy: float, group: int}
        self.trails = []  # List of {pos: (x,y), age: float, color: (r,g,b)}
        self._predator_pos = None  # For predator behavior
        self._attractor_points = []  # For orbit behavior
        self._color_buffer = {}  # For trail blending

    def _init_agents(self, num_agents: int, variation: str):
        """Initialize swarm agents based on variation type"""
        self.agents = []

        if variation == "flock":
            # Create clustered groups
            num_groups = 3
            for i in range(num_agents):
                group = i % num_groups
                center_x = self._center_x + random.uniform(-5, 5)
                center_y = self._center_y + random.uniform(-5, 5)
                self.agents.append(
                    {
                        "pos": (center_x, center_y),
                        "vel": (random.uniform(-1, 1), random.uniform(-1, 1)),
                        "energy": 1.0,
                        "group": group,
                    }
                )

        elif variation == "predator":
            # Initialize prey agents away from predator
            self._predator_pos = (
                random.uniform(0, self.width),
                random.uniform(0, self.height),
            )
            for _ in range(num_agents):
                x = random.uniform(0, self.width)
                y = random.uniform(0, self.height)
                # Ensure minimum distance from predator
                while (
                    math.sqrt(
                        (x - self._predator_pos[0]) ** 2
                        + (y - self._predator_pos[1]) ** 2
                    )
                    < 10
                ):
                    x = random.uniform(0, self.width)
                    y = random.uniform(0, self.height)
                self.agents.append(
                    {
                        "pos": (x, y),
                        "vel": (random.uniform(-1, 1), random.uniform(-1, 1)),
                        "energy": 1.0,
                        "group": 0,
                    }
                )

        elif variation == "school":
            # Create a tight school formation
            for i in range(num_agents):
                angle = random.uniform(0, math.pi * 2)
                radius = random.uniform(0, 5)
                x = self._center_x + math.cos(angle) * radius
                y = self._center_y + math.sin(angle) * radius
                self.agents.append(
                    {
                        "pos": (x, y),
                        "vel": (math.cos(angle), math.sin(angle)),
                        "energy": 1.0,
                        "group": 0,
                    }
                )

        elif variation == "spiral":
            # Arrange in spiral pattern
            for i in range(num_agents):
                angle = (i / num_agents) * math.pi * 4
                radius = (i / num_agents) * min(self.width, self.height) * 0.3
                x = self._center_x + math.cos(angle) * radius
                y = self._center_y + math.sin(angle) * radius
                self.agents.append(
                    {
                        "pos": (x, y),
                        "vel": (-math.sin(angle), math.cos(angle)),
                        "energy": 1.0,
                        "group": i % 3,
                    }
                )

        elif variation == "scatter":
            # Start from center and scatter outward
            for _ in range(num_agents):
                angle = random.uniform(0, math.pi * 2)
                self.agents.append(
                    {
                        "pos": (self._center_x, self._center_y),
                        "vel": (math.cos(angle), math.sin(angle)),
                        "energy": 1.0,
                        "group": random.randint(0, 2),
                    }
                )

        else:  # orbit
            # Create orbital points and agents
            num_orbits = 3
            self._attractor_points = []
            for i in range(num_orbits):
                angle = (i / num_orbits) * math.pi * 2
                radius = min(self.width, self.height) * 0.2
                self._attractor_points.append(
                    (
                        self._center_x + math.cos(angle) * radius,
                        self._center_y + math.sin(angle) * radius,
                    )
                )

            for i in range(num_agents):
                orbit = i % num_orbits
                center = self._attractor_points[orbit]
                angle = random.uniform(0, math.pi * 2)
                radius = random.uniform(2, 4)
                x = center[0] + math.cos(angle) * radius
                y = center[1] + math.sin(angle) * radius
                self.agents.append(
                    {
                        "pos": (x, y),
                        "vel": (-math.sin(angle), math.cos(angle)),
                        "energy": 1.0,
                        "group": orbit,
                    }
                )

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple[int, int, int]:
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

    def _get_agent_color(
        self, agent: Dict[str, Any], color_mode: str
    ) -> tuple[int, int, int]:
        """Get agent color based on mode and state"""
        if color_mode == "energy":
            # Color based on agent's energy level
            if agent["energy"] > 0.8:
                # High energy: white to yellow
                v = (agent["energy"] - 0.8) * 5
                return (255, 255, int(255 * (1 - v)))
            else:
                # Lower energy: blue to white
                v = agent["energy"] * 1.25
                return (int(v * 255), int(v * 255), 255)

        elif color_mode == "flow":
            # Color based on movement direction
            angle = math.atan2(agent["vel"][1], agent["vel"][0]) / (2 * math.pi) + 0.5
            return self._hsv_to_rgb(angle, 1.0, agent["energy"])

        elif color_mode == "trail":
            # Color based on position and time
            x, y = agent["pos"]
            hue = (x / self.width + y / self.height + self._time * 0.1) % 1.0
            return self._hsv_to_rgb(hue, 0.8, agent["energy"])

        elif color_mode == "pulse":
            # Pulsing color effect
            base_hue = agent["group"] / 3
            pulse = math.sin(self._time * 3 + agent["group"] * math.pi / 2) * 0.3 + 0.7
            return self._hsv_to_rgb(base_hue, 1.0, pulse * agent["energy"])

        else:  # group
            # Distinct color per group with energy variation
            base_hue = agent["group"] / 3
            return self._hsv_to_rgb(base_hue, 1.0, agent["energy"])

    def _draw_agent(
        self, x: float, y: float, size: int, color: tuple[int, int, int]
    ) -> List[Dict[str, int]]:
        """Draw an agent with optional trail blending"""
        pixels = []
        for dy in range(size):
            for dx in range(size):
                px, py = int(x) + dx, int(y) + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    if (px, py) in self._color_buffer:
                        # Blend with existing color
                        old_color = self._color_buffer[(px, py)]
                        new_color = tuple(
                            min(255, max(0, int(old * 0.7 + new * 0.3)))
                            for old, new in zip(old_color, color)
                        )
                    else:
                        new_color = color

                    self._color_buffer[(px, py)] = new_color
                    pixels.append(
                        {
                            "index": self.grid_config.xy_to_index(px, py),
                            "r": new_color[0],
                            "g": new_color[1],
                            "b": new_color[2],
                        }
                    )
        return pixels

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a frame of the swarm pattern"""
        # Validate parameters
        params = self.validate_params(params)
        variation = params["variation"]
        num_agents = params["num_agents"]
        speed = params["speed"]
        color_mode = params["color_mode"]
        trail_length = params.get("trail_length", 0)

        # Create new particles if needed
        while len(self.particles) < num_agents:
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
