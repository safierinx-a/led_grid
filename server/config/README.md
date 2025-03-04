# LED Grid Home Assistant Integration

This directory contains the Home Assistant integration for the LED Grid system. The integration provides a comprehensive user interface for controlling the LED grid, monitoring its status, and automating its behavior.

## Setup

1. Ensure your Home Assistant instance can connect to the MQTT broker specified in your `.env` file.
2. Start the LED Grid pattern server, which will automatically register all entities in Home Assistant.
3. Add the dashboard to your Home Assistant instance by copying the contents of `dashboard.yaml` to a new dashboard.

## Components

### Dashboard

The dashboard (`dashboard.yaml`) provides a user-friendly interface for controlling the LED grid:

- **Pattern Selection**: Choose from available patterns
- **Parameter Controls**: Adjust speed, scale, intensity, variation, and color mode
- **Hardware Controls**: Adjust brightness and power
- **Quick Actions**: Reset, clear, and stop buttons
- **Performance Monitoring**: FPS and frame time metrics
- **Status Monitoring**: Component status indicators

### Automations

The automations (`automations.yaml`) handle bidirectional communication between Home Assistant and the LED grid:

- **Pattern Discovery**: Automatically discover available patterns
- **State Synchronization**: Keep Home Assistant state in sync with the LED grid
- **Control Commands**: Send commands to the LED grid when controls are adjusted
- **Error Handling**: Handle error conditions and invalid values

### Scripts

The scripts (`scripts.yaml`) provide complex control sequences:

- **Reset**: Power cycle and reset the LED grid
- **Clear**: Clear the display and reset pattern selection
- **Stop**: Stop the current pattern
- **Power Cycle**: Turn off and on the LED grid
- **Emergency Stop**: Quickly stop and power off the LED grid

## Entity Reference

### Controls

- `input_select.led_grid_pattern`: Pattern selection
- `input_number.pattern_speed`: Pattern speed control
- `input_number.pattern_scale`: Pattern scale control
- `input_number.pattern_intensity`: Pattern intensity control
- `input_select.pattern_variation`: Pattern variation selection
- `input_select.pattern_color_mode`: Pattern color mode selection
- `input_number.led_brightness`: LED brightness control
- `switch.led_power`: LED power control

### Buttons

- `button.reset_leds`: Reset LED hardware
- `button.clear_leds`: Clear LED display
- `button.stop_pattern`: Stop current pattern

### Sensors

- `sensor.led_fps`: Current FPS
- `sensor.led_frame_time`: Frame processing time
- `sensor.led_last_reset`: Last reset timestamp
- `binary_sensor.pattern_server_status`: Pattern server connectivity
- `binary_sensor.led_controller_status`: LED controller connectivity

## Troubleshooting

### Component Offline

If a component shows as offline:

1. Check that the pattern server and LED controller are running
2. Verify MQTT broker connectivity
3. Check network connectivity between components
4. Restart the affected component

### Controls Not Working

If controls don't affect the LED grid:

1. Check component status indicators
2. Verify MQTT topics match between Home Assistant and the LED grid
3. Check MQTT broker logs for message delivery issues
4. Restart the Home Assistant MQTT integration

### Pattern List Empty

If the pattern list is empty:

1. Trigger a pattern list refresh by publishing to `led/command/list`
2. Restart the pattern server
3. Check MQTT broker connectivity

## Advanced Usage

### Custom Automations

You can create custom automations that control the LED grid based on external triggers:

```yaml
- alias: Turn On Party Mode at Sunset
  trigger:
    platform: sun
    event: sunset
  action:
    service: input_select.select_option
    target:
      entity_id: input_select.led_grid_pattern
    data:
      option: "rainbow_wave"
```

### Integration with Other Systems

The LED grid can be integrated with other Home Assistant components:

- **Media Players**: Sync with music
- **Motion Sensors**: Activate patterns when motion is detected
- **Time-Based**: Change patterns based on time of day
- **Weather**: Reflect current weather conditions
