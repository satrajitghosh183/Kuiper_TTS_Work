# display available microphone devices
import sounddevice as sd

print(sd.query_devices())