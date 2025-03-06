#!/usr/bin/env python3

import os
import sys
import importlib
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath("."))


# Define a simple PatternRegistry mock
class MockPatternRegistry:
    _patterns = {}

    @classmethod
    def register(cls, pattern_class):
        pattern_name = pattern_class.__name__.lower()
        cls._patterns[pattern_name] = pattern_class
        return pattern_class

    @classmethod
    def list_patterns(cls):
        return list(cls._patterns.keys())


# Create a simple GridConfig mock
class MockGridConfig:
    def __init__(self):
        self.width = 25
        self.height = 24


# Patch the modules to use our mocks
sys.modules["server.patterns.base"] = type(
    "",
    (),
    {
        "PatternRegistry": MockPatternRegistry,
        "Pattern": type("Pattern", (), {}),
        "PatternDefinition": type("PatternDefinition", (), {}),
        "Parameter": type("Parameter", (), {}),
    },
)

sys.modules["server.config.grid_config"] = type(
    "", (), {"GridConfig": MockGridConfig, "DEFAULT_CONFIG": MockGridConfig()}
)


def main():
    # Find all pattern files
    pattern_files = list(Path("server/patterns").glob("*.py"))
    pattern_modules = [
        f.stem for f in pattern_files if f.stem not in ("base", "__init__")
    ]

    print(f"Found {len(pattern_modules)} pattern files:")
    for name in sorted(pattern_modules):
        print(f"- {name}")

    # Check if plasma.py exists
    if "plasma" in pattern_modules:
        print("\nPlasma pattern file exists!")

        # Check if it has the right class
        try:
            with open("server/patterns/plasma.py", "r") as f:
                content = f.read()
                if (
                    "@PatternRegistry.register" in content
                    and "class Plasma(" in content
                ):
                    print(
                        "Plasma pattern has the correct class and registration decorator!"
                    )
                else:
                    print(
                        "Plasma pattern file exists but might be missing the correct class or decorator"
                    )
        except Exception as e:
            print(f"Error reading plasma.py: {e}")
    else:
        print("\nError: Plasma pattern file does not exist!")


if __name__ == "__main__":
    main()
