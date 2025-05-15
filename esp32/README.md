# ESP32 LED Grid Controller

An Erlang implementation of the LED grid controller for ESP32 using AtomVM.

## Why AtomVM?

Using AtomVM for the ESP32 controller offers several advantages:

1. **Native Erlang/Elixir compatibility**: Since the server is built with Elixir/Phoenix, the controller using Erlang creates a unified technology stack.
2. **Concurrency model**: The Erlang process model is perfect for handling multiple concurrent tasks like WebSocket communication and LED updates.
3. **Fault tolerance**: Erlang's supervisor patterns and error handling provide better reliability.
4. **Efficiency**: The lightweight VM is designed for embedded systems.

## Files in this Directory

- **led_controller.erl**: Main controller implementation
- **neopixel.erl**: Erlang module for interacting with NeoPixel LEDs
- **esp_neopixel.c**: C implementation of the ESP32 RMT driver for NeoPixels
- **ctrlr-esp32.txt**: Additional configuration notes

## Setup

### Prerequisites

1. Install AtomVM toolchain:

   ```bash
   git clone https://github.com/atomvm/AtomVM.git
   cd AtomVM
   mkdir build
   cd build
   cmake ..
   make
   ```

2. Install the AtomVM ESP32 binary:

   ```bash
   cd packbeam
   ./PackBEAM -i ../build/lib/atomvm/ebin/atomvmlib.avm -i led_controller.beam -i neopixel.beam -i jsx.beam -o led_controller.avm
   ```

3. Flash AtomVM to your ESP32:

   ```bash
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 115200 write_flash -z 0x1000 atomvm-esp32.bin
   ```

4. Upload your application:
   ```bash
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

## Batch Frame Support

The controller implements the same batch frame protocol as the Python controller:

- Receives binary batch frames from the server
- Processes frames efficiently using native AtomVM capabilities
- Acknowledges batches to ensure reliable delivery

## Troubleshooting

If the LEDs don't light up:

1. Check hardware connections (GPIO pin, power supply)
2. Verify you're using the correct pin in the configuration
3. Monitor the ESP32 console output for error messages
4. Try the `test_gpio()` function to verify GPIO functionality

## License

MIT
