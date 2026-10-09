from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import os


@dataclass
class Config:
    root: Path = field(default_factory=lambda: Path(os.environ.get("JUNE_ROOT", "D:/June")))
    provider: str = "june_v0"
    model: str = "gpt-4.1-mini"
    provider_daily_calls: int = 150
    hotkey: str = "Ctrl+Space"
    orb_enabled: bool = True
    orb_size: int = 112
    orb_opacity: float = .92
    orb_x: int | None = None
    orb_y: int | None = None
    orb_click_through: bool = False
    start_minimized: bool = False
    continue_automatically: bool = False
    speech_input_device: str = ""
    speech_output_device: str = ""
    speech_voice: str = ""
    local_url: str = "http://127.0.0.1:11434/v1"
    local_model: str = ""
    timezone: str = "Asia/Calcutta"
    port: int = 8765
    max_steps: int = 24
    task_timeout: int = 600
    tool_timeout: int = 90
    max_file_bytes: int = 1_000_000
    context_chars: int = 48000
    allowed_roots: list[str] = field(default_factory=list)
    projects_root: str = 'D:/Projects'
    allowed_workspace_roots: list[str] = field(default_factory=list)
    owner_mode: bool = False
    trusted_workspace_roots: list[str] = field(default_factory=list)
    trusted_apps: list[str] = field(default_factory=lambda: ['notepad','calculator','explorer','vscode'])
    trusted_browser_domains: list[str] = field(default_factory=lambda: ['*'])
    trusted_shell_categories: list[str] = field(default_factory=lambda: ['test','build','run','format','lint','dependencies','git-local'])
    trusted_external_services: dict = field(default_factory=dict)
    trusted_contacts: dict = field(default_factory=dict)
    browser_mode_default: str = 'personal'
    background_browser_mode: str = 'automation'
    privacy: bool = False
    screen_enabled: bool = False
    camera_enabled: bool = False
    voice_enabled: bool = False
    always_listen: bool = False
    quiet: bool = False
    automation_paused: bool = False
    personality: str = "I am June, Mayank's personal AI system. Calm, concise, capable, direct. Never invent observations or claim unverified success."

    @classmethod
    def load(cls, root=None):
        base = Path(root or os.environ.get("JUNE_ROOT", "D:/June")).resolve()
        path = base / "config.json"
        data = json.loads(path.read_text("utf-8")) if path.exists() else {}
        data.pop("root", None)
        # Old installations may still have hosted-provider settings on disk.
        # Migrate them to June V0 and persist that change without touching secrets.
        changed = data.get("provider") == "gemini"
        if changed:
            data["provider"] = "june_v0"
        for legacy_key in ("gemini_model", "provider_min_interval"):
            if legacy_key in data:
                data.pop(legacy_key)
                changed = True
        config = cls(root=base, **data)
        if not config.allowed_roots:
            config.allowed_roots = [str(base)]
        if 'allowed_workspace_roots' not in data:
            config.allowed_workspace_roots = [str(base)]
            if base == Path('D:/June').resolve():
                config.allowed_workspace_roots.append(str(Path('D:/Projects')))
        if 'projects_root' not in data and base != Path('D:/June').resolve():
            config.projects_root = str(base / 'workspace/projects')
        if base == Path('D:/June').resolve():
            if 'owner_mode' not in data: config.owner_mode = True
            if 'trusted_workspace_roots' not in data: config.trusted_workspace_roots = list(config.allowed_workspace_roots)
        for folder in ("data", "data/captures", "data/downloads", "workspace", "models", ".cache"):
            (base / folder).mkdir(parents=True, exist_ok=True)
        for folder in ("tokenizer", "config", "checkpoints", "weights", "training", "telemetry"):
            (base / "models/june" / folder).mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(base / ".cache/browsers"))
        os.environ.setdefault("HF_HOME", str(base / ".cache/huggingface"))
        if changed and path.exists():
            config.save()
        return config

    def save(self):
        data = asdict(self)
        data.pop("root")
        path = self.root / "config.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), "utf-8")
        tmp.replace(path)
