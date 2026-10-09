"""One truthful, inexpensive UI projection of host/runtime state."""
import time
import json


class JuneState:
    def __init__(self, runtime):
        self.runtime = runtime

    def snapshot(self):
        r = self.runtime
        v = r.voice
        jobs = r.store.list('job', 30)
        active = next((j for j in jobs if j['id'] in r.jobs and j.get('status') in {'running', 'waiting_for_permission'}), None)
        approval = next((a for a in r.store.list('approval', 20) if a.get('status') == 'pending'), None)
        provider = getattr(r.brain, 'status', 'configured_unverified')
        task_error = jobs[0].get('error') if jobs and jobs[0].get('status') == 'failed' and time.time() - jobs[0].get('updated_at', 0) < 12 else None
        speaking = bool(getattr(v, 'speaking', False)) and not r.config.privacy
        microphone = v.state in {'starting', 'listening', 'wake listening'} and r.config.voice_enabled and not r.config.privacy
        listening = microphone and (v.push_to_talk or v.awake_until > time.monotonic())
        state = 'IDLE'
        if r.config.privacy:
            state = 'PRIVACY MODE'
        elif approval:
            state = 'WAITING FOR APPROVAL'
        elif speaking:
            state = 'SPEAKING'
        elif listening:
            state = 'LISTENING'
        elif active:
            state = 'EXECUTING' if r.active_tools else 'THINKING'
            if any(t in {'screen.capture', 'vision.analyze'} for t in r.active_tools):
                state = 'OBSERVING'
        elif 'network' in provider:
            state = 'OFFLINE'
        elif provider.startswith(('unavailable', 'not_configured')):
            state = 'BRAIN UNAVAILABLE'
        elif v.error or v.state == 'unavailable' or task_error:
            state = 'ERROR'
        elif not microphone:
            state = 'MUTED'
        meter = getattr(v, 'output_meter', None)
        project = r.current.project()
        return {'state': state, 'observed_at': time.time(), 'provider': r.config.provider, 'model': r.inspector.get_model_info()['model'], 'brain_status': provider, 'voice_state': v.state, 'microphone_state': 'active' if microphone else 'off', 'listening': listening, 'speaking': speaking, 'thinking': state == 'THINKING', 'executing': state == 'EXECUTING', 'privacy_mode': r.config.privacy, 'screen_state': 'enabled' if r.config.screen_enabled and not r.config.privacy else 'off', 'network_state': 'unavailable' if 'network' in provider else 'not independently probed', 'current_project': {'id': project['id'], 'name': project['name'], 'goal': project.get('current_goal', '')} if project else None, 'current_task': active.get('request') if active else None, 'active_job': active['id'] if active else None, 'pending_approval': approval['id'] if approval else None, 'agent_state': r.agent_state, 'error': v.error or task_error or (provider if provider.startswith('unavailable') else None), 'input_level': getattr(v, 'input_level', 0) if microphone else 0, 'output_level': meter.level if meter and speaking else None, 'output_meter': meter.source if meter else 'unavailable; speaking follows SAPI engine state', 'active_app': None if r.config.privacy else getattr(r, 'foreground_app', None), 'orb': {k: getattr(r.config, 'orb_' + k) for k in ('enabled', 'size', 'opacity', 'x', 'y', 'click_through')}}


def memory_graph(runtime, limit=180):
    """Bounded record graph. Edges carry recorded provenance, never inferred neurons."""
    nodes, edges, seen = [], [], set()
    def add(id, kind, label, details):
        if id not in seen and len(nodes) < limit:
            seen.add(id)
            nodes.append({'id': id, 'kind': kind, 'label': runtime.vault.redact(label)[:100], 'details': json.loads(runtime.vault.redact(details))})
    def edge(a, b, relation):
        if a in seen and b in seen:
            edges.append({'source': a, 'target': b, 'relation': relation, 'source_type': 'recorded metadata'})
    projects = runtime.store.list('project', 25)
    for p in projects:
        add('project:' + p['id'], 'PROJECT', p['name'], p)
    rows = []
    for kind in ('memory', 'task', 'timeline'):
        for row in runtime.store.list(kind, 45):
            if row.get('status') == 'superseded':
                continue
            category = row.get('category', '').upper()
            cat = category if category in {'PERSON','IDEA','DECISION','KNOWLEDGE','NOTE'} else {'memory': 'MEMORY', 'task': 'TASK', 'timeline': 'EVENT'}[kind]
            node = kind + ':' + row['id']
            add(node, cat, row.get('text', row.get('title', row.get('summary', kind))), row)
            rows.append((node, row))
    for node, row in rows:
        if row.get('project'):
            edge('project:' + row['project'], node, 'project association')
        for person in row.get('people', [])[:5]:
            name = str(person)
            add('person:' + name, 'PERSON', name, {'source': node})
            edge(node, 'person:' + name, 'mentions')
        for other in row.get('conflicts', []):
            edge(node, 'memory:' + other, 'conflicts with')
        for other in row.get('dependencies', []):
            edge(node, 'task:' + other, 'depends on')
    for p in projects:
        for file in p.get('important_files', [])[:8]:
            key = 'file:' + p['id'] + ':' + file
            add(key, 'FILE', file, {'path': file, 'source': 'registered important file', 'project': p['name']})
            edge('project:' + p['id'], key, 'registered file')
    return {'nodes': nodes, 'edges': edges, 'limit': limit, 'scope': 'Bounded local records, not model neurons; only explicit associations are linked', 'observed_at': time.time()}
