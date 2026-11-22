"""Offline voice-controlled assistant for the Care Open House Expo robot.

Pipeline: microphone -> Vosk (offline speech-to-text) -> command matching
-> pyttsx3 (text-to-speech) + an Arduino over serial to drive the robot.
Everything runs locally with no internet connection.
"""

import argparse
import json
import os
import queue
import sys
import time

import sounddevice as sd
from vosk import KaldiRecognizer, Model

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


SAMPLE_RATE = 16000
BLOCK_SIZE = 8000            # 0.5 s of audio per block
SERIAL_BAUD = 9600
LISTEN_TIMEOUT = 6.0         # seconds to wait for a phrase before giving up

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_CANDIDATES = [
    os.environ.get("VOSK_MODEL_PATH", ""),
    os.path.join(BASE_DIR, "vosk-model-small-en-us-0.15"),
    r"C:\Users\HARISHWARAN\OneDrive\Desktop\final robotics project\vosk-model-small-en-us-0.15",
]

COMMANDS = [
    "hello", "hi", "how are you",
    "expo", "who can attend",
    "move forward", "turn left", "turn right",
    "stop", "raise hand",
    "thank you", "thanks", "bye",
]

# (matching phrases, spoken reply, serial command, exit flag)
RESPONSES = [
    (("how are you",), "I am doing great and happy to assist you", None, False),
    (("who can attend",), "This expo is open to everyone", None, False),
    (("move forward",), "Moving forward", b"FORWARD\n", False),
    (("turn left",), "Turning left", b"LEFT\n", False),
    (("turn right",), "Turning right", b"RIGHT\n", False),
    (("raise hand",), "Raising hand", b"HI\n", False),
    (("stop",), "Stopping all actions", b"STOP\n", False),
    (("thank you", "thanks"), "You're welcome", None, False),
    (("expo",), "This is Care Open House Expo 2026 showcasing innovation and technology", None, False),
    (("hello", "hi"), "Hello, welcome to Care Open House Expo 2026", b"HI\n", False),
    (("bye",), "Thank you, have a great day", b"STOP\n", True),
]


def find_model_path(explicit=None):
    """Return the first usable Vosk model directory, or None."""
    candidates = ([explicit] if explicit else []) + MODEL_CANDIDATES
    for path in candidates:
        if not path or not os.path.isdir(path):
            continue
        markers = (
            os.path.join(path, "am", "final.mdl"),
            os.path.join(path, "graph", "HCLG.fst"),
            os.path.join(path, "conf", "model.conf"),
        )
        if any(os.path.isfile(marker) for marker in markers):
            return path
    return None


def load_model(explicit=None):
    path = find_model_path(explicit)
    if path is None:
        print("ERROR: Vosk model not found.")
        print("Download 'vosk-model-small-en-us-0.15' from "
              "https://alphacephei.com/vosk/models and either place it next to "
              "this script or set the VOSK_MODEL_PATH environment variable.")
        sys.exit(1)
    print("Loading Vosk model from:", path)
    return Model(path)


class Speaker:
    """Thin wrapper around pyttsx3 that degrades to text-only output."""

    def __init__(self):
        self.engine = None
        if pyttsx3 is None:
            print("pyttsx3 not installed -> text-only mode")
            return
        for driver in ("sapi5", ""):
            try:
                self.engine = pyttsx3.init(driverName=driver) if driver else pyttsx3.init()
                self.engine.setProperty("rate", 170)
                self.engine.setProperty("volume", 1.0)
                break
            except Exception:
                self.engine = None
        if self.engine is None:
            print("TTS unavailable -> text-only mode")

    def speak(self, text):
        print("Assistant:", text)
        if self.engine is None:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as exc:
            print("TTS Error:", exc)


def connect_arduino(port=None):
    """Open a serial connection to the Arduino, or return None."""
    if serial is None:
        print("pyserial not installed -> voice-only mode")
        return None

    if port:
        try:
            arduino = serial.Serial(port, SERIAL_BAUD, timeout=1)
            time.sleep(2)
            print("Connected to Arduino on", port)
            return arduino
        except Exception as exc:
            print("Could not open %s: %s -> voice-only mode" % (port, exc))
            return None

    for candidate in list_ports.comports():
        try:
            print("Trying %s..." % candidate.device)
            arduino = serial.Serial(candidate.device, SERIAL_BAUD, timeout=1)
            time.sleep(2)
            print("Connected to Arduino on", candidate.device)
            return arduino
        except Exception:
            continue

    print("Arduino not found -> voice-only mode")
    return None


def send_command(arduino, command):
    if command is None:
        return
    if arduino is None:
        print("[SIMULATION]", command.decode(errors="ignore").strip())
        return
    try:
        arduino.write(command)
    except Exception:
        print("Arduino disconnected!")


class Listener:
    """Streams microphone audio into a grammar-restricted Vosk recognizer."""

    def __init__(self, model):
        self.recognizer = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(COMMANDS))
        self._queue = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        if status:
            print("Audio status:", status)
        self._queue.put(bytes(indata))

    def listen(self, timeout=LISTEN_TIMEOUT):
        self.recognizer.Reset()
        while not self._queue.empty():
            self._queue.get_nowait()

        print("Listening...")
        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                   dtype="int16", channels=1,
                                   callback=self._callback):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        data = self._queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if self.recognizer.AcceptWaveform(data):
                        return json.loads(self.recognizer.Result()).get("text", "").strip().lower()
                return json.loads(self.recognizer.FinalResult()).get("text", "").strip().lower()
        except Exception as exc:
            print("Mic Error:", exc)
            return ""


def handle_command(query, speaker, arduino):
    """Speak a reply, drive the robot if needed. Return True to exit."""
    for phrases, reply, command, should_exit in RESPONSES:
        if any(phrase in query for phrase in phrases):
            speaker.speak(reply)
            send_command(arduino, command)
            return should_exit
    speaker.speak("Please say again clearly")
    return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Offline voice-controlled expo robot assistant")
    parser.add_argument("--model", help="path to the Vosk model directory")
    parser.add_argument("--port", help="Arduino serial port (e.g. COM3); auto-detected if omitted")
    parser.add_argument("--simulate", action="store_true",
                        help="never open a serial port, just print robot commands")
    return parser.parse_args()


def main():
    args = parse_args()
    model = load_model(args.model)
    speaker = Speaker()
    arduino = None if args.simulate else connect_arduino(args.port)
    listener = Listener(model)

    speaker.speak("System is ready")
    try:
        while True:
            query = listener.listen()
            if not query:
                continue
            print("You said:", query)
            if handle_command(query, speaker, arduino):
                break
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        if arduino is not None:
            try:
                arduino.write(b"STOP\n")
                arduino.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
