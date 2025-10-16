import socket
import pyaudio
import sys

HOST = '0.0.0.0'
PORT = 5555
CHUNK = 1024
CHANNELS = 1
FORMAT = pyaudio.paInt16

p = pyaudio.PyAudio()
stream = None

try:
    device_info = p.get_default_input_device_info()
    RATE = int(device_info['defaultSampleRate'])
    input_device_index = device_info['index']

    print(f"Found default input device: '{device_info['name']}'")
    print(f"Using device's supported sample rate: {RATE} Hz")

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=input_device_index)

except IOError:
    print("Error: No default input device found. Please ensure a microphone is connected.")
    p.terminate()
    sys.exit(1)


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)
print(f"Server is listening on {HOST}:{PORT}...")

try:
    while True:
        print("Waiting for a client to connect...")
        conn, addr = server.accept()
        print(f"Connected to client at {addr}")

        try:
            rate_bytes = RATE.to_bytes(4, 'little')
            conn.sendall(rate_bytes)
            print(f"Sent sample rate {RATE} to client.")

            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                conn.send(data)

        except (BrokenPipeError, ConnectionResetError):
            print(f"Client {addr} disconnected.")
        except Exception as e:
            print(f"An error occurred with client {addr}: {e}")
        finally:
            conn.close()
            print("Connection closed. Ready for a new client.")

except KeyboardInterrupt:
    print("\nServer is shutting down.")
finally:
    print("Cleaning up resources...")
    if stream:
        stream.stop_stream()
        stream.close()
    p.terminate()
    server.close()
    print("Server shut down successfully.")
