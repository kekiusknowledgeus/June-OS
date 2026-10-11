from contextlib import asynccontextmanager
import secrets
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .runtime import Runtime


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    session: str = Field(default="default", max_length=100)


class Approval(BaseModel):
    allow: bool
    remember: str | None = None
    scope_value: str | None = None


def create_app(runtime=None):
    runtime = runtime or Runtime()
    path = runtime.config.root / "data/api-token"
    token = path.read_text().strip() if path.exists() else secrets.token_urlsafe(32)
    if not path.exists():
        path.write_text(token)

    @asynccontextmanager
    async def lifespan(app):
        await runtime.start()
        yield
        await runtime.close()

    app = FastAPI(title="June local API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.runtime, app.state.token = runtime, token

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        hosts = {f"127.0.0.1:{runtime.config.port}", f"localhost:{runtime.config.port}", "testserver"}
        if request.headers.get("host") not in hosts:
            return JSONResponse({"error": "Invalid host"}, status_code=403)
        origin = request.headers.get("origin")
        bridge_request=request.url.path.startswith('/bridge/')
        if bridge_request:
            import re
            if request.client and request.client.host not in {'127.0.0.1','::1','testclient'}:
                return JSONResponse({'error':'Loopback required'},status_code=403)
            if origin and not re.fullmatch(r'chrome-extension://[a-p]{32}',origin):
                return JSONResponse({'error':'Extension origin required'},status_code=403)
            if request.method=='OPTIONS':
                return JSONResponse({},headers={'Access-Control-Allow-Origin':origin or 'null','Access-Control-Allow-Methods':'GET, POST','Access-Control-Allow-Headers':'Authorization, Content-Type'})
            if request.url.path!='/bridge/pair' and not runtime.personal_browser.bridge.authenticate(request.headers.get('authorization','').removeprefix('Bearer '),origin):
                return JSONResponse({'error':'Bridge authentication required'},status_code=401)
        if not bridge_request and origin and origin not in {f"http://127.0.0.1:{runtime.config.port}", f"http://localhost:{runtime.config.port}"}:
            return JSONResponse({"error": "Cross-origin request blocked"}, status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not secrets.compare_digest(supplied, token):
                return JSONResponse({"error": "Authentication required"}, status_code=401)
        if request.headers.get("transfer-encoding"):
            return JSONResponse({"error": "Chunked requests are not accepted"}, status_code=411)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"error": "Invalid content length"}, status_code=400)
        if size < 0 or size > 100000:
            return JSONResponse({"error": "Request too large"}, status_code=413)
        response = await call_next(request)
        if bridge_request and origin: response.headers['Access-Control-Allow-Origin']=origin
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            runtime.store.audit({"trigger": "authenticated_ui", "action": request.method + " " + request.url.path, "success": response.status_code < 400})
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; connect-src 'self'"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"error": runtime.vault.redact(str(exc))}, status_code=400)

    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"error": runtime.vault.redact(str(exc))}, status_code=403)

    @app.exception_handler(RuntimeError)
    async def unavailable(request, exc):
        return JSONResponse({"error": runtime.vault.redact(str(exc))}, status_code=503)

    @app.get("/")
    async def home():
        return FileResponse(Path(__file__).parent / "web/index.html")

    @app.get("/app.js")
    async def script():
        return FileResponse(Path(__file__).parent / "web/app.js")

    @app.get("/style.css")
    async def style():
        return FileResponse(Path(__file__).parent / "web/style.css")

    @app.get("/settings.js")
    async def settings_script():
        return FileResponse(Path(__file__).parent / "web/settings.js", media_type="text/javascript")

    @app.get('/brain.js')
    async def brain_script():
        return FileResponse(Path(__file__).parent / 'web/brain.js', media_type='text/javascript')

    @app.get('/brain.css')
    async def brain_style():
        return FileResponse(Path(__file__).parent / 'web/brain.css', media_type='text/css')

    @app.get('/api/startup')
    async def startup_state():
        from .startup import startup_path
        path = startup_path()
        return {'enabled': path.exists() and 'rem Managed by June' in path.read_text(errors='replace')}

    @app.get("/api/voice/devices")
    async def voice_devices():
        from .voice import available_devices
        return await available_devices()

    @app.get('/api/browser/status')
    async def browser_status():
        return runtime.personal_browser.bridge.status()

    @app.post('/api/browser/pair')
    async def browser_pairing():
        return runtime.personal_browser.bridge.pairing()

    @app.post('/api/browser/revoke')
    async def browser_revoke():
        bridge=runtime.personal_browser.bridge
        bridge.credentials={};bridge.last_seen=0;bridge.pair_code=None
        bridge.path.write_text('{}')
        bridge.cancel_pending()
        return {'revoked':True}

    @app.post('/bridge/pair')
    async def pair_extension(request: Request, values: dict):
        if request.headers.get('origin') != 'chrome-extension://'+values.get('extension',''):
            raise PermissionError('Pairing origin mismatch')
        return runtime.personal_browser.bridge.pair(values.get('code',''),values.get('extension',''))

    @app.get('/bridge/poll')
    async def bridge_poll():
        if runtime.config.privacy: raise PermissionError('Privacy mode blocks browser control')
        return await runtime.personal_browser.bridge.poll()

    @app.post('/bridge/result')
    async def bridge_result(values: dict):
        runtime.personal_browser.bridge.complete(values['id'],values)
        return {'accepted':True}

    @app.post('/bridge/claim')
    async def bridge_claim(values: dict):
        runtime.personal_browser.bridge.claim(values.get('id'))
        return {'active':True}

    @app.get('/api/trust')
    async def trust_settings():
        keys=('owner_mode','trusted_workspace_roots','trusted_apps','trusted_browser_domains','trusted_shell_categories','trusted_external_services','trusted_contacts','browser_mode_default','background_browser_mode')
        return {**{k:getattr(runtime.config,k) for k in keys},'rules':runtime.trust.rules}

    @app.post('/api/trust')
    async def save_trust(values: dict):
        from .security import Paths
        current=await trust_settings()
        if set(values)-set(current) or 'rules' in values: raise ValueError('Unknown trust setting')
        for key,value in values.items():
            if type(value)!=type(current[key]): raise ValueError('Invalid trust setting type')
            if isinstance(value,list) and any(not isinstance(x,str) for x in value): raise ValueError('Expected strings')
            if key=='trusted_workspace_roots':
                for root in value:
                    path=Paths(runtime.config).resolve(root)
                    if not Path(root).is_absolute() or path.parent==path: raise ValueError('An explicit workspace is required')
            if key in {'trusted_external_services','trusted_contacts'}:
                if any(not isinstance(v,dict) or any(x not in {'ASK','ALWAYS_ALLOW','DENY'} for x in v.values()) for v in value.values()): raise ValueError('Invalid service policy')
            if key in {'browser_mode_default','background_browser_mode'} and value not in {'personal','automation'}: raise ValueError('Invalid browser mode')
        for key,value in values.items(): setattr(runtime.config,key,value)
        runtime.config.save()
        return await trust_settings()

    @app.post('/api/trust/revoke/{id}')
    async def revoke_trust(id: str):
        runtime.trust.revoke(id)
        return {'revoked':True}

    @app.get("/api/state")
    async def state():
        return {"presence": runtime.presence.snapshot(), "health": await runtime.health(), "jobs": runtime.store.list("job", 30), "messages": list(reversed(runtime.store.list("message", 60))), "approvals": [a for a in runtime.store.list("approval") if a["status"] == "pending"], "notifications": runtime.store.list("notification", 30), "current": runtime.current.snapshot(), "ui_requests": runtime.store.list("ui_request", 5)}

    @app.get("/api/brain")
    async def brain():
        return {"model": runtime.inspector.get_model_info(), "operations": runtime.inspector.get_runtime_metrics(), "presence": runtime.presence.snapshot()}

    @app.get('/api/presence')
    async def presence():
        return runtime.presence.snapshot()

    @app.get('/api/graph')
    async def graph():
        from .presence import memory_graph
        return memory_graph(runtime)

    @app.post('/api/presence/preferences')
    async def presence_preferences(values: dict):
        boolean = {'orb_enabled', 'orb_click_through'}
        ranges = {'orb_size': (80, 240), 'orb_opacity': (.3, 1), 'orb_x': (-32000, 32000), 'orb_y': (-32000, 32000)}
        if set(values) - boolean - set(ranges):
            raise ValueError('Unknown presence preference')
        for key, value in values.items():
            if key in boolean and not isinstance(value, bool):
                raise ValueError('Invalid presence switch')
            if key in ranges:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not ranges[key][0] <= value <= ranges[key][1]:
                    raise ValueError('Presence preference is out of range')
                if key != 'orb_opacity' and not isinstance(value, int):
                    raise ValueError('Position and size must be whole numbers')
        for key, value in values.items():
            setattr(runtime.config, key, value)
        runtime.config.save()
        return runtime.presence.snapshot()['orb']

    @app.get("/api/timeline")
    async def timeline(project: str | None = None):
        return runtime.timeline.query(project, limit=100)

    @app.post("/api/context/window")
    async def context_window(values: dict):
        # Only the authenticated desktop captures this before its overlay takes focus.
        if not runtime.config.privacy:
            runtime.current.set("active_window", {k: values[k] for k in ("title", "handle", "pid", "rect", "observed_at") if k in values}, "desktop summon observation")
            await runtime.projects.suggest_from_window(values)
        return {"status": "recorded"}

    @app.post("/api/pause")
    async def pause():
        await runtime.pause_all()
        return {"status": "paused"}

    @app.post("/api/resume/{id}")
    async def resume(id: str):
        return runtime.resume_job(id)

    @app.post("/api/shutdown")
    async def shutdown():
        return runtime.submit("shut down June")

    @app.post("/api/startup")
    async def startup(values: dict):
        from .startup import set_startup
        if not isinstance(values.get("enabled"), bool) or values.get("confirm") != "change June login startup":
            raise ValueError("Explicit startup confirmation is required")
        return set_startup(runtime.config, values["enabled"])

    @app.post("/api/preferences")
    async def preferences(values: dict):
        allowed = {"hotkey", "speech_input_device", "speech_output_device", "speech_voice", "speech_backend"}
        if set(values) - allowed or any(not isinstance(v, str) or len(v) > 200 for v in values.values()):
            raise ValueError("Invalid preference")
        if "hotkey" in values:
            from .hotkey import parse_hotkey
            parse_hotkey(values["hotkey"])
        if 'speech_backend' in values and values['speech_backend'] not in {'sapi', 'kokoro', 'auto'}:
            raise ValueError('Choose sapi, kokoro, or auto')
        if any(key.startswith('speech_') for key in values):
            await runtime.voice.stop_speaking()
            await runtime.voice._close_speakers()
        for key, value in values.items():
            setattr(runtime.config, key, value)
        runtime.config.save()
        return {"status": "saved", "note": "Restart June to apply hotkey changes; restart voice to apply audio preferences"}

    @app.post("/api/chat")
    async def chat(message: Message):
        return runtime.submit(message.text, message.session)

    @app.post("/api/approve/{id}")
    async def approve(id: str, decision: Approval):
        runtime.approve(id, decision.allow, decision.remember, decision.scope_value)
        return {"status": "recorded"}

    @app.post("/api/cancel/{id}")
    async def cancel(id: str):
        return await runtime.cancel(id)

    @app.post("/api/stop")
    async def stop():
        await runtime.cancel_all()
        await runtime.voice.stop_speaking()
        return {"status": "stopped"}

    @app.post("/api/settings")
    async def settings(values: dict):
        return await runtime.settings(values)

    @app.post("/api/voice/talk")
    async def talk():
        await runtime.voice.start(push_to_talk=True)
        return {"status": runtime.voice.state}

    @app.get("/api/records/{kind}")
    async def records(kind: str):
        if kind == "audit":
            return runtime.store.audits()
        if kind not in {"memory", "task", "project", "schedule", "watch", "notification", "event"}:
            raise HTTPException(404)
        return runtime.store.list(kind)

    @app.post("/api/tasks")
    async def task(values: dict):
        return await runtime.task_save(**values)

    @app.post("/api/projects")
    async def project(values: dict):
        return await runtime.project_save(**values)

    @app.get('/api/projects/discover')
    async def discover_projects():
        return await runtime.projects.discover()

    @app.post('/api/projects/action')
    async def project_action(values: dict):
        action=values.get('action')
        if action not in {'create','register','unregister','switch','inspect'}:
            raise ValueError('Unknown project action')
        # Mutations are queued through the same exact-action approval path as chat.
        return runtime.submit_project_action(action,values.get('arguments',{}))

    @app.post("/api/memory")
    async def memory(values: dict):
        return runtime.memory.remember(runtime.vault.redact(values["text"]), values.get("category", "knowledge"), explicit=True, confidence=1, source="user_dashboard")

    @app.delete("/api/memory/{id}")
    async def forget(id: str):
        runtime.store.delete("memory", id)
        return {"status": "forgotten"}

    @app.post("/api/memory/{id}/manage")
    async def manage_memory(id: str, values: dict):
        return runtime.memory.manage(id, **values)

    @app.post("/api/schedules")
    async def schedule(values: dict):
        return await runtime.schedule(**values)

    @app.post("/api/schedules/{id}/disable")
    async def disable_schedule(id: str):
        if not runtime.store.get("schedule", id):
            raise HTTPException(404)
        return runtime.store.put("schedule", {"enabled": False}, id)

    @app.get("/api/briefing")
    async def briefing():
        return await runtime.briefing()

    @app.post("/api/screen")
    async def screen():
        return await runtime.windows.capture()

    return app
