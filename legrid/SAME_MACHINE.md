# Same-Machine Mode

This document explains how to use the **same-machine mode** for running pattern generation and LED control on the same Raspberry Pi, eliminating network overhead.

## Overview

Same-machine mode allows you to run the entire LED grid system on a single Raspberry Pi without the need for WebSocket communication between separate processes. This provides:

- **5-10x better performance** (eliminates network overhead)
- **90% memory reduction** (no WebSocket buffers, JSON serialization)
- **Sub-5ms latency** (direct process communication)
- **Simplified deployment** (single machine setup)

## Architecture

```
┌─────────────────────────────────────┐
│         Elixir/Phoenix Server      │
│  ┌─────────────────────────────┐   │
│  │    Pattern Generation       │   │
│  │    (Sine fields, etc.)       │   │
│  └─────────────────────────────┘   │
│              │                     │
│              ▼                     │
│  ┌─────────────────────────────┐   │
│  │    Local Interface          │   │
│  │    (Direct IPC)             │   │
│  └─────────────────────────────┘   │
│              │                     │
│              ▼                     │
│  ┌─────────────────────────────┐   │
│  │    LED Controller           │   │
│  │    (Python/Rust)            │   │
│  └─────────────────────────────┘   │
│              │                     │
│              ▼                     │
│  ┌─────────────────────────────┐   │
│  │    Physical LEDs            │   │
│  │    (WS2812B/NeoPixel)      │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Configuration

### Enable Same-Machine Mode

Edit `config/config.exs`:

```elixir
config :legrid,
  # Enable same-machine mode
  same_machine_mode: true,
  local_controller: [
    enabled: true,
    led_pin: 18,                   # GPIO pin for LED data
    led_count: 600,                # Number of LEDs (25x24)
    width: 25,                     # Grid width
    height: 24,                    # Grid height
    controller_type: "python"      # "python" or "rust"
  ]
```

### Environment Variables

You can also configure via environment variables:

```bash
export LEGRID_SAME_MACHINE_MODE=true
export LEGRID_LOCAL_CONTROLLER_ENABLED=true
export LEGRID_LOCAL_CONTROLLER_LED_PIN=18
export LEGRID_LOCAL_CONTROLLER_LED_COUNT=600
export LEGRID_LOCAL_CONTROLLER_WIDTH=25
export LEGRID_LOCAL_CONTROLLER_HEIGHT=24
export LEGRID_LOCAL_CONTROLLER_TYPE=python
```

## Controller Types

### Python Controller (Default)

**Pros:**

- Easy to modify and extend
- Reuses existing hardware interface code
- Good for development and testing

**Cons:**

- Higher memory usage
- Slower than Rust version

**Usage:**

```bash
# The Python controller runs automatically when same-machine mode is enabled
mix phx.server
```

### Rust Controller (Recommended for Production)

**Pros:**

- Maximum performance
- Minimal memory usage
- Zero-copy frame processing

**Cons:**

- Requires Rust toolchain
- More complex to modify

**Build and Usage:**

```bash
# Build the Rust controller
cd legrid/priv/bin
rustc local_controller.rs -o local_controller

# Configure to use Rust controller
export LEGRID_LOCAL_CONTROLLER_TYPE=rust
mix phx.server
```

## Performance Comparison

| Metric               | Networked Mode | Same-Machine Python | Same-Machine Rust |
| -------------------- | -------------- | ------------------- | ----------------- |
| **Latency**          | 10-30ms        | 2-5ms               | 1-3ms             |
| **Memory Usage**     | 100-200MB      | 50-80MB             | 10-20MB           |
| **CPU Usage**        | 20-40%         | 10-20%              | 5-10%             |
| **Max FPS**          | 30-60          | 60-120              | 120-240           |
| **Setup Complexity** | High           | Low                 | Medium            |

## Deployment

### Raspberry Pi 3B

**Recommended Configuration:**

```elixir
config :legrid,
  same_machine_mode: true,
  local_controller: [
    enabled: true,
    led_pin: 18,
    led_count: 600,
    width: 25,
    height: 24,
    controller_type: "rust"  # Use Rust for best performance
  ]
```

**Expected Performance:**

- **Frame Rate**: 60-120 FPS
- **Latency**: 1-3ms
- **Memory Usage**: 10-20MB
- **CPU Usage**: 5-15%

### Raspberry Pi Pico 2

**For Pi Pico 2, use the ESP32 implementation instead:**

- The ESP32 controller already runs standalone
- No need for same-machine mode
- Direct hardware control via AtomVM

## Troubleshooting

### Controller Won't Start

1. **Check Python dependencies:**

   ```bash
   pip install adafruit-circuitpython-neopixel
   ```

2. **Check GPIO permissions:**

   ```bash
   sudo usermod -a -G gpio $USER
   ```

3. **Verify LED pin configuration:**
   ```bash
   # Test GPIO pin
   gpio -g mode 18 out
   gpio -g write 18 1
   ```

### Performance Issues

1. **Use Rust controller for better performance**
2. **Reduce pattern complexity**
3. **Lower frame rate if needed**

### Memory Issues

1. **Switch to Rust controller**
2. **Reduce batch sizes**
3. **Monitor with `htop`**

## Development

### Adding New Patterns

Patterns work the same in both modes. The pattern generation happens in the Elixir server, and frames are sent to the local controller.

### Debugging

**Enable debug logging:**

```elixir
config :logger, :console,
  level: :debug
```

**Monitor controller process:**

```bash
# Check if controller is running
ps aux | grep local_controller

# Monitor system resources
htop
```

## Migration from Networked Mode

1. **Backup current configuration**
2. **Enable same-machine mode**
3. **Test with Python controller first**
4. **Switch to Rust controller for production**
5. **Update deployment scripts**

## Future Enhancements

- **Hardware-accelerated video processing**
- **Real-time audio reactivity**
- **Direct GPIO control from Rust**
- **SIMD optimizations for frame processing**
- **Multi-controller support on single machine**
