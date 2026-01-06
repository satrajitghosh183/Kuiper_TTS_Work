# kuiper-record.py
# Interactively or non-interactively record audio for training phrases.

import argparse
import csv
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import sounddevice as sd
import wave

import kuiper_common as kuiper


stop_recording = False  # global flag for keyboard thread


def wait_for_space() -> None:
    """Wait for space/enter in a separate thread (TTY only)."""
    global stop_recording

    if not sys.stdin.isatty():
        return

    import select
    import tty
    import termios

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while not stop_recording:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1)
                if key in (" ", "\n"):
                    stop_recording = True
                    break
    except Exception as e:  # noqa: BLE001
        print(f"Warning: error in keyboard monitoring: {e}")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def record_audio(
    sample_rate: int = 22050,
    device: Optional[int] = None,
    max_duration: Optional[float] = None,
    interactive: bool = True,
) -> Optional[np.ndarray]:
    """Record audio from a microphone."""
    global stop_recording
    stop_recording = False

    if interactive and sys.stdin.isatty():
        space_thread = threading.Thread(target=wait_for_space, daemon=True)
        space_thread.start()

    current_device = sd.default.device[0] if device is None else device
    device_info = sd.query_devices(current_device)
    print(f"Recording with: {device_info['name']}")

    frames: List[np.ndarray] = []
    blocksize = 4096
    start_time = time.time()

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=blocksize,
            device=current_device,
            latency="low",
        ) as stream:
            while True:
                if interactive and stop_recording:
                    break
                if not interactive and max_duration is not None:
                    if time.time() - start_time >= max_duration:
                        break

                chunk, overflowed = stream.read(blocksize)
                if overflowed:
                    print("Warning: audio buffer overflow", end="\r", flush=True)
                frames.append(chunk)
    except KeyboardInterrupt:
        print("\nRecording interrupted (KeyboardInterrupt)")
        stop_recording = True
    except Exception as e:  # noqa: BLE001
        print(f"Recording error: {e}")
        stop_recording = True

    print("Recording stopped")

    if frames:
        audio_data = np.concatenate(frames, axis=0)
        return audio_data.flatten()
    return None


def save_wav(audio_data: np.ndarray, filename: Path, sample_rate: int = 22050) -> None:
    """Save audio data to WAV file."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())


def list_microphones() -> Optional[int]:
    """List all available input devices and return default index."""
    devices = sd.query_devices()
    print("\nAvailable microphones:")
    print("=" * 80)
    default_input = sd.default.device[0]
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            marker = " <- DEFAULT" if i == default_input else ""
            print(
                f"  [{i}] {device['name']} "
                f"(channels: {device['max_input_channels']}, "
                f"sample rate: {device['default_samplerate']:.0f} Hz){marker}"
            )
    print("=" * 80)
    return default_input


def load_phrases_from_files(files: List[Path]) -> List[Tuple[Path, str]]:
    """Load non-empty lines from text files as phrases."""
    phrases: List[Tuple[Path, str]] = []
    for input_file in files:
        try:
            with input_file.open("r", encoding="utf-8") as f:
                for line in f:
                    text = line.strip()
                    if text:
                        phrases.append((input_file, text))
        except FileNotFoundError:
            print(f"File not found: {input_file}")
    return phrases


def write_metadata_row(writer, wav_path: Path, text: str, device_id: Optional[int]) -> None:
    writer.writerow(
        {"wav": str(wav_path), "text": text, "device": device_id if device_id is not None else "", "timestamp": time.time()}
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record audio for training phrases.")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output directory for WAV files")
    parser.add_argument("--device", "-d", type=int, help="Microphone device ID (use --list to see available devices)")
    parser.add_argument("--list", "-l", action="store_true", help="List available microphones and exit")
    parser.add_argument("--sample-rate", type=int, default=kuiper.SAMPLE_RATE, help=f"Sample rate in Hz (default: {kuiper.SAMPLE_RATE})")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive recording: record each phrase for --duration seconds without waiting for keyboard input.",
    )
    parser.add_argument("--duration", type=float, default=5.0, help="Max duration per phrase in seconds (non-interactive mode).")
    parser.add_argument("--metadata", type=Path, default=None, help="Optional CSV file to append metadata (wav,text,device,timestamp).")
    parser.add_argument("files", nargs="*", type=Path, help="Input text files containing phrases (one per line).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.list:
        list_microphones()
        return 0

    if not args.files:
        print("No input files specified")
        return 1

    default_device = list_microphones()
    if args.device is not None:
        sd.default.device = args.device
        device_id = args.device
        print(f"Using microphone device [{args.device}]")
    else:
        device_id = default_device
        print(f"Using default microphone device [{default_device}]")
        print("Use --device <id> to select a different microphone")

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    phrases = load_phrases_from_files(args.files)
    if not phrases:
        print("No phrases found in the provided files.")
        return 1

    metadata_path = args.metadata or (output_dir / "recordings_metadata.csv")
    metadata_file_exists = metadata_path.exists()
    metadata_fp = metadata_path.open("a", newline="", encoding="utf-8")
    fieldnames = ["wav", "text", "device", "timestamp"]
    writer = csv.DictWriter(metadata_fp, fieldnames=fieldnames)
    if not metadata_file_exists:
        writer.writeheader()

    file_counter = {}

    try:
        for input_file, text in phrases:
            base = input_file.stem
            file_counter.setdefault(base, 0)
            file_counter[base] += 1
            wav_filename = output_dir / f"{base}_{file_counter[base]:04d}.wav"

            print(f"\nText: {text}")
            if not args.non_interactive and sys.stdin.isatty():
                print("Type 'r' to record, 'q' to quit: ", end="", flush=True)
                while True:
                    choice = input().strip().lower()
                    if choice == "q":
                        print("Quitting...")
                        return 0
                    if choice == "r":
                        break
                    print("Invalid choice. Type 'r' to record, 'q' to quit: ", end="", flush=True)

                audio_data = record_audio(sample_rate=args.sample_rate, device=device_id, interactive=True)
            else:
                print(f"Non-interactive mode: recording for {args.duration:.1f} s...")
                audio_data = record_audio(
                    sample_rate=args.sample_rate,
                    device=device_id,
                    max_duration=args.duration,
                    interactive=False,
                )

            if audio_data is not None and len(audio_data) > 0:
                save_wav(audio_data, wav_filename, sample_rate=args.sample_rate)
                write_metadata_row(writer, wav_filename, text, device_id)
                metadata_fp.flush()
                print(f"Saved: {wav_filename}")
            else:
                print("No audio recorded, skipping.")
    finally:
        metadata_fp.close()

    print("\nAll recordings complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

