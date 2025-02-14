from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Type, Optional
from server.config.grid_config import GridConfig


@dataclass
class Point:
    """Represents a point in the LED grid"""

    x: int
    y: int


@dataclass
class Parameter:
    """Definition of a pattern parameter"""

    name: str
    type: Type
    default: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    description: str = ""


@dataclass
class PatternDefinition:
    """Definition of a pattern and its parameters"""

    name: str
    description: str
    parameters: List[Parameter]
    category: str = "misc"
    tags: List[str] = field(default_factory=list)


class Pattern(ABC):
    """Base class for all patterns"""

    def __init__(self, grid_config: GridConfig):
        self.grid_config = grid_config
        self.width = grid_config.width
        self.height = grid_config.height

    @classmethod
    @abstractmethod
    def definition(cls) -> PatternDefinition:
        """Return the pattern definition"""
        pass

    @abstractmethod
    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        """Generate a single frame of the pattern

        Returns:
            List of dicts with keys: index, r, g, b
        """
        pass

    def _ensure_all_pixels_handled(
        self, pattern_pixels: List[Dict[str, int]]
    ) -> List[Dict[str, int]]:
        """Ensures all pixels in the grid are accounted for, turning off unused ones.

        Args:
            pattern_pixels: List of pixels that should be lit up

        Returns:
            Complete list of all pixels in the grid with their states
        """
        # Create a map of pixels that should be on
        active_pixels = {pixel["index"]: pixel for pixel in pattern_pixels}

        # Create the complete pixel list
        all_pixels = []
        for y in range(self.height):
            for x in range(self.width):
                index = self.grid_config.xy_to_index(x, y)
                if index in active_pixels:
                    all_pixels.append(active_pixels[index])
                else:
                    all_pixels.append({"index": index, "r": 0, "g": 0, "b": 0})

        return all_pixels

    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fill in default parameters"""
        definition = self.definition()
        validated = {}

        for param in definition.parameters:
            value = params.get(param.name, param.default)

            # Type conversion
            try:
                value = param.type(value)
            except (ValueError, TypeError):
                value = param.default

            # Range validation
            if param.min_value is not None and value < param.min_value:
                value = param.min_value
            if param.max_value is not None and value > param.max_value:
                value = param.max_value

            validated[param.name] = value

        return validated


# Pattern registry
class PatternRegistry:
    _patterns: Dict[str, Type[Pattern]] = {}

    @classmethod
    def register(cls, pattern_class: Type[Pattern]):
        """Register a pattern class"""
        definition = pattern_class.definition()
        cls._patterns[definition.name] = pattern_class
        return pattern_class

    @classmethod
    def get_pattern(cls, name: str) -> Optional[Type[Pattern]]:
        """Get a pattern class by name"""
        return cls._patterns.get(name)

    @classmethod
    def list_patterns(cls) -> List[PatternDefinition]:
        """List all registered patterns"""
        return [pattern_class.definition() for pattern_class in cls._patterns.values()]

    @classmethod
    def get_pattern_definition(cls, name: str) -> Optional[PatternDefinition]:
        """Get a pattern definition by name"""
        pattern_class = cls.get_pattern(name)
        if pattern_class:
            return pattern_class.definition()
        return None
