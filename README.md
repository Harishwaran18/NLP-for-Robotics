# NLP for Robotics — Offline Voice-Controlled Expo Robot

An offline voice assistant for the **Care Open House Expo 2026** robot. You speak a
command, the program recognizes it **without any internet connection**, replies out
loud, and moves the robot through an Arduino over a serial (USB) connection.

```
Microphone  ->  Vosk (offline speech-to-text)  ->  command matching
                                                        |
                                          pyttsx3 (voice reply)
                                                        |
                                          Arduino over serial (robot motion)
```

## Features

- **Fully offline** speech recognition using the [Vosk](https://alphacephei.com/vosk/)
  `vosk-model-small-en-us-0.15` model — no cloud, no API keys.
- **Grammar-restricted** recognition: only the supported commands are recognized,
  which makes it fast and accurate.
- **Spoken replies** with `pyttsx3` (Windows SAPI5 / cross-platform).
- **Arduino control** over serial, with automatic port detection.
- **Graceful fallbacks**: if the Arduino or a TTS engine is missing, it keeps
  working in simulation / text-only mode.
- Configurable model path, serial port, and a `--simulate` flag for testing
  without hardware.

## Hardware

| Part | Notes |
| --- | --- |
| Computer | Windows / Linux / macOS with a microphone |
| Arduino | Uno/Nano/etc. connected over USB, running the sketch below |
| Robot chassis | Motors driven by the Arduino on the commands below |

## Project structure

```
mainn.py                        Main program (speech -> reply -> robot)
requirements.txt                Python dependencies
README.md                       This file
vosk-model-small-en-us-0.15/    Offline speech model (included)
├── am/                         Acoustic model
├── conf/                       Feature configs
├── graph/                      Decoding graph
└── ivector/                    Speaker/feature stats
```

## Setup

1. **Install Python 3.8+** and the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   On Linux you also need PortAudio for `sounddevice`:

   ```bash
   sudo apt-get install libportaudio2
   ```

2. **Use the included Vosk model.** The `vosk-model-small-en-us-0.15` folder is
   already committed in this repository next to `mainn.py`, so no download is
   needed:

   ```
   NLP-for-Robotics/
   ├── mainn.py
   └── vosk-model-small-en-us-0.15/
       ├── am/
       ├── conf/
       ├── graph/
       └── ...
   ```

   If the folder is missing (for example you cloned without large files), download
   it from <https://alphacephei.com/vosk/models> and unzip it next to `mainn.py`, or
   point to it with the `VOSK_MODEL_PATH` environment variable:

   ```bash
   set VOSK_MODEL_PATH=C:\path\to\vosk-model-small-en-us-0.15   # Windows
   export VOSK_MODEL_PATH=/path/to/vosk-model-small-en-us-0.15  # Linux/macOS
   ```

   > **Note:** the `final.mat`, `final.dubm`, `global_cmvn.stats`, `online_cmvn.conf`,
   > `splice.conf` and `word_boundary.int` files in the repository root are copies of
   > files that also live inside `vosk-model-small-en-us-0.15/`; they are harmless
   > leftovers and are not needed to run the program.

3. **Upload the Arduino sketch** (see below) and connect the board by USB.

## Run

```bash
python mainn.py
```

Optional arguments:

```bash
python mainn.py --model path/to/vosk-model-small-en-us-0.15   # explicit model
python mainn.py --port COM3                                   # explicit serial port
python mainn.py --simulate                                    # no Arduino, print commands
```

The program prints `System is ready`, then listens for a command. Say **"bye"**
to shut down.

## Voice commands

| You say | Assistant replies | Robot command (serial) |
| --- | --- | --- |
| hello / hi | Hello, welcome to Care Open House Expo 2026 | `HI` |
| how are you | I am doing great and happy to assist you | — |
| expo | This is Care Open House Expo 2026 showcasing innovation and technology | — |
| who can attend | This expo is open to everyone | — |
| move forward | Moving forward | `FORWARD` |
| turn left | Turning left | `LEFT` |
| turn right | Turning right | `RIGHT` |
| stop | Stopping all actions | `STOP` |
| raise hand | Raising hand | `HI` |
| thank you / thanks | You're welcome | — |
| bye | Thank you, have a great day | `STOP` (exits) |

## Serial protocol

Commands are sent as newline-terminated ASCII strings at **9600 baud**:
`HI\n`, `FORWARD\n`, `LEFT\n`, `RIGHT\n`, `STOP\n`.

Minimal Arduino sketch to drive the robot:

```cpp
void setup() {
  Serial.begin(9600);
  // pinMode(...) for your motor driver here
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "FORWARD")      { /* drive forward  */ }
    else if (cmd == "LEFT")    { /* turn left      */ }
    else if (cmd == "RIGHT")   { /* turn right     */ }
    else if (cmd == "STOP")    { /* stop motors    */ }
    else if (cmd == "HI")      { /* wave / gesture */ }
  }
}
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Vosk model not found` | Download the model and place it next to `mainn.py`, or set `VOSK_MODEL_PATH`. |
| `Mic Error` / no input device | Check the microphone is connected and set as default; install PortAudio on Linux. |
| `Arduino not found` | Install `pyserial`, check the USB cable, and pass the correct `--port` (e.g. `--port COM3`). |
| No sound from the assistant | Install a system TTS voice (SAPI5 on Windows, `espeak` on Linux); the program still runs in text-only mode. |

## Credits

- Speech recognition: [Vosk](https://alphacephei.com/vosk/) / Kaldi.
- `vosk-model-small-en-us-0.15` © Alpha Cephei Inc.
