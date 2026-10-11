import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from june.brain import Decision, JuneBrain
from june.config import Config
from june.errors import BrainUnavailable
from june.groq_brain import GroqBrain
from june.kokoro_speak import chunks
from june.runtime import Runtime
from june.voice import WindowsSpeech


def event(delta=None, finish=None):
    return 'data: ' + json.dumps({'choices': [{'delta': delta or {}, 'finish_reason': finish}]}) + '\n\n'


def brain_with_response(tmp_path, body, status=200, headers=None):
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(status, text=body, headers=headers)
    brain = GroqBrain(Config.load(tmp_path), SimpleNamespace(get=lambda _: 'synthetic'))
    brain._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return brain, requests


@pytest.mark.parametrize('body', [
    event({'content': 'partial'}),
    event({'content': 'partial'}, 'length') + 'data: [DONE]\n\n',
    'data: not-json\n\n',
    event(finish='stop') + 'data: [DONE]\n\n',
    event({'tool_calls': [{'index': 0, 'id': 'a', 'function': {'name': 'file__read', 'arguments': '{}'}}]}, 'stop') + 'data: [DONE]\n\n',
])
async def test_groq_never_accepts_incomplete_or_empty_responses(tmp_path, body):
    brain, _ = brain_with_response(tmp_path, body)
    try:
        with pytest.raises(BrainUnavailable):
            await brain.respond([{'role': 'user', 'content': 'read file'}], [{'name': 'file__read'}])
    finally:
        await brain.close()


async def test_rate_limit_cooldown_does_not_resend(tmp_path):
    brain, requests = brain_with_response(tmp_path, '', 429, {'retry-after': '3.1'})
    try:
        for _ in range(2):
            with pytest.raises(BrainUnavailable) as error:
                await brain.respond([], [])
            assert error.value.retry_after == 4
        assert len(requests) == 1
    finally:
        await brain.close()


@pytest.mark.parametrize('value', ['NaN', 'inf', None, 'garbage', '-1'])
def test_retry_after_is_bounded(value):
    assert GroqBrain.retry_seconds(value) == 1


def test_multiple_tools_form_one_assistant_turn():
    context = [{'type': 'function_call', 'call_id': x, 'name': 'file__read', 'arguments': '{}'} for x in ['a', 'b']]
    context += [{'type': 'function_call_output', 'call_id': x, 'output': '{}'} for x in ['a', 'b']]
    messages = GroqBrain._messages(context)
    assert [m['role'] for m in messages] == ['assistant', 'tool', 'tool']
    assert len(messages[0]['tool_calls']) == 2


async def test_mixed_domain_tools_include_browser_and_vision(tmp_path):
    runtime = Runtime(Config.load(tmp_path))
    try:
        selected = GroqBrain._select_tools([{'role': 'user', 'content': 'Fix Python project then open browser and click the page and inspect screen'}], runtime.registry.schemas())
        names = {t['name'] for t in selected}
        assert {'file__read', 'browser__personal__click', 'browser__personal__activate', 'vision__analyze'} <= names
    finally:
        await runtime.close()


async def test_complete_stream_usage_and_fragments(tmp_path):
    body = event({'content': 'Hello '}) + event({'content': 'June'}, 'stop')
    body += 'data: {"choices":[],"x_groq":{"usage":{"total_tokens":9}}}\n\ndata: [DONE]\n\n'
    brain, requests = brain_with_response(tmp_path, body)
    callback = AsyncMock()
    try:
        decision = await brain.respond_stream([], [], callback)
        assert decision.text == 'Hello June'
        assert callback.await_count == 2
        assert brain.usage == {'total_tokens': 9}
        assert 'reasoning_effort' not in requests[0]
    finally:
        await brain.close()


async def test_batch_failure_skips_later_action_and_history_is_complete(tmp_path):
    class Script(JuneBrain):
        async def respond(self, context, tools):
            if any(x.get('type') == 'function_call_output' for x in context):
                self.history = context[:]
                return Decision('Stopped after failure')
            return Decision(calls=[{'id': 'a', 'name': 'file__read', 'arguments': {'path': 'absent.txt'}},
                                   {'id': 'b', 'name': 'memory__remember', 'arguments': {'text': 'must not run'}}])
    brain = Script()
    runtime = Runtime(Config.load(tmp_path), brain)
    try:
        job = runtime.submit('Inspect the files')
        await runtime.jobs[job['id']]
        assert not runtime.store.list('memory')
        assert len([x for x in brain.history if x.get('type') == 'function_call']) == 2
        outputs = [json.loads(x['output']) for x in brain.history if x.get('type') == 'function_call_output']
        assert outputs[-1]['status'] == 'skipped'
    finally:
        await runtime.close()


