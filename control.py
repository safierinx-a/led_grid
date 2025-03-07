#!/usr/bin/env python3

import json
import argparse
import paho.mqtt.client as mqtt
import time


def send_command(topic: str, payload, mqtt_host="localhost"):
    """Send a command to the pattern server"""
    try:
        # Create MQTT client
        client = mqtt.Client()

        # Set up connection timeout
        connection_timeout = 5  # seconds

        # Connect with timeout
        try:
            client.connect(mqtt_host, 1883, 60)
        except Exception as e:
            print(f"Error connecting to MQTT broker at {mqtt_host}: {e}")
            return False

        # Convert dict payloads to JSON, leave strings as is
        if isinstance(payload, dict):
            payload = json.dumps(payload)

        # Publish with QoS 1 to ensure delivery
        result = client.publish(topic, payload, qos=1)

        # Check publish result
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Error publishing to {topic}: MQTT error code {result.rc}")
            client.disconnect()
            return False

        # Wait for publish to complete
        result.wait_for_publish(timeout=5.0)

        # Disconnect
        client.disconnect()

        print(f"Command sent successfully to {topic}")
        return True

    except Exception as e:
        print(f"Error sending command: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Control LED Pattern Server")
    parser.add_argument(
        "--mqtt-host", default="localhost", help="MQTT broker hostname or IP"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Pattern command
    pattern_parser = subparsers.add_parser("pattern", help="Set pattern")
    pattern_parser.add_argument("name", help="Pattern name")
    pattern_parser.add_argument(
        "--params", type=json.loads, help="Pattern parameters as JSON", default={}
    )

    # Update pattern parameters
    params_parser = subparsers.add_parser("params", help="Update pattern parameters")
    params_parser.add_argument("params", type=json.loads, help="Parameters as JSON")

    # Add modifier
    add_modifier_parser = subparsers.add_parser("add-modifier", help="Add modifier")
    add_modifier_parser.add_argument("name", help="Modifier name")
    add_modifier_parser.add_argument(
        "--params", type=json.loads, help="Modifier parameters as JSON", default={}
    )

    # Remove modifier
    remove_modifier_parser = subparsers.add_parser(
        "remove-modifier", help="Remove modifier"
    )
    remove_modifier_parser.add_argument("index", type=int, help="Modifier index")

    # Clear modifiers
    subparsers.add_parser("clear-modifiers", help="Clear all modifiers")

    # Update modifier parameters
    update_modifier_parser = subparsers.add_parser(
        "update-modifier", help="Update modifier parameters"
    )
    update_modifier_parser.add_argument("index", type=int, help="Modifier index")
    update_modifier_parser.add_argument(
        "params", type=json.loads, help="Parameters as JSON"
    )

    # List patterns and modifiers
    subparsers.add_parser("list", help="List available patterns and modifiers")

    # Stop pattern
    subparsers.add_parser("stop", help="Stop current pattern")

    # Clear display
    subparsers.add_parser("clear", help="Clear display")

    # Set brightness
    brightness_parser = subparsers.add_parser("brightness", help="Set LED brightness")
    brightness_parser.add_argument(
        "value", type=float, help="Brightness value (0.0-1.0)"
    )

    # Power control
    power_parser = subparsers.add_parser("power", help="Control LED power")
    power_parser.add_argument(
        "state", choices=["on", "off"], help="Power state (on/off)"
    )

    args = parser.parse_args()

    if args.command == "pattern":
        # Validate pattern name
        if not args.name:
            print("Error: Pattern name is required")
            return

        # Send command and check result
        success = send_command(
            "led/command/pattern",
            {"name": args.name, "params": args.params},
            args.mqtt_host,
        )

        if success:
            print(f"Pattern set to '{args.name}' with parameters: {args.params}")

    elif args.command == "params":
        # Validate params
        if not args.params:
            print("Error: Parameters are required")
            return

        # Send command and check result
        success = send_command(
            "led/command/params", {"params": args.params}, args.mqtt_host
        )

        if success:
            print(f"Pattern parameters updated: {args.params}")

    elif args.command == "add-modifier":
        send_command(
            "led/command/modifier/add",
            {"name": args.name, "params": args.params},
            args.mqtt_host,
        )

    elif args.command == "remove-modifier":
        send_command(
            "led/command/modifier/remove", {"index": args.index}, args.mqtt_host
        )

    elif args.command == "clear-modifiers":
        send_command("led/command/modifier/clear", {}, args.mqtt_host)

    elif args.command == "update-modifier":
        send_command(
            "led/command/modifier/params",
            {"index": args.index, "params": args.params},
            args.mqtt_host,
        )

    elif args.command == "list":
        # For list command, we need to wait for the response
        def on_message(client, userdata, msg):
            if msg.topic == "led/status/list":
                data = json.loads(msg.payload.decode())
                print("\nAvailable Patterns:")
                for pattern in data["patterns"]:
                    print(f"  {pattern['name']}: {pattern['description']}")
                    print("    Parameters:")
                    for param in pattern["parameters"]:
                        print(
                            f"      {param['name']}: {param['description']} (default: {param['default']})"
                        )

                print("\nAvailable Modifiers:")
                for modifier in data["modifiers"]:
                    print(f"  {modifier['name']}: {modifier['description']}")
                    print("    Parameters:")
                    for param in modifier["parameters"]:
                        print(
                            f"      {param['name']}: {param['description']} (default: {param['default']})"
                        )

                print("\nCurrent State:")
                print(f"  Active Pattern: {data['current_pattern']}")
                print("  Active Modifiers:")
                for i, (name, params) in enumerate(data["current_modifiers"]):
                    print(f"    {i}: {name} {params}")
                client.disconnect()

        client = mqtt.Client()
        client.on_message = on_message
        client.connect(args.mqtt_host, 1883, 60)
        client.subscribe("led/status/list")
        client.publish("led/command/list", "{}")
        client.loop_start()
        time.sleep(1)  # Wait for response
        client.loop_stop()

    elif args.command == "stop":
        # Send command and check result
        success = send_command("led/command/stop", {}, args.mqtt_host)

        if success:
            print("Pattern stopped")

    elif args.command == "clear":
        send_command("led/command/clear", {}, args.mqtt_host)

    elif args.command == "brightness":
        # Validate brightness value
        if args.value < 0.0 or args.value > 1.0:
            print("Error: Brightness value must be between 0.0 and 1.0")
            return

        # Send command and check result
        success = send_command(
            "led/command/hardware",
            {"command": "brightness", "value": args.value},
            args.mqtt_host,
        )

        if success:
            print(f"Brightness set to {args.value * 100:.1f}%")

    elif args.command == "power":
        # Convert to uppercase for the MQTT protocol
        state = "ON" if args.state.lower() == "on" else "OFF"

        # Send command and check result
        success = send_command("led/command/power", state, args.mqtt_host)

        if success:
            print(f"Power set to {args.state.upper()}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
