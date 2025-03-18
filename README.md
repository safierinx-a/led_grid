# LED Grid Control System

This project implements a modular LED control system for a 24x25 WS2812B LED grid using a Raspberry Pi. The system uses a hybrid communication approach:

1. Pattern Server (`server/pattern_server.py`): Generates patterns and sends frame data from local server via ZMQ
2. LED Controller (`led_controller.py`): Controls the LED hardware, receives frames via ZMQ
3. MQTT: Used for control commands (pattern selection, parameters, etc.)
4. Web Dashboard: Browser-based UI for controlling patterns and settings

## Hardware Setup

- 24 strips of 25 WS2812B LEDs (600 LEDs total)
- Raspberry Pi (connected to LED data line via GPIO 18)
- Power supply appropriate for WS2812B LEDs (5V, ~18A for full brightness)

### Wiring Diagram

For the Raspberry Pi connection:

- Connect the LED data line to GPIO 18 (Pin 12)
- Connect LED ground to Raspberry Pi ground
- Use a separate 5V power supply for the LEDs (do not power from the Pi)
- Consider using a level shifter between Pi's 3.3V GPIO and the LED's 5V data line

## Software Requirements

Install dependencies on both pattern server and LED controller:

```bash
# On pattern server
cd led_grid
pip install -r requirements.txt

# On LED controller (Raspberry Pi)
pip install -r requirements.txt
```

### Key Dependencies

- Python 3.7+
- Flask & Flask-SocketIO (for web dashboard)
- ZeroMQ (for frame data transmission)
- Paho-MQTT (for control commands)
- NumPy (for pattern generation)
- Dotenv (for configuration)

## System Architecture

The system uses a hybrid communication approach for optimal performance:

- ZMQ REQ/REP: High-performance frame data transmission between pattern server and LED controller
- MQTT: Control commands for pattern selection, parameters, and system control
- WebSockets: Real-time communication with the web dashboard

### Network Configuration

1. Pattern Server:

   - Binds ZMQ REP socket to port 5555
   - Connects to MQTT broker for control commands
   - Serves web dashboard on port 5001

2. LED Controller:

   - Connects to pattern server's ZMQ socket
   - Connects to MQTT broker for control commands

3. Required Ports:
   - ZMQ: 5555 (TCP)
   - MQTT: 1883 (TCP)
   - Web Dashboard: 5001 (TCP)

### Thread Safety

The system is designed with thread safety in mind:

- Pattern Manager: Uses locks to protect pattern state and hardware state access
- Frame Generator: Uses locks to protect observer lists and frame generation
- Grid Configuration: Uses locks to ensure consistent access across components
- Web Server: Properly handles concurrent connections with thread-safe state access

This ensures stable operation even under high loads with multiple connected clients.

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

4. Access the web dashboard:

```
http://your-server-ip:5001
```

Or if you've enabled HTTPS:

```
https://your-server-ip:5001
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
WEB_PORT=5001           # Web dashboard port
```

## Enabling HTTPS

The web dashboard can be served over HTTPS for secure access. To enable HTTPS:

1. Generate SSL certificates:

```bash
# Run the certificate generation script
cd led_grid
./scripts/generate_ssl_cert.sh your-domain.com
```

2. Set SSL certificate environment variables:

```bash
# Add to your .env file
SSL_CERT="./certs/server.crt"
SSL_KEY="./certs/server.key"
```

3. Restart the server. It will automatically detect SSL certificates and start in HTTPS mode.

For production use, consider using Let's Encrypt or another trusted certificate authority instead of self-signed certificates.

### Browser Security Warnings

Since self-signed certificates are not trusted by browsers by default, you'll see a security warning when accessing the dashboard. To proceed:

- Chrome: Click "Advanced" and then "Proceed to [site] (unsafe)"
- Firefox: Click "Advanced" and then "Accept the Risk and Continue"
- Safari: Click "Show Details" and then "visit this website"

## Running as a System Service

For production deployments, you should run the LED Grid services using systemd:

### Pattern Server Service

Create `/etc/systemd/system/led-pattern-server.service`:

```ini
[Unit]
Description=LED Grid Pattern Server
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/led_grid
ExecStart=/usr/bin/python3 server/pattern_server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### LED Controller Service

Create `/etc/systemd/system/led-controller.service`:

```ini
[Unit]
Description=LED Grid Controller
After=network.target led-pattern-server.service
Requires=led-pattern-server.service

[Service]
User=root
WorkingDirectory=/path/to/led_grid
ExecStart=/usr/bin/python3 led_controller.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable led-pattern-server led-controller
sudo systemctl start led-pattern-server led-controller
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

### Connection Issues

- Verify MQTT broker is running and accessible

  ```bash
  systemctl status mosquitto
  mosquitto_sub -t "test/topic" -h localhost -v
  ```

- Check ZMQ port (5555) is open on pattern server

  ```bash
  netstat -tuln | grep 5555
  telnet pattern-server-ip 5555
  ```

- Verify network connectivity between components
  ```bash
  ping pattern-server-ip
  traceroute pattern-server-ip
  ```

### Web Dashboard Issues

- Check if the web server is running

  ```bash
  curl http://localhost:5001/health
  ```

- SSL Certificate Problems

  - Ensure certificate paths are correct in .env file
  - Verify certificate permissions (600 for key file)
  - Check certificate expiration date:
    ```bash
    openssl x509 -enddate -noout -in certs/server.crt
    ```

- WebSocket Connection Issues
  - Check browser console for errors
  - Ensure firewall allows WebSocket connections
  - Try disabling browser extensions that might block connections

### Performance Issues

- Monitor FPS in pattern server and LED controller logs

  - Pattern server should report generation FPS
  - LED controller should report rendering FPS

- Check network latency between components

  ```bash
  ping -c 10 pattern-server-ip
  ```

- Verify CPU usage on both systems
  ```bash
  top
  htop
  ```

### Hardware Issues

- Check GPIO permissions

  ```bash
  ls -la /dev/gpiomem
  sudo usermod -a -G gpio your_username
  ```

- Verify power supply connections

  - Use a multimeter to check voltage at the LED strip
  - Ensure ground is common between Pi and LED power supply

- Monitor LED strip power requirements
  - Calculate max power: LEDs × 60mA = total amps needed
  - Measure actual current draw with an ammeter

## License

MIT License
