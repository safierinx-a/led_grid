# LED Grid Control System

This project implements a modular LED control system for a 24x25 WS2812B LED grid using a Raspberry Pi. The system uses a hybrid communication approach:

1. Pattern Server (`server/pattern_server.py`): Generates patterns and sends frame data from local server via ZMQ
2. LED Controller (`led_controller.py`): Controls the LED hardware, receives frames via ZMQ
3. MQTT: Used for control commands (pattern selection, parameters, etc.)

## Hardware Setup

- 24 strips of 25 WS2812B LEDs (600 LEDs total)
- Raspberry Pi (connected to LED data line via GPIO 18)
- Power supply appropriate for WS2812B LEDs (5V, ~18A for full brightness)

## Software Requirements

Install dependencies on both pattern server and LED controller:

```bash
# On pattern server
cd server
pip install -r requirements.txt

# On LED controller (Raspberry Pi)
pip install -r requirements.txt
```

## System Architecture

The system uses a hybrid communication approach for optimal performance:

- ZMQ REQ/REP: High-performance frame data transmission between pattern server and LED controller
- MQTT: Control commands for pattern selection, parameters, and system control

### Network Configuration

1. Pattern Server:

   - Binds ZMQ REP socket to port 5555
   - Connects to MQTT broker for control commands

2. LED Controller:

   - Connects to pattern server's ZMQ socket
   - Connects to MQTT broker for control commands

3. Required Ports:
   - ZMQ: 5555 (TCP)
   - MQTT: 1883 (TCP)

## Running the System

1. Start the MQTT broker:

```bash
sudo apt-get install mosquitto
sudo systemctl start mosquitto
```

2. Start the pattern server:

```bash
python3 server/pattern_server.py
```

3. Start the LED controller:

```bash
sudo python3 led_controller.py
```

## Configuration

Create a `.env` file with your settings:

```env
MQTT_BROKER=192.168.1.154
MQTT_PORT=1883
MQTT_USER=your_user
MQTT_PASSWORD=your_password
ZMQ_PORT=5555
ZMQ_HOST=192.168.1.154  # Pattern server's IP
```

## Adding New Patterns

1. Create a new pattern class in `server/patterns/`
2. Inherit from `Pattern` base class
3. Implement `definition()` and `generate_frame()`
4. Pattern will be automatically registered

Example:

```python
@PatternRegistry.register
class MyPattern(Pattern):
    @classmethod
    def definition(cls) -> PatternDefinition:
        return PatternDefinition(
            name="my_pattern",
            description="My custom pattern",
            parameters=[...]
        )

    def generate_frame(self, params: Dict[str, Any]) -> List[Dict[str, int]]:
        # Generate and return frame data
        return pixels
```

## Troubleshooting

1. Connection Issues:

   - Verify MQTT broker is running and accessible
   - Check ZMQ port (5555) is open on pattern server
   - Verify network connectivity between components

2. Performance Issues:

   - Monitor FPS in pattern server and LED controller logs
   - Check network latency between components
   - Verify CPU usage on both systems

3. Hardware Issues:
   - Check GPIO permissions
   - Verify power supply connections
   - Monitor LED strip power requirements

## License

MIT License
