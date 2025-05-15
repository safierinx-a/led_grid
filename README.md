# LED Grid Controller System

A comprehensive LED grid control system with a Python client, Elixir/Phoenix server, and ESP32 controller implementations.

## Project Structure

This project is organized into three main components:

1. **legrid/** - Elixir/Phoenix server that generates patterns and distributes frames
2. **py_controller/** - Python client that receives frames and controls LED hardware
3. **esp32/** - ESP32 implementation using AtomVM (Erlang for embedded)

## Getting Started

### Server (Elixir/Phoenix)

The server generates patterns and sends frame batches to connected controllers:

```bash
cd legrid
mix deps.get
mix phx.server
```

The server will start on http://localhost:4000 by default.

### Controller (Python)

The Python controller connects to the server, receives frames, and drives the LED hardware:

```bash
cd py_controller
python main.py
```

For development without physical hardware, the controller uses a mock implementation that logs LED updates.

### ESP32 Controller

For ESP32-based controllers, an AtomVM (Erlang) implementation is provided in the `esp32/` directory.

## Key Features

### Batch Frame Processing

The system implements an efficient batch frame transmission protocol:

- Frames are collected in batches for improved network efficiency
- Controllers acknowledge batches to ensure reliable delivery
- Dynamic batch sizing based on pattern characteristics
- Priority frames for pattern changes

### Connection Management

- Automatic reconnection and recovery
- Statistics reporting and monitoring
- Connection status dashboard
- Support for multiple concurrent controllers

### Pattern Generation

The server supports various pattern generators:

- Game of Life
- Sine waves
- Conway patterns
- Custom animations
- And more...

## Deployment

### Docker Support

Docker configuration is provided for containerized deployment:

```bash
docker-compose up
```

## Development

For development, the Python controller automatically uses a mock hardware implementation when physical LEDs aren't available.

The server includes a development dashboard at http://localhost:4000/dashboard for real-time monitoring.

## License

MIT
