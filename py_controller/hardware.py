import time
import logging

logger = logging.getLogger("legrid-controller")


class LEDHardware:
    """Base class for LED hardware control"""

    def __init__(self, led_count, width, height, brightness=255):
        self.led_count = led_count
        self.width = width
        self.height = height
        self.brightness = brightness
        self.initialized = False

    def initialize(self):
        """Initialize the hardware"""
        raise NotImplementedError

    def set_pixel(self, index, r, g, b):
        """Set a single pixel"""
        raise NotImplementedError

    def show(self):
        """Update the display"""
        raise NotImplementedError

    def clear(self):
        """Clear all pixels"""
        raise NotImplementedError

    def cleanup(self):
        """Clean up resources"""
        pass


class NeoPixelHardware(LEDHardware):
    """Hardware implementation using NeoPixel/WS2812B LEDs"""

    def __init__(self, led_count, width, height, pin=18, brightness=255):
        super().__init__(led_count, width, height, brightness)
        self.pin = pin
        self.strip = None

    def initialize(self):
        """Initialize the NeoPixel hardware"""
        try:
            import board
            import neopixel

            # Map pin number to board pin
            pin_obj = getattr(board, f"D{self.pin}")

            # Initialize the strip
            self.strip = neopixel.NeoPixel(
                pin_obj,
                self.led_count,
                brightness=self.brightness / 255.0,
                auto_write=False,
                pixel_order=neopixel.GRB,
            )

            self.initialized = True
            logger.info(
                f"Initialized NeoPixel hardware with {self.led_count} LEDs on pin {self.pin}"
            )
            return True

        except ImportError:
            logger.warning("NeoPixel libraries not available")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize NeoPixel hardware: {e}")
            return False

    def set_pixel(self, index, r, g, b):
        """Set a single pixel color"""
        if not self.initialized or not self.strip:
            return

        if 0 <= index < self.led_count:
            self.strip[index] = (r, g, b)

    def show(self):
        """Update the physical display"""
        if self.initialized and self.strip:
            self.strip.show()

    def clear(self):
        """Turn off all LEDs"""
        if not self.initialized or not self.strip:
            return

        for i in range(self.led_count):
            self.strip[i] = (0, 0, 0)
        self.strip.show()

    def cleanup(self):
        """Clean up resources"""
        self.clear()


class MockHardware(LEDHardware):
    """Mock implementation for development without physical hardware"""

    def __init__(self, led_count, width, height, brightness=255):
        super().__init__(led_count, width, height, brightness)
        self.pixels = [(0, 0, 0) for _ in range(led_count)]

    def initialize(self):
        """Initialize the mock hardware"""
        self.initialized = True
        logger.info(f"Initialized mock LED hardware with {self.led_count} LEDs")
        return True

    def set_pixel(self, index, r, g, b):
        """Set a single pixel in the mock display"""
        if 0 <= index < self.led_count:
            self.pixels[index] = (r, g, b)

    def show(self):
        """Update the mock display"""
        # For visual debugging in console output
        lit_count = sum(1 for p in self.pixels if p != (0, 0, 0))
        logger.debug(f"Display updated: {lit_count}/{self.led_count} pixels lit")

    def clear(self):
        """Clear all pixels"""
        self.pixels = [(0, 0, 0) for _ in range(self.led_count)]
        logger.debug("Display cleared")


def create_hardware(config):
    """Factory function to create the appropriate hardware interface"""
    led_count = config.get("led_count", 600)
    width = config.get("width", 25)
    height = config.get("height", 24)
    pin = config.get("led_pin", 18)
    brightness = config.get("brightness", 255)

    # Try NeoPixel hardware first
    hw = NeoPixelHardware(led_count, width, height, pin, brightness)
    if hw.initialize():
        return hw

    # Fall back to mock hardware
    logger.info("Falling back to mock hardware implementation")
    hw = MockHardware(led_count, width, height, brightness)
    hw.initialize()
    return hw
