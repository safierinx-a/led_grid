# Legrid LED Matrix Controller

A flexible and performant controller for driving LED matrix displays with patterns from a web-based server. The system supports both Raspberry Pi hardware control and a mock implementation for development without physical hardware.

## Features

- Real-time control of WS2812B/NeoPixel LED matrices
- WebSocket communication with the Legrid server
- Support for binary and JSON frame formats
- Automatic reconnection and error handling
- Configurable settings via command-line arguments
- Mock implementation for development without hardware
- Performance statistics and diagnostics

## Requirements

### Hardware

- Raspberry Pi (3B+ or newer recommended)
- WS2812B/NeoPixel LED strip/matrix
- 5V power supply (adequate for your LED count)
- Level shifter (recommended for reliable signal)

### Software

- Python 3.6+
- rpi_ws281x library (for hardware control)
- websocket-client library

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/legrid-controller.git
cd legrid-controller
```

2. Install dependencies:

```bash
pip install websocket-client
```

3. Install rpi_ws281x (on Raspberry Pi only):

```bash
pip install rpi_ws281x
```

## Configuration

The controller accepts various command-line arguments:

| Argument           | Description                                 | Default             |
| ------------------ | ------------------------------------------- | ------------------- |
| `--width`          | Grid width                                  | 25                  |
| `--height`         | Grid height                                 | 24                  |
| `--led-count`      | Number of LEDs                              | 600                 |
| `--led-pin`        | GPIO pin                                    | 18                  |
| `--led-brightness` | LED brightness (0-255)                      | 255                 |
| `--server-url`     | Legrid server URL                           | ws://localhost:8080 |
| `--log-level`      | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO                |

## Usage

### Basic Usage

Run the controller with default settings:

```bash
python raspberry-controller.py
```

### Custom Configuration

```bash
python raspberry-controller.py --width 32 --height 32 --led-count 1024 --led-pin 18 --led-brightness 128 --server-url ws://your-server:8080 --log-level INFO
```

### Development Mode

For development without actual hardware, the controller automatically uses a mock implementation when the rpi_ws281x library is not available.

## Wiring Diagram

```
Raspberry Pi    Level Shifter    LED Strip
-----------    -------------    ---------
5V  ---------> 5V (HV)
GND ---------> GND
Pin 18 -------> A1        ----> Data In
               B1
               VCC (LV) <----- 3.3V
               HV  <----------- 5V (from power supply)
               GND <----------- GND (from power supply)
```

## Protocol

The controller supports two frame formats:

### Binary Format

- 1 byte: protocol version
- 1 byte: message type (1 = frame, 2 = delta frame)
- 4 bytes: frame ID (uint32)
- 2 bytes: width (uint16)
- 2 bytes: height (uint16)
- Remaining bytes: RGB pixel data (1 byte per channel)

### JSON Format

```json
{
  "type": "frame",
  "id": "12345678",
  "pixels": [[r,g,b], [r,g,b], ...]
}
```

## License

MIT License

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