async def test_bridge_claim_single_use_and_cancelled_request(tmp_path):
    runtime = Runtime(Config.load(tmp_path))
    bridge = runtime.personal_browser.bridge
    bridge.last_seen = time.time()
    try:
        task = asyncio.create_task(bridge.request('read', {'tab': 1}))
        item = await bridge.poll()
        with pytest.raises(ValueError, match='unclaimed'):
            bridge.complete(item['id'], {'result': {}})
        bridge.claim(item['id'])
        with pytest.raises(PermissionError):
            bridge.claim(item['id'])
        bridge.complete(item['id'], {'result': {'text': 'observed'}})
        assert await task == {'text': 'observed'}
        assert not bridge.pending and not bridge.claimed
        task = asyncio.create_task(bridge.request('click'))
        item = await bridge.poll()
        bridge.cancel_pending()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(PermissionError):
            bridge.claim(item['id'])
    finally:
        await runtime.close()


def test_speech_chunks_are_bounded_and_preserve_words():
    text = 'First sentence. ' + 'longword ' * 70 + 'x' * 500
    parts = list(chunks(text))
    assert parts[0] == 'First sentence.'
    assert max(map(len, parts)) <= 180
    assert ''.join(parts).replace(' ', '') == text.replace(' ', '')


async def test_sapi_selection_privacy_and_warm_worker(tmp_path, monkeypatch):
    config = Config.load(tmp_path)
    config.voice_enabled = True
    voice = WindowsSpeech(config, None)
    monkeypatch.setattr(voice, '_kokoro_available', lambda: True)
    voice._sapi_speak = AsyncMock()
    voice._ensure_kokoro = AsyncMock()
    await voice.speak('Hello')
    voice._sapi_speak.assert_awaited_once_with('Hello')
    voice._ensure_kokoro.assert_not_awaited()
    config.privacy = True
    await voice.speak('Private')
    assert voice._sapi_speak.await_count == 1


async def test_stop_preserves_idle_worker_but_kills_active_inference(tmp_path):
    voice = WindowsSpeech(Config.load(tmp_path), None)
    writer = SimpleNamespace(write=lambda _: None, drain=AsyncMock())
    process = SimpleNamespace(returncode=None, stdin=writer, kill=lambda: None, wait=AsyncMock())
    voice.kokoro_process = process
    await voice.stop_speaking()
    assert voice.kokoro_process is process
    voice.speaking = True
    await voice.stop_speaking()
    assert voice.kokoro_process is None
    process.wait.assert_awaited_once()


@pytest.mark.parametrize('text', ['open github and read the page', 'open youtube then play the video', 'search memory for project', 'open tabs'])
def test_router_defers_compound_or_local_requests(text):
    from june.browser_commands import resolve_browser_command
    assert resolve_browser_command(text) is None


async def test_read_current_page_reads_body(tmp_path):
    runtime = Runtime(Config.load(tmp_path))
    runtime.execute = AsyncMock(side_effect=[{'status': 'success', 'result': {'tab': 1, 'title': 'Fixture'}},
                                             {'status': 'success', 'result': {'text': 'Body text'}}])
    try:
        assert await runtime.commands.dispatch('read current page', 'test') == 'Body text'
        assert runtime.execute.call_args.args[1] == 'browser.personal.read'
        runtime.execute.reset_mock()
        assert await runtime.commands.dispatch('show the database table', 'test') is None
        runtime.execute.assert_not_awaited()
    finally:
        await runtime.close()


async def test_first_audio_deadline_falls_back_without_repeating_audio(tmp_path):
    config = Config.load(tmp_path)
    config.voice_enabled = True
    config.kokoro_first_audio_timeout = .1
    voice = WindowsSpeech(config, None)
    voice.active_backend = 'kokoro'
    voice._close_kokoro = AsyncMock()
    voice._sapi_speak = AsyncMock()
    await voice._watch_first_audio(0, 'Hello')
    voice._sapi_speak.assert_awaited_once_with('Hello')
    voice._sapi_speak.reset_mock()
    voice.first_audio_ms = 50
    await voice._watch_first_audio(0, 'Hello')
    voice._sapi_speak.assert_not_awaited()


