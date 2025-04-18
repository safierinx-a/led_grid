#!/usr/bin/env python3
"""
Binary Frame Decoder Utility for LeGrid

This script decodes binary frames from the LeGrid system, providing detailed
information about the frame format and contents. It can decode frames from:
1. Binary files (saved frame captures)
2. Base64 encoded strings
3. Hex strings

Usage:
  python frame-decoder.py --file <binary_file>
  python frame-decoder.py --base64 <base64_string>
  python frame-decoder.py --hex <hex_string>

Example:
  python frame-decoder.py --file frame_capture.bin
  python frame-decoder.py --base64 AQEAAAAQABAAAQIDBAUGBwgJCgsMDQ4P
  python frame-decoder.py --hex 0101000000100010000102030405060708090a0b0c0d0e0f
"""

import argparse
import base64
import binascii
import logging
import struct
import sys
from colorama import Fore, Back, Style, init

# Initialize colorama for cross-platform colored output
init()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("frame-decoder")


def decode_frame(binary_data, verbose=False, visualize=False):
    """Decode a binary frame and print its contents"""
    try:
        if len(binary_data) < 10:
            logger.error(
                f"{Fore.RED}Frame too short: {len(binary_data)} bytes{Style.RESET_ALL}"
            )
            return

        # Print the first 30 bytes in hex for debugging if verbose
        if verbose:
            header_hex = binary_data[:30].hex()
            formatted_hex = " ".join(
                header_hex[i : i + 2] for i in range(0, len(header_hex), 2)
            )
            logger.info(
                f"{Fore.CYAN}First 30 bytes (hex): {formatted_hex}{Style.RESET_ALL}"
            )

        # Parse header
        version = binary_data[0]
        msg_type = binary_data[1]
        frame_id = struct.unpack("<I", binary_data[2:6])[0]
        width = struct.unpack("<H", binary_data[6:8])[0]
        height = struct.unpack("<H", binary_data[8:10])[0]

        # Define message type names
        msg_types = {1: "FULL_FRAME", 2: "DELTA_FRAME"}
        msg_type_name = msg_types.get(msg_type, "UNKNOWN")

        logger.info(f"{Fore.GREEN}Frame Header:{Style.RESET_ALL}")
        logger.info(f"  Version: {version}")
        logger.info(f"  Type: {msg_type} ({msg_type_name})")
        logger.info(f"  Frame ID: {frame_id}")
        logger.info(f"  Dimensions: {width}x{height}")

        if msg_type == 1:  # Full frame
            pixel_count = width * height
            expected_bytes = 10 + (pixel_count * 3)  # Header + RGB for each pixel
            logger.info(
                f"{Fore.BLUE}Full frame: {pixel_count} pixels, expecting {expected_bytes} bytes{Style.RESET_ALL}"
            )

            if len(binary_data) < expected_bytes:
                logger.warning(
                    f"{Fore.YELLOW}Frame truncated: {len(binary_data)} bytes (expected {expected_bytes}){Style.RESET_ALL}"
                )

            # Sample pixels
            pixel_data = binary_data[10:]
            sample_count = min(10, pixel_count) if not verbose else pixel_count

            # Display the first few pixels
            logger.info(
                f"{Fore.CYAN}Pixel Data (showing {sample_count} of {pixel_count}):{Style.RESET_ALL}"
            )
            for i in range(sample_count):
                idx = i * 3  # 3 bytes per pixel
                if idx + 2 < len(pixel_data):
                    r = pixel_data[idx]
                    g = pixel_data[idx + 1]
                    b = pixel_data[idx + 2]

                    # Calculate row and column for 2D representation
                    row = i // width
                    col = i % width
                    logger.info(
                        f"  Pixel ({col},{row}) [index {i}]: RGB({r}, {g}, {b})"
                    )

            # Visualize in terminal if requested
            if visualize and width <= 32 and height <= 32:  # Limit to reasonable size
                logger.info(f"{Fore.GREEN}Frame Visualization:{Style.RESET_ALL}")
                for y in range(height):
                    line = ""
                    for x in range(width):
                        pixel_idx = (y * width + x) * 3
                        if pixel_idx + 2 < len(pixel_data):
                            r = pixel_data[pixel_idx]
                            g = pixel_data[pixel_idx + 1]
                            b = pixel_data[pixel_idx + 2]

                            # Simplified color mapping for terminal
                            if max(r, g, b) < 30:
                                # Dark/black
                                line += Back.BLACK + "  " + Style.RESET_ALL
                            elif r > max(g, b) + 50:
                                # Red dominant
                                line += Back.RED + "  " + Style.RESET_ALL
                            elif g > max(r, b) + 50:
                                # Green dominant
                                line += Back.GREEN + "  " + Style.RESET_ALL
                            elif b > max(r, g) + 50:
                                # Blue dominant
                                line += Back.BLUE + "  " + Style.RESET_ALL
                            elif r > 200 and g > 200 and b < 100:
                                # Yellow
                                line += Back.YELLOW + "  " + Style.RESET_ALL
                            elif r > 200 and b > 200 and g < 100:
                                # Magenta
                                line += Back.MAGENTA + "  " + Style.RESET_ALL
                            elif g > 200 and b > 200 and r < 100:
                                # Cyan
                                line += Back.CYAN + "  " + Style.RESET_ALL
                            elif r > 200 and g > 200 and b > 200:
                                # White/bright
                                line += Back.WHITE + "  " + Style.RESET_ALL
                            else:
                                # Mixed colors
                                line += Back.WHITE + "  " + Style.RESET_ALL
                    logger.info(line)

        elif msg_type == 2:  # Delta frame
            if len(binary_data) < 12:  # Header + delta count (2 bytes)
                logger.warning(
                    f"{Fore.YELLOW}Delta frame too short: {len(binary_data)} bytes{Style.RESET_ALL}"
                )
                return

            num_deltas = struct.unpack("<H", binary_data[10:12])[0]
            logger.info(
                f"{Fore.BLUE}Delta frame: {num_deltas} pixel changes{Style.RESET_ALL}"
            )

            expected_bytes = 12 + (
                num_deltas * 5
            )  # Header + count + (index + RGB) for each delta
            if len(binary_data) < expected_bytes:
                logger.warning(
                    f"{Fore.YELLOW}Delta frame truncated: {len(binary_data)} bytes (expected {expected_bytes}){Style.RESET_ALL}"
                )

            # Sample delta changes
            delta_data = binary_data[12:]
            sample_count = min(20, num_deltas) if not verbose else num_deltas

            logger.info(
                f"{Fore.CYAN}Delta Changes (showing {sample_count} of {num_deltas}):{Style.RESET_ALL}"
            )
            for i in range(sample_count):
                idx = i * 5  # 5 bytes per delta (2 for index, 3 for RGB)
                if idx + 4 < len(delta_data):
                    pixel_idx = struct.unpack("<H", delta_data[idx : idx + 2])[0]
                    r = delta_data[idx + 2]
                    g = delta_data[idx + 3]
                    b = delta_data[idx + 4]

                    # Calculate row and column for 2D representation
                    row = pixel_idx // width
                    col = pixel_idx % width
                    logger.info(
                        f"  Pixel ({col},{row}) [index {pixel_idx}]: RGB({r}, {g}, {b})"
                    )
        else:
            logger.warning(
                f"{Fore.YELLOW}Unknown message type: {msg_type}{Style.RESET_ALL}"
            )

        # Print frame size summary
        logger.info(f"{Fore.GREEN}Frame Size Summary:{Style.RESET_ALL}")
        logger.info(f"  Total bytes: {len(binary_data)}")
        logger.info(f"  Header bytes: 10")

        if msg_type == 1:  # Full frame
            pixel_bytes = len(binary_data) - 10
            pixel_count_actual = pixel_bytes // 3
            logger.info(f"  Pixel data bytes: {pixel_bytes}")
            logger.info(f"  Pixels encoded: {pixel_count_actual}")
            if pixel_count_actual != width * height:
                logger.warning(
                    f"{Fore.YELLOW}  Warning: Expected {width * height} pixels but found data for {pixel_count_actual}{Style.RESET_ALL}"
                )
        elif msg_type == 2:  # Delta frame
            delta_bytes = len(binary_data) - 12
            delta_count_actual = delta_bytes // 5
            logger.info(f"  Delta header bytes: 2")
            logger.info(f"  Delta data bytes: {delta_bytes}")
            logger.info(f"  Delta changes encoded: {delta_count_actual}")
            if delta_count_actual != num_deltas:
                logger.warning(
                    f"{Fore.YELLOW}  Warning: Expected {num_deltas} deltas but found data for {delta_count_actual}{Style.RESET_ALL}"
                )

    except Exception as e:
        logger.error(f"{Fore.RED}Error decoding frame: {e}{Style.RESET_ALL}")
        import traceback

        logger.error(f"{Fore.RED}{traceback.format_exc()}{Style.RESET_ALL}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Decode LeGrid binary frames")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file", "-f", help="Binary file containing a frame")
    input_group.add_argument("--base64", "-b", help="Base64 encoded frame data")
    input_group.add_argument("--hex", "-x", help="Hex encoded frame data")

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--visualize",
        "-z",
        action="store_true",
        help="Visualize frame in terminal (for small frames)",
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    try:
        binary_data = None
        if args.file:
            with open(args.file, "rb") as f:
                binary_data = f.read()
            logger.info(
                f"{Fore.GREEN}Reading frame from file: {args.file}{Style.RESET_ALL}"
            )
        elif args.base64:
            binary_data = base64.b64decode(args.base64)
            logger.info(f"{Fore.GREEN}Decoding base64 input{Style.RESET_ALL}")
        elif args.hex:
            # Remove spaces and 0x prefixes if present
            hex_clean = args.hex.replace(" ", "").replace("0x", "")
            binary_data = binascii.unhexlify(hex_clean)
            logger.info(f"{Fore.GREEN}Decoding hex input{Style.RESET_ALL}")

        if binary_data:
            logger.info(
                f"{Fore.GREEN}Data size: {len(binary_data)} bytes{Style.RESET_ALL}"
            )
            decode_frame(binary_data, args.verbose, args.visualize)
        else:
            logger.error(f"{Fore.RED}No valid input data provided{Style.RESET_ALL}")

    except Exception as e:
        logger.error(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

# Example (commented out):
# Here are some example binary frame patterns you can test with:
#
# 1. Small 4x4 red grid (full frame):
#    python frame-decoder.py --hex 0101000000040004FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000 --visualize
#
# 2. Small 4x4 checkerboard (full frame):
#    python frame-decoder.py --hex 01010000000400040000FFFF00000000FFFF00000000FFFF00000000FFFF00000000FFFF00000000FFFF00000000FFFF0000 --visualize
#
# 3. Small 4x4 with one pixel change (delta frame):
#    python frame-decoder.py --hex 01020000000400040001000000FF00FF --visualize
