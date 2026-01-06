# listmicrophones.py
# List available microphone devices with optional JSON output.

import argparse
import json

import sounddevice as sd


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="List audio input devices.")
    parser.add_argument("--json", action="store_true", help="Output devices as JSON instead of human-readable text.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        devices = sd.query_devices()
    except Exception as e:  # noqa: BLE001
        print(f"Error querying devices: {e}")
        return 1

    input_devices = [
        {
            "id": idx,
            "name": dev["name"],
            "max_input_channels": dev["max_input_channels"],
            "default_samplerate": dev["default_samplerate"],
        }
        for idx, dev in enumerate(devices)
        if dev["max_input_channels"] > 0
    ]

    if not input_devices:
        print("No input devices found.")
        return 1

    if args.json:
        print(json.dumps(input_devices, indent=2))
    else:
        print("Input devices:")
        for dev in input_devices:
            print(f"  [{dev['id']}] {dev['name']} (channels: {dev['max_input_channels']}, sample rate: {dev['default_samplerate']:.0f} Hz)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