async def test_gui_capture_failure_keeps_verification_gate(tmp_path, monkeypatch):
    from june.windows import Windows
    import sys
    config = Config.load(tmp_path)
    config.screen_enabled = True
    windows = Windows(config)
    observed = {'capture_id': 'a', 'observed_at': time.time(), 'monitor': 1, 'active': True,
                'image_hash': 'same', 'window': {'title': 'Fixture', 'handle': 1, 'rect': [0, 0, 100, 100]},
                'width': 100, 'height': 100, 'origin': [0, 0]}
    windows.last_capture = observed
    windows.capture = AsyncMock(side_effect=[observed, RuntimeError('capture unavailable')])
    clicked = []
    monkeypatch.setitem(sys.modules, 'pyautogui', SimpleNamespace(click=lambda *args: clicked.append(args)))
    with pytest.raises(RuntimeError, match='capture unavailable'):
        await windows.action('click', x=10, y=10, capture_id='a', expected_window='Fixture')
    assert clicked == [(10, 10)]
    with pytest.raises(ValueError, match='previous action'):
        await windows.action('click', capture_id='a', expected_window='Fixture')


def test_backend_preferences_validate_and_persist(tmp_path):
    from fastapi.testclient import TestClient
    from june.api import create_app
    runtime = Runtime(Config.load(tmp_path))
    app = create_app(runtime)
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + app.state.token}
        assert client.post('/api/preferences', headers=headers, json={'speech_backend': 'invalid'}).status_code == 400
        assert client.post('/api/preferences', headers=headers, json={'speech_backend': 'kokoro'}).status_code == 200
        assert Config.load(tmp_path).speech_backend == 'kokoro'


async def test_invalid_browser_arguments_rejected_before_prepare(tmp_path):
    runtime = Runtime(Config.load(tmp_path))
    runtime.personal_browser.prepare = AsyncMock()
    try:
        result = await runtime.execute('test', 'browser.personal.click', {'tab': 'wrong', 'selector': '#go'})
        assert result['status'] == 'failure'
        runtime.personal_browser.prepare.assert_not_awaited()
        assert not runtime.approvals
    finally:
        await runtime.close()


async def test_repeated_observation_is_allowed_within_step_budget(tmp_path):
    class Observer(JuneBrain):
        async def respond(self, context, tools):
            count = sum(x.get('type') == 'function_call_output' for x in context)
            return Decision('Observed three times') if count == 3 else Decision(calls=[
                {'id': str(count), 'name': 'file__list', 'arguments': {}}])
    runtime = Runtime(Config.load(tmp_path), Observer())
    try:
        job = runtime.submit('Inspect the directory repeatedly')
        await runtime.jobs[job['id']]
        assert runtime.store.get('job', job['id'])['status'] == 'completed'
    finally:
        await runtime.close()


async def test_groq_disconnect_before_text_can_retry(tmp_path):
    brain, _ = brain_with_response(tmp_path, '')
    await brain.close()
    def fail(request):
        raise httpx.ConnectError('synthetic')
    brain._client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(ConnectionError, match='connect'):
            await brain.respond([], [])
    finally:
        await brain.close()


async def test_groq_disconnect_after_text_is_not_retried(tmp_path):
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield event({'content': 'partial'}).encode()
            raise httpx.ReadError('synthetic')
    brain, _ = brain_with_response(tmp_path, '')
    await brain.close()
    brain._client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Interrupted())))
    try:
        with pytest.raises(BrainUnavailable, match='interrupted'):
            await brain.respond([], [])
    finally:
        await brain.close()


async def test_cooldown_does_not_consume_daily_budget(tmp_path):
    config = Config.load(tmp_path)
    config.provider = 'groq'
    runtime = Runtime(config)
    runtime.brain.retry_at = time.monotonic() + 10
    try:
        with pytest.raises(BrainUnavailable):
            await runtime.infer('test', [])
        assert not runtime.store.list('usage')
    finally:
        await runtime.close()
