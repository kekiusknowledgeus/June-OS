import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from june.config import Config
from june.runtime import Runtime
from june.brain import JuneBrain
from june.presence import memory_graph
from june.orb import clamp_position


class FakeBrain(JuneBrain):
    status = 'verified'
    external = True
    async def respond(self, context, tools):
        raise AssertionError('Presence must never call inference')


async def test_presence_priority_and_real_flags(tmp_path):
    r=Runtime(Config.load(tmp_path), FakeBrain())
    assert r.presence.snapshot()['state']=='MUTED'
    r.config.voice_enabled=True
    r.voice.state='wake listening'
    assert r.presence.snapshot()['state']=='IDLE'
    assert r.presence.snapshot()['microphone_state']=='active'
    r.voice.awake_until=time.monotonic()+30
    assert r.presence.snapshot()['state']=='LISTENING'
    r.voice.speaking=True
    assert r.presence.snapshot()['state']=='SPEAKING'
    a=r.store.put('approval',{'status':'pending'})
    assert r.presence.snapshot()['state']=='WAITING FOR APPROVAL'
    r.config.privacy=True
    p=r.presence.snapshot()
    assert p['state']=='PRIVACY MODE' and not p['speaking'] and p['input_level']==0
    assert p['microphone_state']=='off'
    r.config.privacy=False
    r.store.put('approval',{'status':'denied'},a['id'])
    r.voice.speaking=False
    r.voice.awake_until=0
    r.brain.status='unavailable:network'
    assert r.presence.snapshot()['state']=='OFFLINE'
    r.brain.status='unavailable:429:RESOURCE_EXHAUSTED'
    assert r.presence.snapshot()['state']=='BRAIN UNAVAILABLE'
    await r.close()


async def test_presence_tracks_job_tool_and_observation_lifecycle(tmp_path):
    r = Runtime(Config.load(tmp_path), FakeBrain())
    job = r.store.put('job', {'status': 'running', 'request': 'Fixture task'})
    worker = asyncio.create_task(asyncio.sleep(60))
    r.jobs[job['id']] = worker
    assert r.presence.snapshot()['state'] == 'THINKING'
    r.active_tools.append('project.run')
    assert r.presence.snapshot()['state'] == 'EXECUTING'
    assert r.presence.snapshot()['active_job'] == job['id']
    r.active_tools[:] = ['screen.capture']
    assert r.presence.snapshot()['state'] == 'OBSERVING'
    r.active_tools.clear()
    r.store.put('job', {'status': 'completed'}, job['id'])
    assert r.presence.snapshot()['state'] == 'MUTED'
    r.store.put('job', {'status': 'failed', 'error': 'Fixture task failure'}, job['id'])
    assert r.presence.snapshot()['state'] == 'ERROR'
    assert r.presence.snapshot()['error'] == 'Fixture task failure'
    r.voice.error = 'Fixture voice error'
    assert r.presence.snapshot()['state'] == 'ERROR'
    worker.cancel()
    await asyncio.gather(worker, return_exceptions=True)
    r.jobs.clear()
    await r.close()


async def test_graph_links_only_recorded_associations_and_no_inference(tmp_path):
    r=Runtime(Config.load(tmp_path),FakeBrain())
    p=await r.project_save('Fixture',str(tmp_path),{'important_files':['main.py']})
    memory=r.memory.remember('Renderer decision',category='decision',project=p['id'],people=['Example person'])
    r.memory.remember('Unrelated fact')
    graph=memory_graph(r)
    ids={n['id'] for n in graph['nodes']}
    assert any(n['kind']=='DECISION' for n in graph['nodes'])
    assert any(e['source']=='project:'+p['id'] and e['target']=='memory:'+memory['id'] for e in graph['edges'])
    assert all(e['source'] in ids and e['target'] in ids for e in graph['edges'])
    assert all(e['source_type']=='recorded metadata' for e in graph['edges'])
    assert not r.store.list('inference')
    await r.close()


def test_monitor_clamping_negative_origins_and_disconnection():
    screens=[(-1920,0,0,1080),(0,0,1920,1080)]
    assert clamp_position(-1800,100,112,screens)==(-1800,100)
    assert clamp_position(8000,100,112,screens)==(1808,100)
    assert clamp_position(-1800,100,112,[screens[1]])==(0,100)


def test_presence_api_config_validation_and_persistence(tmp_path):
    config=Config.load(tmp_path)
    app=__import__('june.api',fromlist=['create_app']).create_app(Runtime(config,FakeBrain()))
    with TestClient(app) as client:
        auth={'Authorization':'Bearer '+app.state.token}
        assert client.get('/api/presence').status_code==401
        assert client.get('/api/graph',headers=auth).status_code==200
        assert client.post('/api/presence/preferences',headers=auth,json={'orb_size':10}).status_code==400
        assert client.post('/api/presence/preferences',headers=auth,json={'privacy':False}).status_code==400
        assert client.post('/api/presence/preferences',headers=auth,json={'orb_x':-800,'orb_y':100,'orb_size':140,'orb_opacity':.8,'orb_click_through':True}).status_code==200
        reloaded=Config.load(tmp_path)
        assert reloaded.orb_x==-800 and reloaded.orb_size==140 and reloaded.orb_click_through
