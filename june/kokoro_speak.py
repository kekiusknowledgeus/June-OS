"""Run Kokoro audio synthesis in June's isolated Python 3.12 environment.

The main June runtime uses Python 3.14; this subprocess keeps it independent
from Kokoro's dependencies. No network calls or audio recording.
"""
import io
from pathlib import Path
import sys
import winsound

import soundfile as sf
from kokoro_onnx import Kokoro


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: kokoro_speak.py MODEL.onnx VOICES.bin")
    model, voices = (Path(p) for p in sys.argv[1:])
    if not model.is_file() or not voices.is_file():
        raise SystemExit("Kokoro model files are missing")
    text = sys.stdin.read(1600).strip()
    if not text:
        return
    tts = Kokoro(str(model), str(voices))
    samples, sample_rate = tts.create(
        text, voice="af_heart", speed=1.0, lang="en-us"
    )
    output = io.BytesIO()
    sf.write(output, samples, sample_rate, format="WAV")
    # Synchronous playback so the parent can interrupt by killing this process.
    winsound.PlaySound(output.getvalue(), winsound.SND_MEMORY)


if __name__ == "__main__":
    main()
