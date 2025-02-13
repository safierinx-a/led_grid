# LED Grid Control System

This project implements a modular LED control system for a 24x25 WS2812B LED grid using a Raspberry Pi. The system is split into two main components:

1. Pattern Engine (`pattern_engine.py`): Generates and broadcasts pattern commands
2. LED Controller (`led_controller.py`): Receives pattern commands and controls the LED hardware

## Hardware Setup

- 24 strips of 25 WS2812B LEDs (600 LEDs total)
- Raspberry Pi (connected to LED data line via GPIO 18)
- Power supply appropriate for WS2812B LEDs (5V, ~18A for full brightness)

## Software Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## System Architecture

The system uses MQTT for communication between the pattern engine and LED controller:

- Pattern Engine broadcasts pattern commands on topic `led/pattern`
- LED Controller subscribes to `led/pattern` and executes the patterns
- Patterns are defined as JSON messages with pattern name and parameters

## Running the System

1. Start the MQTT broker:

```bash
sudo apt-get install mosquitto
sudo systemctl start mosquitto
```

2. Start the LED controller:

```bash
sudo python3 led_controller.py
```

3. Start the pattern engine:

```bash
python3 pattern_engine.py
```

## Adding New Patterns

To add new patterns:

1. Add pattern generator method to `PatternEngine` class
2. Add pattern execution logic to `LEDController` class
3. Broadcast pattern with appropriate parameters

## Troubleshooting

- Ensure the MQTT broker is running
- Check GPIO permissions
- Verify power supply connections
- Monitor system logs for errors

## License

MIT License
