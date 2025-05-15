import os
import json
import logging


class Config:
    """Configuration management with environment variable support"""

    DEFAULT_CONFIG = {
        "width": 25,
        "height": 24,
        "led_count": 600,
        "led_pin": 18,
        "brightness": 255,
        "server_url": "ws://localhost:4000/controller/websocket",
        "layout": "serpentine",
        "flip_x": False,
        "flip_y": False,
        "transpose": False,
        "log_level": "INFO",
    }

    @classmethod
    def load(cls, config_file=None):
        """Load configuration from file, environment and defaults"""
        config = cls.DEFAULT_CONFIG.copy()

        # Load from file if exists
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except Exception as e:
                print(f"Error loading config file: {e}")

        # Override with environment variables
        for key in config:
            env_key = f"LEGRID_{key.upper()}"
            if env_key in os.environ:
                value = os.environ[env_key]

                # Type conversion
                if isinstance(config[key], bool):
                    config[key] = value.lower() in ("true", "yes", "1")
                elif isinstance(config[key], int):
                    config[key] = int(value)
                else:
                    config[key] = value

        return config

    @staticmethod
    def setup_logging(log_level):
        """Configure logging based on config"""
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO

        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        return logging.getLogger("legrid-controller")
