import asyncio
import json
import pytest
from june.config import Config
from june.runtime import Runtime
from june.brain import JuneBrain, Decision
from june.errors import BrainUnavailable
from june.workflows import Workflow
from june.hotkey import parse_hotkey


class Offline(JuneBrain):
    external = True
    async def respond(self, context, tools):
        raise BrainUnavailable('Synthetic provider outage')


async def finish(r, text):
    job = r.submit(text)
    await asyncio.wait_for(r.jobs[job['id']], 8)
    return r.store.get('job', job['id'])


async def test_offline_context_memory_restart(tmp_path):
    cfg = Config.load(tmp_path)
    cfg.privacy = True
    r = Runtime(cfg, Offline())
    p = await r.project_save('Fixture', str(tmp_path), {'commands': {'test': 'pytest'}})
    r.current.set('current_project', p['id'], 'test selection')
    result = await finish(r, 'remember that Fixture uses deterministic tests')
    assert result['status'] == 'completed'
    assert 'Remembered' in result['response']
    assert (await finish(r, 'status'))['status'] == 'completed'
    await r.on_voice('Remember that tomorrow I want to work on Fixture addition tests.')
    await asyncio.gather(*list(r.jobs.values()))
    assert r.store.list('task')
    r.current.set('recent_command', {'arguments': {'project': p['id'], 'command': 'test'}, 'returncode': 1}, 'observed test')
    r.current.set('active_window', {'title': 'Fixture'}, 'test')
    await r.close()
    r = Runtime(cfg, Offline())
    assert r.current.project()['id'] == p['id']
    assert r.current.value('recent_command')['returncode'] == 1
    assert r.current.snapshot()['active_window']['stale']
    assert (await finish(r, 'find deterministic tests'))['status'] == 'completed'
    assert 'Fixture addition tests' in (await finish(r, 'What should I work on today?'))['response']
    assert not r.store.list('inference')
    await r.close()


async def test_provider_outage_preserves_local_commands(tmp_path):
    r = Runtime(Config.load(tmp_path), Offline())
    assert (await finish(r, 'Explain a synthetic concept'))['status'] == 'waiting_external'
    assert (await finish(r, 'what needs my attention'))['status'] == 'completed'
    assert (await finish(r, 'show me your brain'))['status'] == 'completed'
    assert r.store.list('ui_request')
    await r.close()


def test_workflow_requires_check_after_latest_edit():
    flow = Workflow('coding')
    ok = {'status': 'success', 'result': {'returncode': 0}}
    flow.observe('file.write', {'path': 'main.py'}, ok)
    flow.observe('shell.run', {'command': 'echo success'}, ok)
    assert flow.completion_problem()
    flow.observe('shell.run', {'command': 'echo pytest'}, ok)
    assert flow.completion_problem()
    flow.observe('shell.run', {'command': 'python -m pytest tests'}, ok)
    assert not flow.completion_problem()
    flow.observe('file.write', {'path': 'main.py'}, ok)
    assert flow.completion_problem()
    flow.observe('shell.run', {'command': 'python -m pytest'}, {'status': 'success', 'result': {'returncode': 1}})
    assert flow.completion_problem()


async def test_undo_refuses_newer_user_edit(tmp_path):
    r = Runtime(Config.load(tmp_path), Offline())
    change = await r.files.write('fixture.txt', 'June content')
    (tmp_path / 'fixture.txt').write_text('New user content')
    with pytest.raises(ValueError, match='newer work'):
        await r.files.undo(change['change_id'])
    assert (tmp_path / 'fixture.txt').read_text() == 'New user content'
    (tmp_path / 'fixture.txt').write_text('June content')
    await r.files.undo(change['change_id'])
    assert not (tmp_path / 'fixture.txt').exists()
    await r.close()


async def test_memory_conflict_resolution_preserves_provenance(tmp_path):
    r = Runtime(Config.load(tmp_path), Offline())
    a = r.memory.remember('Fixture uses Python', subject='fixture-language', source='user1', explicit=True)
    b = r.memory.remember('Fixture uses Rust', subject='fixture-language', source='user2', explicit=True)
    assert a['id'] in b['conflicts']
    r.memory.manage(b['id'], 'resolve', other_id=a['id'])
    assert set(r.store.get('memory', b['id'])['sources']) == {'user1', 'user2'}
    assert all(m['id'] != a['id'] for m in r.memory.search('Fixture language'))
    await r.close()


def test_hotkey_validation():
    assert parse_hotkey('Ctrl + Space') == (0x4002, 0x20)
    assert parse_hotkey('Ctrl+Shift+F12')[1] == 0x7B
    with pytest.raises(ValueError):
        parse_hotkey('Ctrl+Invalid')


