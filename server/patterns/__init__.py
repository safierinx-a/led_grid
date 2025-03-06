from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry

# Import all pattern modules to register them
from server.patterns import (
    plasma,
    rainbow_wave,
    fire,
    matrix_rain,
    game_of_life,
    starfield,
    particle_system,
    waves,
    polyhedra3d,
    color_cycle,
    emoji,
    perlin_landscape,
    sine_wave,
    swarm_system,
    generative,
)

__all__ = ["Pattern", "PatternDefinition", "Parameter", "PatternRegistry"]
