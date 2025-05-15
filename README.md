# AtomVM LED Grid Controller

An Erlang implementation of the LED grid controller for ESP32 using AtomVM.

## Why AtomVM?

Using AtomVM for the ESP32 controller offers several advantages:

1. **Native Erlang/Elixir compatibility**: Since your server is built with Elixir/Phoenix, the controller using Erlang creates a unified technology stack.
2. **Concurrency model**: The Erlang process model is perfect for handling multiple concurrent tasks like WebSocket communication and LED updates.
3. **Fault tolerance**: Erlang's supervisor patterns and error handling provide better reliability.
4. **Efficiency**: The lightweight VM is designed for embedded systems.

## Setup

### Prerequisites

1. Install AtomVM toolchain:

   ```
   git clone https://github.com/atomvm/AtomVM.git
   cd AtomVM
   mkdir build
   cd build
   cmake ..
   make
   ```

2. Install the AtomVM ESP32 binary:

   ```
   cd packbeam
   ./PackBEAM -i ../build/lib/atomvm/ebin/atomvmlib.avm -i led_controller.beam -i neopixel.beam -i jsx.beam -o led_controller.avm
   ```

3. Flash AtomVM to your ESP32:

   ```
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 115200 write_flash -z 0x1000 atomvm-esp32.bin
   ```

4. Upload your application:
   ```
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 115200 write_flash -z 0x3A0000 led_controller.avm
   ```

## ESP-IDF Native Function Requirements

The `neopixel.erl` module relies on two native functions that need to be implemented in AtomVM's ESP32 port:

- `esp:rmt_neopixel_init(Pin, NumLeds)`: Initializes the RMT peripheral for NeoPixel control
- `esp:rmt_neopixel_show(Buffer)`: Sends the RGB data to the NeoPixel strip

These functions need to be added to AtomVM's ESP-IDF driver. A minimal implementation can be found in the `esp_neopixel.c` file.

## Configuration

Edit the `led_controller.erl` file to configure:

- WiFi credentials
- Server host and port
- LED count and pin
- Grid dimensions

## Troubleshooting

If the LEDs don't light up:

1. Check hardware connections (GPIO pin, power supply)
2. Verify you're using the correct pin in the configuration
3. Monitor the ESP32 console output for error messages
4. Try the `test_gpio()` function to verify GPIO functionality

### Batch Frame Format

The controller also supports batched frames for improved connection stability and animation performance:

- 1 byte: 0xB (batch identifier)
- 4 bytes: Frame count (uint32, little-endian)
- 1 byte: Priority flag (1 = priority frames, 0 = normal frames)
- For each frame:
  - 4 bytes: Frame length (uint32, little-endian)
  - N bytes: Frame data (in binary format as described above)

Batch frames offer several advantages:

- Reduced overhead by sending multiple frames in a single WebSocket message
- Better buffering and playback during network instability
- More efficient animation transmission

You can test batch frame transmission using the included `batch-test.py` script:

```bash
python batch-test.py --frames 120 --pattern rainbow
```

## License

MIT
