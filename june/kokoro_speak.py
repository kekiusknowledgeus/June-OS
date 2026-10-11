"""Persistent isolated Kokoro worker. JSON lines in/out; audio stays in memory."""
import io
import json
import re
import sys
import threading
import time


def chunks(text, limit=180):
    """Bound first synthesis even when the response has no punctuation."""
    text = text.strip()
    while text:
        boundary = re.search(r'[.!?;]\s', text[:limit + 1])
        end = boundary.end() if boundary else min(len(text), limit)
        if not boundary and end < len(text):
            space = text.rfind(' ', 0, end)
            if space > 0:
                end = space
        yield text[:end].strip()
        text = text[end:].strip()


def load_engine(model, voices, threads=2):
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, min(8, threads))
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry('session.intra_op.allow_spinning', '0')
    session = ort.InferenceSession(model, sess_options=options, providers=['CPUExecutionProvider'])
    return Kokoro.from_session(session, voices)


def main():
    import winsound
    import soundfile as sf
    if len(sys.argv) not in {3, 4}:
        raise SystemExit('Usage: kokoro_speak.py MODEL VOICES [THREADS]')
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    engine = load_engine(*sys.argv[1:3], int(sys.argv[3]) if len(sys.argv) == 4 else 2)
    condition = threading.Condition()
    state = {'generation': 0, 'request': None, 'closed': False}

    def emit(event):
        print(json.dumps(event), flush=True)

    def run():
        while True:
            with condition:
                condition.wait_for(lambda: state['request'] is not None or state['closed'])
                if state['closed']:
                    return
                request = state['request']
                state['request'] = None
                generation = state['generation']
            start = time.monotonic()
            try:
                for i, chunk in enumerate(chunks(request['text'][:8000])):
                    if state['generation'] != generation:
                        break
                    samples, rate = engine.create(chunk, voice='af_heart', speed=1.0, lang='en-us')
                    buffer = io.BytesIO()
                    sf.write(buffer, samples, rate, format='WAV', subtype='PCM_16')
                    if state['generation'] != generation:
                        break
                    if i == 0:
                        emit({'id': request['id'], 'first_audio_ms': round((time.monotonic() - start) * 1000)})
                    winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY)
                emit({'id': request['id'], 'done': True})
            except Exception:
                emit({'id': request['id'], 'error': 'Kokoro synthesis or playback failed'})

    threading.Thread(target=run, daemon=True).start()
    emit({'ready': True})
    try:
        for line in sys.stdin:
            request = json.loads(line)
            with condition:
                state['generation'] += 1
                state['request'] = request if request.get('command') == 'speak' else None
                winsound.PlaySound(None, 0)
                condition.notify()
    finally:
        with condition:
            state['closed'] = True
            condition.notify()
        winsound.PlaySound(None, 0)


if __name__ == '__main__':
    main()
