import socket
import pyaudio
import wave
import os
from datetime import datetime
import numpy as np

PI_IP = '46.228.120.35'
PORT = 5555
CHUNK = 1024
RATE = 44100
CHANNELS = 1
FORMAT = pyaudio.paInt16
RECORD_DIR = os.path.expanduser("~/records")
GAIN = 10

p = pyaudio.PyAudio()

if not os.path.exists(RECORD_DIR):
    os.makedirs(RECORD_DIR)

sock = socket.socket()
try:
    sock.connect((PI_IP, PORT))
    print(f"Connected to {PI_IP}. Recording audio...")
except Exception as e:
    print(f"Failed to connect: {e}")
    exit()

current_minute = -1
wave_file = None
file_path = ""

try:
    while True:
        now = datetime.now()
        if now.minute != current_minute:
            if wave_file:
                wave_file.close()
                print(f"Saved: {file_path}")

            current_minute = now.minute
            timestamp = now.strftime("%Y-%m-%d_%H-%M")
            file_path = os.path.join(RECORD_DIR, f"record_{timestamp}.wav")

            wave_file = wave.open(file_path, 'wb')
            wave_file.setnchannels(CHANNELS)
            wave_file.setsampwidth(p.get_sample_size(FORMAT))
            wave_file.setframerate(RATE)
            print(f"Recording to: {file_path}")

        data = sock.recv(CHUNK * 2)
        if data and wave_file:
            audio_data = np.frombuffer(data, dtype=np.int16)
            amplified_data = np.clip(audio_data.astype(np.int32) * GAIN, -32768, 32767)
            final_data = amplified_data.astype(np.int16)
            wave_file.writeframes(final_data.tobytes())
        else:
            print("Stream ended.")
            break

except KeyboardInterrupt:
    print("\nStopping recording.")
finally:
    print("Cleaning up...")
    if wave_file:
        wave_file.close()
        print(f"Saved: {file_path}")
    sock.close()
    p.terminate()
    print("Finished.")
