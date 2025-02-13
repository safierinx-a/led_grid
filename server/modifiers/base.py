from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Type, Optional
from ..config.grid_config import GridConfig
from ..patterns.base import Parameter, PatternDefinition


@dataclass
class ModifierDefinition:
    """Definition of a pattern modifier"""

    name: str
    description: str
    parameters: List[Parameter]
    category: str = "effect"
    tags: List[str] = field(default_factory=list)


class Modifier(ABC):
    """Base class for pattern modifiers"""

    def __init__(self, grid_config: GridConfig):
        self.grid_config = grid_config
        self.width = grid_config.width
        self.height = grid_config.height

    @classmethod
    @abstractmethod
    def definition(cls) -> ModifierDefinition:
        """Return the modifier definition"""
        pass

    @abstractmethod
    def apply(
        self, pixels: List[Dict[str, int]], params: Dict[str, Any]
    ) -> List[Dict[str, int]]:
        """Apply the modifier to a frame of pixels

        Args:
            pixels: List of dicts with keys: index, r, g, b
            params: Modifier parameters

        Returns:
            Modified list of pixels
        """
        pass

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


class ModifierRegistry:
    """Registry for pattern modifiers"""

    _modifiers: Dict[str, Type[Modifier]] = {}

    @classmethod
    def register(cls, modifier_class: Type[Modifier]):
        """Register a modifier class"""
        definition = modifier_class.definition()
        cls._modifiers[definition.name] = modifier_class
        return modifier_class

    @classmethod
    def get_modifier(cls, name: str) -> Optional[Type[Modifier]]:
        """Get a modifier class by name"""
        return cls._modifiers.get(name)

    @classmethod
    def list_modifiers(cls) -> List[ModifierDefinition]:
        """List all registered modifiers"""
        return [
            modifier_class.definition() for modifier_class in cls._modifiers.values()
        ]
