"""Persistent local Kokoro TTS worker, running under June's Python 3.12 voice venv.

Input: one JSON object per line on stdin, with command=speak and text.
Output: ready / done / error JSON records on stdout. Playback is synchronous,
so the parent can interrupt it by terminating this process.
"""
import io
import json
from pathlib import Path
import sys
import winsound

import soundfile as sf
from kokoro_onnx import Kokoro


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: kokoro_speak.py MODEL.onnx VOICES.bin")
    model, voices = (Path(p) for p in sys.argv[1:])
    if not model.is_file() or not voices.is_file():
        raise SystemExit("Kokoro model files are missing")

    # Expensive initialization happens once, not for every June response.
    tts = Kokoro(str(model), str(voices))
    emit({"status": "ready"})

    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("command") != "speak":
                raise ValueError("Expected speak command")
            text = request.get("text", "")
            if not isinstance(text, str):
                raise ValueError("Text must be a string")
            text = text.strip()[:1500]
            if text:
                samples, sample_rate = tts.create(
                    text, voice="af_heart", speed=1.0, lang="en-us"
                )
                output = io.BytesIO()
                sf.write(output, samples, sample_rate, format="WAV")
                winsound.PlaySound(output.getvalue(), winsound.SND_MEMORY)
            emit({"status": "done"})
        except Exception as exc:
            emit({"status": "error", "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
