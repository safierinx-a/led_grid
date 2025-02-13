#!/usr/bin/env python3

import json
import argparse
import paho.mqtt.client as mqtt
import time


def send_command(topic: str, payload: dict):
    """Send a command to the pattern server"""
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    client.publish(topic, json.dumps(payload))
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Control LED Pattern Server")
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

    args = parser.parse_args()

    if args.command == "pattern":
        send_command("led/command/pattern", {"name": args.name, "params": args.params})

    elif args.command == "params":
        send_command("led/command/params", {"params": args.params})

    elif args.command == "add-modifier":
        send_command(
            "led/command/modifier/add", {"name": args.name, "params": args.params}
        )

    elif args.command == "remove-modifier":
        send_command("led/command/modifier/remove", {"index": args.index})

    elif args.command == "clear-modifiers":
        send_command("led/command/modifier/clear", {})

    elif args.command == "update-modifier":
        send_command(
            "led/command/modifier/params", {"index": args.index, "params": args.params}
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
        client.connect("localhost", 1883, 60)
        client.subscribe("led/status/list")
        client.publish("led/command/list", "{}")
        client.loop_start()
        time.sleep(1)  # Wait for response
        client.loop_stop()

    elif args.command == "stop":
        send_command("led/command/stop", {})

    elif args.command == "clear":
        send_command("led/command/clear", {})

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
