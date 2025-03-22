"""
Pattern definitions for the LED grid.

Each pattern module contains one or more pattern classes that are automatically
registered with the PatternRegistry when imported.
"""

# Import base pattern and registry
from server.patterns.base import Pattern, PatternDefinition, Parameter, PatternRegistry

# Import all patterns
from server.patterns.test_pattern import TestPattern
from server.patterns.color_cycle import ColorCycle
from server.patterns.emoji import Emoji
from server.patterns.fire import Fire
from server.patterns.game_of_life import GameOfLife
from server.patterns.generative import Generative
from server.patterns.matrix_rain import MatrixRain
from server.patterns.particle_system import ParticleSystem
from server.patterns.perlin_landscape import PerlinLandscape
from server.patterns.plasma import Plasma
from server.patterns.polyhedra3d import Polyhedra3D
from server.patterns.rainbow_wave import RainbowWave
from server.patterns.sine_wave import SineWave
from server.patterns.starfield import Starfield
from server.patterns.swarm_system import SwarmSystem
from server.patterns.waves import Waves

# Import new pattern directories
from server.patterns.silhouettes import *
from server.patterns.illusions import *

__all__ = [
    "Pattern",
    "PatternDefinition",
    "Parameter",
    "PatternRegistry",
    "TestPattern",
    "ColorCycle",
    "Emoji",
    "Fire",
    "GameOfLife",
    "Generative",
    "MatrixRain",
    "ParticleSystem",
    "PerlinLandscape",
    "Plasma",
    "Polyhedra3D",
    "RainbowWave",
    "SineWave",
    "Starfield",
    "SwarmSystem",
    "Waves",
    # Add new pattern categories
    "Metamorphosis",
    "ShadowTheater",
    "DepthTunnel",
    "ImpossibleCube",
]
