# Given a set of files containing text, interactively record audio for each phrase
#
# Usage: python kuiper-record.py --output dir file1.txt file2.txt 
# for each file, the output directory will contain:
#   file1_0001.wav, file1_0002.wav, ...
#   Right now, a training file will be created with the following format, but this
#   may change in the future
#   file1_0001.wav: I speak this text.
#   file1_0002.wav: testing. The quick brown fox jumps over the lazy dog.
#
#  Right now, this is the format used for training in piper, but if we can streamline that, we might
#  change the intermediate format as well. But at least this approach does not require the user to 
#  construct arbitrary indices, just have a file with the list of text examples to be spoken.
#  Right now, we would manually create data sets by having each user create their own directory.
#
import argparse
import os
import sys
import time
import threading
import queue
import wave
import sounddevice as sd
import numpy as np
from pathlib import Path

# Global flag for stopping recording
stop_recording = False

def wait_for_space():
    """Wait for space key press in a separate thread"""
    global stop_recording
    import select
    import tty
    import termios
    
    # Set terminal to raw mode for single character input
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while not stop_recording:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1)
                if key == ' ' or key == '\n':  # Accept space or enter
                    stop_recording = True
                    break
    except Exception as e:
        print(f"⚠️  Error in keyboard monitoring: {e}")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def record_audio(sample_rate=22050, device=None):
    """Record audio until space is pressed"""
    global stop_recording
    stop_recording = False
    
    # Start thread to monitor space key
    space_thread = threading.Thread(target=wait_for_space, daemon=True)
    space_thread.start()
    
    current_device = sd.default.device[0] if device is None else device
    device_info = sd.query_devices(current_device)
    print(f"🎤 Recording with: {device_info['name']} (Press SPACE to stop)")
    
    frames = []
    # Use larger blocksize to prevent overflow
    blocksize = 4096
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', 
                          blocksize=blocksize, device=device, latency='low') as stream:
            while not stop_recording:
                chunk, overflowed = stream.read(blocksize)
                if overflowed:
                    print("⚠️  Audio buffer overflow", end='\r', flush=True)
                frames.append(chunk)
    except KeyboardInterrupt:
        print("\n⚠️  Recording interrupted")
        stop_recording = True
    except Exception as e:
        print(f"⚠️  Recording error: {e}")
        stop_recording = True
    
    print("⏹️  Recording stopped")
    
    if frames:
        audio_data = np.concatenate(frames, axis=0)
        return audio_data.flatten()
    return None

def save_wav(audio_data, filename, sample_rate=22050):
    """Save audio data to WAV file"""
    with wave.open(str(filename), 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

def list_microphones():
    """List all available input devices"""
    devices = sd.query_devices()
    print("\n📱 Available Microphones:")
    print("=" * 80)
    default_input = sd.default.device[0]
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            marker = " ← DEFAULT" if i == default_input else ""
            print(f"  [{i}] {device['name']} (channels: {device['max_input_channels']}, "
                  f"sample rate: {device['default_samplerate']:.0f} Hz){marker}")
    print("=" * 80)
    return default_input

def main():
    parser = argparse.ArgumentParser(description='Record audio for training phrases')
    parser.add_argument('--output', '-o', required=True, help='Output directory for WAV files')
    parser.add_argument('--device', '-d', type=int, help='Microphone device ID (use --list to see available devices)')
    parser.add_argument('--list', '-l', action='store_true', help='List available microphones and exit')
    parser.add_argument('files', nargs='*', help='Input text files')
    
    args = parser.parse_args()
    
    # List microphones if requested
    if args.list:
        list_microphones()
        return
    
    # Show current microphone
    default_device = list_microphones()
    if args.device is not None:
        sd.default.device = args.device
        print(f"\n✅ Using microphone device [{args.device}]")
    else:
        print(f"\n✅ Using default microphone device [{default_device}]")
        print("   Use --device <id> to select a different microphone")
    
    if not args.files:
        print("\n❌ No input files specified")
        return
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_counter = {}  # Track counter per input file
    
    for input_file in args.files:
        input_path = Path(input_file)
        file_base = input_path.stem
        file_counter[file_base] = 0
        
        print(f"\n📄 Processing file: {input_file}")
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ File not found: {input_file}")
            continue
        
        for line in lines:
            file_counter[file_base] += 1
            wav_filename = output_dir / f"{file_base}_{file_counter[file_base]:04d}.wav"
            
            print(f"\n📝 Text: {line}")
            print("Type 'r' to record, 'q' to quit: ", end='', flush=True)
            
            while True:
                choice = input().strip().lower()
                if choice == 'q':
                    print("👋 Quitting...")
                    return
                elif choice == 'r':
                    audio_data = record_audio(device=args.device)
                    if audio_data is not None and len(audio_data) > 0:
                        save_wav(audio_data, wav_filename, sample_rate=22050)
                        print(f"✅ Saved: {wav_filename}")
                        break
                    else:
                        print("⚠️  No audio recorded, try again")
                        print("Type 'r' to record, 'q' to quit: ", end='', flush=True)
                else:
                    print("Invalid choice. Type 'r' to record, 'q' to quit: ", end='', flush=True)
    
    print("\n✅ All recordings complete!")

if __name__ == '__main__':
    main()

