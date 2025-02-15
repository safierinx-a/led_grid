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
        cohesion = params["cohesion"]

        # Clear color buffer at start of frame
        self._color_buffer.clear()

        # Initialize agents if needed
        if len(self.agents) < num_agents:
            self._init_agents(num_agents, variation)
        elif len(self.agents) > num_agents:
            # Remove excess agents if number was reduced
            self.agents = self.agents[:num_agents]

        # Update agents
        pixels = []
        new_agents = []

        # Update predator position for predator variation
        if variation == "predator":
            if self._predator_pos is None:
                self._predator_pos = (self._center_x, self._center_y)
            angle = self._time * speed * 0.1
            radius = 5 * math.sin(self._time * 0.05) + 7
            self._predator_pos = (
                self._center_x + math.cos(angle) * radius,
                self._center_y + math.sin(angle) * radius,
            )

        # Update attractor points for orbit variation
        if variation == "orbit" and not self._attractor_points:
            num_attractors = 3
            for i in range(num_attractors):
                angle = (i / num_attractors) * 2 * math.pi
                radius = 8
                self._attractor_points.append(
                    (
                        self._center_x + math.cos(angle) * radius,
                        self._center_y + math.sin(angle) * radius,
                    )
                )

        # Limit trail length based on number of agents to prevent memory issues
        max_trail_length = min(trail_length, max(1, 50 // num_agents))

        # Update and draw agents
        for agent in self.agents:
            # Calculate new position and velocity based on variation
            if variation == "flock":
                new_agent = self._update_flock_agent(
                    agent, self.agents, speed, cohesion
                )
            elif variation == "predator":
                new_agent = self._update_predator_agent(
                    agent, self.agents, self._predator_pos, speed
                )
            elif variation == "school":
                new_agent = self._update_school_agent(
                    agent, self.agents, speed, cohesion
                )
            elif variation == "spiral":
                new_agent = self._update_spiral_agent(agent, speed)
            elif variation == "scatter":
                new_agent = self._update_scatter_agent(agent, speed)
            else:  # orbit
                new_agent = self._update_orbit_agent(
                    agent, self._attractor_points, speed
                )

            # Add trail if enabled
            if max_trail_length > 0:
                self.trails.append(
                    {
                        "pos": agent["pos"],
                        "age": 1.0,
                        "color": self._get_agent_color(agent, color_mode),
                    }
                )

            # Add agent to new list and draw
            new_agents.append(new_agent)
            color = self._get_agent_color(new_agent, color_mode)
            x, y = new_agent["pos"]
            pixels.extend(self._draw_agent(x, y, params["size"], color))

        # Update and draw trails with fixed maximum
        if max_trail_length > 0:
            new_trails = []
            for trail in self.trails[
                -max_trail_length * len(self.agents) :
            ]:  # Only process recent trails
                if trail["age"] > 0.1:
                    trail["age"] *= 0.9
                    color = tuple(int(c * trail["age"]) for c in trail["color"])
                    x, y = trail["pos"]
                    pixels.extend(self._draw_agent(x, y, 1, color))
                    new_trails.append(trail)
            self.trails = new_trails[
                : max_trail_length * len(self.agents)
            ]  # Enforce maximum trail length

        # Draw predator if active
        if variation == "predator" and self._predator_pos:
            predator_color = (255, 50, 50)  # Red color for predator
            x, y = self._predator_pos
            pixels.extend(self._draw_agent(x, y, params["size"] + 1, predator_color))

        self.agents = new_agents
        self._time += 1

        return self._ensure_all_pixels_handled(pixels)

    def _update_flock_agent(
        self, agent: Dict, agents: List[Dict], speed: float, cohesion: float
    ) -> Dict:
        """Update agent position and velocity for flocking behavior"""
        # Calculate center of mass and average velocity
        com_x, com_y = 0, 0
        avg_dx, avg_dy = 0, 0
        count = 0

        for other in agents:
            if other != agent and other["group"] == agent["group"]:
                dx = other["pos"][0] - agent["pos"][0]
                dy = other["pos"][1] - agent["pos"][1]
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < 8:  # Neighbor radius
                    com_x += other["pos"][0]
                    com_y += other["pos"][1]
                    avg_dx += other["vel"][0]
                    avg_dy += other["vel"][1]
                    count += 1

        if count > 0:
            # Cohesion - move toward center of mass
            com_x /= count
            com_y /= count
            cohesion_dx = (com_x - agent["pos"][0]) * cohesion
            cohesion_dy = (com_y - agent["pos"][1]) * cohesion

            # Alignment - match average velocity
            avg_dx /= count
            avg_dy /= count

            # Update velocity
            new_dx = agent["vel"][0] * 0.9 + (cohesion_dx + avg_dx) * 0.1
            new_dy = agent["vel"][1] * 0.9 + (cohesion_dy + avg_dy) * 0.1
        else:
            new_dx = agent["vel"][0]
            new_dy = agent["vel"][1]

        # Normalize velocity
        vel_mag = math.sqrt(new_dx * new_dx + new_dy * new_dy)
        if vel_mag > 0:
            new_dx = (new_dx / vel_mag) * speed
            new_dy = (new_dy / vel_mag) * speed

        # Update position
        new_x = (agent["pos"][0] + new_dx) % self.width
        new_y = (agent["pos"][1] + new_dy) % self.height

        return {
            "pos": (new_x, new_y),
            "vel": (new_dx, new_dy),
            "energy": agent["energy"],
            "group": agent["group"],
        }

    def _update_predator_agent(
        self,
        agent: Dict,
        agents: List[Dict],
        predator_pos: Tuple[float, float],
        speed: float,
    ) -> Dict:
        """Update agent position and velocity for predator avoidance behavior"""
        # Calculate distance to predator
        dx = predator_pos[0] - agent["pos"][0]
        dy = predator_pos[1] - agent["pos"][1]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 10:  # Flee radius
            # Flee from predator
            flee_dx = -dx / dist * speed * 2
            flee_dy = -dy / dist * speed * 2
            agent["energy"] = min(
                1.0, agent["energy"] + 0.1
            )  # Increase energy when fleeing
        else:
            # Normal movement
            flee_dx = agent["vel"][0]
            flee_dy = agent["vel"][1]
            agent["energy"] = max(
                0.3, agent["energy"] - 0.01
            )  # Decrease energy when calm

        # Add some random movement
        flee_dx += random.uniform(-0.5, 0.5)
        flee_dy += random.uniform(-0.5, 0.5)

        # Normalize velocity
        vel_mag = math.sqrt(flee_dx * flee_dx + flee_dy * flee_dy)
        if vel_mag > 0:
            flee_dx = (flee_dx / vel_mag) * speed
            flee_dy = (flee_dy / vel_mag) * speed

        # Update position
        new_x = (agent["pos"][0] + flee_dx) % self.width
        new_y = (agent["pos"][1] + flee_dy) % self.height

        return {
            "pos": (new_x, new_y),
            "vel": (flee_dx, flee_dy),
            "energy": agent["energy"],
            "group": agent["group"],
        }

    def _update_school_agent(
        self, agent: Dict, agents: List[Dict], speed: float, cohesion: float
    ) -> Dict:
        """Update agent position and velocity for schooling behavior"""
        # Similar to flocking but with tighter grouping and smoother movement
        com_x, com_y = 0, 0
        avg_dx, avg_dy = 0, 0
        separation_x, separation_y = 0, 0
        count = 0

        for other in agents:
            if other != agent:
                dx = other["pos"][0] - agent["pos"][0]
                dy = other["pos"][1] - agent["pos"][1]
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < 6:  # Closer neighbor radius for schools
                    # Separation - avoid getting too close
                    if dist < 2:
                        separation_x -= dx / dist
                        separation_y -= dy / dist

                    com_x += other["pos"][0]
                    com_y += other["pos"][1]
                    avg_dx += other["vel"][0]
                    avg_dy += other["vel"][1]
                    count += 1

        if count > 0:
            com_x /= count
            com_y /= count
            avg_dx /= count
            avg_dy /= count

            # Combine behaviors
            new_dx = (
                agent["vel"][0] * 0.7  # Momentum
                + (com_x - agent["pos"][0]) * cohesion * 0.1  # Cohesion
                + avg_dx * 0.1  # Alignment
                + separation_x * 0.1  # Separation
            )
            new_dy = (
                agent["vel"][1] * 0.7
                + (com_y - agent["pos"][1]) * cohesion * 0.1
                + avg_dy * 0.1
                + separation_y * 0.1
            )
        else:
            new_dx = agent["vel"][0]
            new_dy = agent["vel"][1]

        # Normalize velocity
        vel_mag = math.sqrt(new_dx * new_dx + new_dy * new_dy)
        if vel_mag > 0:
            new_dx = (new_dx / vel_mag) * speed
            new_dy = (new_dy / vel_mag) * speed

        # Update position
        new_x = (agent["pos"][0] + new_dx) % self.width
        new_y = (agent["pos"][1] + new_dy) % self.height

        # Update energy based on alignment with group
        if count > 0:
            alignment = abs(new_dx - avg_dx) + abs(new_dy - avg_dy)
            agent["energy"] = max(0.3, min(1.0, 1.0 - alignment * 0.2))

        return {
            "pos": (new_x, new_y),
            "vel": (new_dx, new_dy),
            "energy": agent["energy"],
            "group": agent["group"],
        }

    def _update_spiral_agent(self, agent: Dict, speed: float) -> Dict:
        """Update agent position and velocity for spiral movement"""
        # Calculate angle and radius from center
        dx = agent["pos"][0] - self._center_x
        dy = agent["pos"][1] - self._center_y
        radius = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)

        # Spiral movement
        new_angle = angle + speed * (0.1 + 0.05 * radius)
        new_radius = max(1, radius + math.sin(new_angle * 2) * 0.1)

        # Update position
        new_x = self._center_x + math.cos(new_angle) * new_radius
        new_y = self._center_y + math.sin(new_angle) * new_radius

        # Wrap around screen edges
        new_x = new_x % self.width
        new_y = new_y % self.height

        # Calculate velocity from position change
        new_dx = new_x - agent["pos"][0]
        new_dy = new_y - agent["pos"][1]

        # Update energy based on radius
        agent["energy"] = 0.3 + (new_radius / (self.width * 0.5)) * 0.7

        return {
            "pos": (new_x, new_y),
            "vel": (new_dx, new_dy),
            "energy": agent["energy"],
            "group": agent["group"],
        }

    def _update_scatter_agent(self, agent: Dict, speed: float) -> Dict:
        """Update agent position and velocity for scatter movement"""
        # Add random acceleration
        new_dx = agent["vel"][0] + random.uniform(-0.5, 0.5) * speed
        new_dy = agent["vel"][1] + random.uniform(-0.5, 0.5) * speed

        # Normalize velocity
        vel_mag = math.sqrt(new_dx * new_dx + new_dy * new_dy)
        if vel_mag > 0:
            new_dx = (new_dx / vel_mag) * speed
            new_dy = (new_dy / vel_mag) * speed

        # Update position
        new_x = (agent["pos"][0] + new_dx) % self.width
        new_y = (agent["pos"][1] + new_dy) % self.height

        # Update energy based on velocity
        agent["energy"] = 0.3 + (vel_mag / speed) * 0.7

        return {
            "pos": (new_x, new_y),
            "vel": (new_dx, new_dy),
            "energy": agent["energy"],
            "group": agent["group"],
        }

    def _update_orbit_agent(
        self, agent: Dict, attractor_points: List[Tuple[float, float]], speed: float
    ) -> Dict:
        """Update agent position and velocity for orbital movement around attractor points"""
        # Find closest attractor
        min_dist = float("inf")
        closest_attractor = None

        for attractor in attractor_points:
            dx = attractor[0] - agent["pos"][0]
            dy = attractor[1] - agent["pos"][1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_dist:
                min_dist = dist
                closest_attractor = attractor

        if closest_attractor:
            # Calculate orbital velocity
            dx = closest_attractor[0] - agent["pos"][0]
            dy = closest_attractor[1] - agent["pos"][1]
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0:
                # Orbital velocity (perpendicular to radius)
                orbit_dx = -dy / dist * speed
                orbit_dy = dx / dist * speed

                # Add some attraction/repulsion based on distance
                ideal_dist = 5.0
                radial_factor = (dist - ideal_dist) * 0.1
                orbit_dx += dx / dist * radial_factor
                orbit_dy += dy / dist * radial_factor

                # Update velocity with some inertia
                new_dx = agent["vel"][0] * 0.9 + orbit_dx * 0.1
                new_dy = agent["vel"][1] * 0.9 + orbit_dy * 0.1
            else:
                new_dx = agent["vel"][0]
                new_dy = agent["vel"][1]

            # Normalize velocity
            vel_mag = math.sqrt(new_dx * new_dx + new_dy * new_dy)
            if vel_mag > 0:
                new_dx = (new_dx / vel_mag) * speed
                new_dy = (new_dy / vel_mag) * speed

            # Update position
            new_x = (agent["pos"][0] + new_dx) % self.width
            new_y = (agent["pos"][1] + new_dy) % self.height

            # Update energy based on how close to ideal orbit it is
            orbit_quality = 1.0 - abs(dist - ideal_dist) / ideal_dist
            agent["energy"] = 0.3 + orbit_quality * 0.7

            return {
                "pos": (new_x, new_y),
                "vel": (new_dx, new_dy),
                "energy": agent["energy"],
                "group": agent["group"],
            }
        else:
            return agent
