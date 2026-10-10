"""Persistent offline Kokoro voice worker running in Python 3.12.

Model weights load once. Replies are synthesized in short chunks so playback
begins before the whole reply has been generated.
"""
import io
import json
from pathlib import Path
import re
import sys
import time
import winsound

import soundfile as sf
from kokoro_onnx import Kokoro


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def speech_chunks(text, max_chars=120):
    """Prefer natural sentence boundaries while keeping first audio short."""
    text = re.sub(r"\s+", " ", text).strip()
    current = []
    length = 0
    for word in text.split():
        added = len(word) + (1 if current else 0)
        if current and length + added > max_chars:
            yield " ".join(current)
            current, length = [], 0
        current.append(word)
        length += len(word) + (1 if len(current) > 1 else 0)
        if length >= 55 and word.endswith((".", "!", "?", ";", ":")):
            yield " ".join(current)
            current, length = [], 0
    if current:
        yield " ".join(current)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: kokoro_speak.py MODEL.onnx VOICES.bin")
    model, voices = (Path(p) for p in sys.argv[1:])
    if not model.is_file() or not voices.is_file():
        raise SystemExit("Kokoro model files are missing")

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
            start = time.perf_counter()
            first_audio = None
            parts = 0
            for chunk in speech_chunks(text[:1500]):
                samples, sample_rate = tts.create(
                    chunk, voice="af_heart", speed=1.0, lang="en-us"
                )
                output = io.BytesIO()
                sf.write(output, samples, sample_rate, format="WAV")
                if first_audio is None:
                    first_audio = round(time.perf_counter() - start, 2)
                winsound.PlaySound(output.getvalue(), winsound.SND_MEMORY)
                parts += 1
            emit({"status": "done", "chunks": parts,
                  "first_audio_seconds": first_audio,
                  "total_seconds": round(time.perf_counter() - start, 2)})
        except Exception as exc:
            emit({"status": "error", "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
