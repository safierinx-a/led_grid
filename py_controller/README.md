# LED Grid Controller

A clean, modular implementation of the controller for the LED grid system, designed to work seamlessly with the Elixir/Phoenix server.

## Features

- Full frame binary protocol implementation
- Configurable LED grid layout and orientation
- Robust WebSocket connection with automatic reconnection
- Phoenix Channel integration with proper event handling
- Hardware abstraction layer for easy porting
- Mock implementation for development without hardware
- Detailed statistics reporting
- Comprehensive error handling

## Installation

### Dependencies

```bash
pip install websocket-client
```

If running on a Raspberry Pi with physical LEDs:

```bash
pip install adafruit-circuitpython-neopixel
```

### Basic Usage

```bash
python -m py_controller.main --server-url ws://your-server:4000/controller/websocket
```

## Configuration

The controller can be configured via command-line arguments, environment variables, or a configuration file.

### Command-line Arguments

```
--config PATH               Path to configuration file
--width WIDTH               Grid width
--height HEIGHT             Grid height
--led-count COUNT           Number of LEDs
--led-pin PIN               GPIO pin for LED data
--brightness BRIGHTNESS     LED brightness (0-255)
--server-url URL            WebSocket server URL
--log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR)
--layout LAYOUT             LED strip layout pattern (linear, serpentine)
--flip-x                    Flip grid horizontally
--flip-y                    Flip grid vertically
--transpose                 Transpose grid (swap X and Y axes)
```

### Environment Variables

Environment variables follow the pattern `LEGRID_VARIABLE_NAME`, e.g.:

- `LEGRID_WIDTH` - Grid width
- `LEGRID_HEIGHT` - Grid height
- `LEGRID_SERVER_URL` - WebSocket server URL
- etc.

### Configuration File

You can specify a JSON configuration file with the `--config` argument:

```json
{
  "width": 25,
  "height": 24,
  "led_count": 600,
  "led_pin": 18,
  "brightness": 255,
  "server_url": "ws://your-server:4000/controller/websocket",
  "layout": "serpentine",
  "flip_x": false,
  "flip_y": false,
  "transpose": false,
  "log_level": "INFO"
}
```

## Architecture

The controller is organized into several modular components:

- **Main Controller**: Orchestrates all components and manages lifecycle
- **Frame Processor**: Handles binary frame processing and LED layout mapping
- **Hardware Interface**: Abstracts the LED hardware control
- **Connection Manager**: Manages WebSocket communication with the server

### Binary Protocol

The controller implements the Legrid binary protocol for efficient frame transmission:

```
<Version:1><Type:1><FrameID:4><Width:2><Height:2><Pixels:3*width*height>
```

This implementation focuses on full frame processing (Type 1) for simplicity and reliability.

## Running as a Service

To run the controller as a system service on a Raspberry Pi:

1. Create a service file:

```
# /etc/systemd/system/legrid-controller.service
[Unit]
Description=Legrid LED Controller
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/py_controller/main.py --config /etc/legrid/config.json
WorkingDirectory=/path/to/py_controller
StandardOutput=journal
StandardError=journal
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

2. Enable and start the service:

```bash
sudo systemctl enable legrid-controller
sudo systemctl start legrid-controller
```

## Development

For development without physical hardware, the controller will automatically use a mock implementation that logs LED updates instead of controlling physical hardware.
