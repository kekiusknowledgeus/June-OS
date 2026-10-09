from fastapi.testclient import TestClient
from june.api import create_app
from june.runtime import Runtime
from june.config import Config


def test_auth_origin_and_dashboard_records(tmp_path):
    app = create_app(Runtime(Config.load(tmp_path)))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/state").status_code == 401
        headers = {"Authorization": "Bearer " + app.state.token}
        assert client.get("/api/state", headers=headers).status_code == 200
        brain = client.get('/api/brain', headers=headers)
        assert brain.status_code == 200
        assert brain.json()['model']['supports_internal_inspection'] is False
        assert brain.json()['operations']['resources']['disk_free_gb'] >= 0
        assert client.get("/api/state", headers={**headers, "Origin": "https://evil.invalid"}).status_code == 403
        assert client.get("/api/state", headers={**headers, "Host": "evil.invalid"}).status_code == 403
        created = client.post("/api/tasks", json={"title": "Build June"}, headers=headers)
        assert created.status_code == 200
        assert client.get("/api/records/task", headers=headers).json()[0]["title"] == "Build June"
        assert client.post("/api/settings", json={"allowed_roots": ["C:/"]}, headers=headers).status_code == 400
        assert client.post("/api/settings", json={"privacy": True}, headers=headers).status_code == 200
        assert client.post("/api/screen", json={}, headers=headers).status_code == 403
