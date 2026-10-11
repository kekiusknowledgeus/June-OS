"""Silent local Kokoro benchmark. No playback, recording, network, or saved WAV.

Run with .venv-voice/Scripts/python.exe scripts/benchmark_speech.py --threads 2
Use --original to compare the installed library's default session settings.
"""
import argparse
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threads', type=int, choices=range(1, 9), default=2)
    parser.add_argument('--original', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from june.kokoro_speak import load_engine
    model = root / 'models/kokoro/kokoro-v1.0.int8.onnx'
    voices = root / 'models/kokoro/voices-v1.0.bin'
    if not model.is_file() or not voices.is_file():
        parser.error('Place the local Kokoro model and voices in models/kokoro first')
    start = time.perf_counter()
    if args.original:
        from kokoro_onnx import Kokoro
        engine = Kokoro(str(model), str(voices))
    else:
        engine = load_engine(str(model), str(voices), args.threads)
    print(json.dumps({'mode': 'original' if args.original else 'bounded_cpu',
                      'threads': None if args.original else args.threads,
                      'load_seconds': round(time.perf_counter() - start, 3)}), flush=True)
    for case in ('cold', 'warm'):
        start = time.perf_counter()
        audio, rate = engine.create('June is ready.', voice='af_heart', speed=1.0, lang='en-us')
        elapsed = time.perf_counter() - start
        duration = len(audio) / rate
        print(json.dumps({'case': case, 'synthesis_seconds': round(elapsed, 3),
                          'audio_seconds': round(duration, 3),
                          'real_time_factor': round(elapsed / duration, 3) if duration else None}), flush=True)


if __name__ == '__main__':
    main()