async def test_gui_stale_capture_and_verification_gate(tmp_path, monkeypatch):
    r = Runtime(Config.load(tmp_path), Offline())
    r.config.screen_enabled = True
    r.windows.pending_verification = 'unreviewed-after.png'
    with pytest.raises(ValueError, match='previous action'):
        await r.windows.action('click', capture_id='old', expected_window='Fixture')
    r.windows.pending_verification = None
    with pytest.raises(ValueError, match='stale'):
        await r.windows.action('click', capture_id='old', expected_window='Fixture')
    import time
    original = {'capture_id': 'a', 'observed_at': time.time(), 'monitor': 1, 'active': True, 'image_hash': 'abc', 'window': {'title': 'Fixture', 'handle': 1, 'rect': [0,0,100,100]}}
    r.windows.last_capture = original
    async def changed(*args):
        return {**original, 'image_hash': 'changed'}
    monkeypatch.setattr(r.windows, 'capture', changed)
    with pytest.raises(ValueError, match='Screen or target'):
        await r.windows.action('click', capture_id='a', expected_window='Fixture')
    await r.close()


async def test_pause_cancels_permission_and_resumes_fresh(tmp_path):
    class Writer(JuneBrain):
        async def respond(self, context, tools):
            return Decision(calls=[{'name': 'file__write', 'id': 'one', 'arguments': {'path': 'fixture.txt', 'text': 'test'}}])
    r = Runtime(Config.load(tmp_path), Writer())
    job = r.submit('Write fixture')
    for _ in range(100):
        if r.approvals:
            break
        await asyncio.sleep(.01)
    old = next(iter(r.approvals))
    await r.pause_all()
    assert r.store.get('job', job['id'])['status'] == 'paused'
    assert not (tmp_path / 'fixture.txt').exists()
    resumed = r.resume_job(job['id'])
    for _ in range(100):
        if r.approvals:
            break
        await asyncio.sleep(.01)
    assert next(iter(r.approvals)) != old
    with pytest.raises(ValueError):
        r.approve(old, True)
    await r.cancel(resumed['id'])
    await r.close()


async def test_registered_command_change_invalidates_approval(tmp_path):
    r = Runtime(Config.load(tmp_path), Offline())
    p = await r.project_save('Fixture', str(tmp_path), {'commands': {'test': 'echo original'}})
    job = r.store.put('job', {'status': 'running', 'request': 'test'})
    task = asyncio.create_task(r.execute(job['id'], 'project.run', {'project': p['id'], 'command': 'test'}))
    for _ in range(100):
        if r.approvals:
            break
        await asyncio.sleep(.01)
    r.store.put('project', {'commands': {'test': 'echo changed'}}, p['id'])
    r.approve(next(iter(r.approvals)), True)
    assert (await task)['status'] == 'permission_denied'
    await r.close()


async def test_speech_failure_does_not_lose_completed_response(tmp_path, monkeypatch):
    r = Runtime(Config.load(tmp_path), Offline())
    async def fail(text):
        raise RuntimeError('Disconnected output')
    monkeypatch.setattr(r.voice, 'speak', fail)
    result = await finish(r, 'status')
    assert result['status'] == 'completed'
    assert result['speech_warning']
    await r.close()


def test_database_lock_failure_recovers_without_partial_record(tmp_path):
    import sqlite3
    from june.store import Store
    path = tmp_path / 'locked.db'
    store = Store(path)
    store.db.execute('PRAGMA busy_timeout=25')
    rival = sqlite3.connect(path)
    rival.execute('BEGIN IMMEDIATE')
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        store.put('task', {'title': 'Must not be saved'}, 'failed')
    rival.rollback()
    rival.close()
    assert store.get('task', 'failed') is None
    assert store.put('task', {'title': 'Recovered'}, 'ok')['title'] == 'Recovered'
    store.close()


async def test_push_to_talk_returns_to_opted_in_wake_mode(tmp_path):
    from june.voice import WindowsSpeech
    cfg = Config.load(tmp_path)
    cfg.voice_enabled = cfg.always_listen = True
    voice = WindowsSpeech(cfg, None)
    voice.push_to_talk = True
    await voice._finish_ptt()
    assert voice.state == 'wake listening'
    assert not voice.push_to_talk
    cfg.privacy = True
    await voice._finish_ptt()
    assert voice.state == 'muted'


async def test_control_response_is_visible_in_conversation(tmp_path):
    r = Runtime(Config.load(tmp_path), Offline())
    result = await finish(r, 'pause everything')
    assert result['status'] == 'completed'
    assert any(m['role'] == 'assistant' and 'Paused' in m['content'] for m in r.store.list('message'))
    assert (await finish(r, 'resume everything'))['status'] == 'completed'
    assert (await finish(r, 'stop'))['status'] == 'completed'
    await r.close()
