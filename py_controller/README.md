# Python LED Grid Controller

A modular Python implementation of the LED grid controller that works seamlessly with the Elixir/Phoenix server.

## Key Features

- Full binary frame protocol implementation with batch processing
- Proper batch acknowledgment and sequence tracking
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
# Run from the main directory
cd py_controller
python main.py

# Or with custom configuration
python main.py --server-url ws://your-server:4000/controller/websocket --width 25 --height 24
```

## Batch Frame Processing

This controller implements an advanced binary batch frame protocol:

- Receives and processes batches of frames for better performance
- Properly acknowledges received batches with sequence numbers
- Tracks and requests the next batch in sequence
- Handles binary data directly for maximum efficiency

The batch protocol provides:

- Improved network efficiency with reduced overhead
- Better buffer management and playback during network instability
- Higher frame rates for smooth animations

## Architecture

The controller is organized into several modular components:

- **Main Controller**: Orchestrates all components and manages lifecycle
- **Connection Manager**: Manages WebSocket communication and batch processing
- **Frame Processor**: Handles binary frame decoding and LED layout mapping
- **Hardware Interface**: Abstracts the LED hardware control

### Binary Protocol

The controller implements the Legrid binary protocol:

```
Batch format:
<Batch marker:1><Frame count:4><Priority:1><Sequence:4><Timestamp:8><Frames...>

Frame format:
<Length:4><Version:1><Type:1><FrameID:4><Width:2><Height:2><Pixels:3*width*height>
```

## Configuration

The controller can be configured via command-line arguments, environment variables, or a configuration file.

### Command-line Arguments

```
--config PATH               Path to configuration file
--width WIDTH               Grid width (default: 25)
--height HEIGHT             Grid height (default: 24)
--led-count COUNT           Number of LEDs (default: width*height)
--led-pin PIN               GPIO pin for LED data (default: 18)
--brightness BRIGHTNESS     LED brightness (0-255) (default: 255)
--server-url URL            WebSocket server URL (default: ws://localhost:4000/controller/websocket)
--log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR) (default: INFO)
--layout LAYOUT             LED strip layout pattern (linear, serpentine) (default: serpentine)
--flip-x                    Flip grid horizontally
--flip-y                    Flip grid vertically
--transpose                 Transpose grid (swap X and Y axes)
```

### Environment Variables

Environment variables follow the pattern `LEGRID_VARIABLE_NAME`, e.g.:

- `LEGRID_WIDTH` - Grid width
- `LEGRID_HEIGHT` - Grid height
- `LEGRID_SERVER_URL` - WebSocket server URL

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
