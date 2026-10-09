"""Small structured app adapters; executable names never come from model text."""
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from .security import Risk
from .tools import S


class Applications:
    def __init__(self, runtime):
        self.runtime = runtime

    async def open_project(self, project, application="explorer"):
        p = self.runtime.current.project(project)
        if not p:
            raise ValueError("Project is not registered or ambiguous")
        root = self.runtime.files.paths.resolve(p["root_path"])
        if not root.is_dir():
            raise FileNotFoundError("Project folder is unavailable")
        if application == "explorer":
            argv = ["explorer.exe", str(root)]
        elif application == "vscode":
            exe = shutil.which("code")
            if not exe:
                candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Microsoft VS Code/Code.exe", Path("C:/Program Files/Microsoft VS Code/Code.exe")]
                exe = next((str(c) for c in candidates if c.is_file()), None)
            if not exe:
                raise FileNotFoundError("VS Code is not installed or discoverable")
            # Prefer executable over code.cmd; never execute an arbitrary shell string.
            if exe.lower().endswith(".cmd"):
                candidate = Path(exe).parent.parent / "Code.exe"
                if not candidate.is_file():
                    raise FileNotFoundError("VS Code executable could not be resolved")
                exe = str(candidate)
            argv = [exe, str(root)]
        elif application == "unreal":
            files = list(root.glob("*.uproject"))
            if len(files) != 1:
                raise ValueError("Project needs exactly one .uproject file")
            exe = Path("D:/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe")
            if not exe.is_file():
                raise FileNotFoundError("Unreal Editor executable unavailable at the registered path")
            argv = [str(exe), str(files[0])]
        else:
            raise ValueError("Choose explorer, vscode or unreal")
        proc = subprocess.Popen(argv)
        self.runtime.current.set("current_project", p["id"], "explicit project open")
        return {"status": "launch_requested", "project": p["name"], "application": application, "pid": proc.pid, "root_path": str(root)}

    async def run_project(self, project, command, expected_command=None, expected_cwd=None):
        p = self.runtime.current.project(project)
        if not p:
            raise ValueError("Project unavailable")
        commands = p.get("commands", {})
        if command not in commands:
            raise ValueError("Unknown project command; inspect project commands first")
        if expected_command is None or commands[command] != expected_command or p["root_path"] != expected_cwd:
            raise PermissionError("Project command changed or lacks a host-bound preview; inspect and approve again")
        self.runtime.current.set("current_project", p["id"], "explicit project command")
        return await self.runtime.shell.run(commands[command], p["root_path"], min(self.runtime.config.tool_timeout, 300))

    async def inspect_project(self, project):
        p = self.runtime.current.project(project)
        if not p:
            raise ValueError("Project unavailable")
        git = await self.runtime.shell.git("status", p["root_path"])
        root = self.runtime.files.paths.resolve(p["root_path"])
        markers = [name for name in ("pyproject.toml", "package.json", "CMakeLists.txt", "Cargo.toml", "Makefile") if (root / name).exists()]
        markers += [f.name for f in root.glob("*.uproject")]
        detected = await self.runtime.projects.detect_project_type(str(root))
        return {"project": p, "git": git, "build_markers": detected['evidence'], 'detection':detected, 'files':await self.runtime.files.list(str(root)), "recent_events": self.runtime.timeline.query(p["id"], limit=15)}

    def register(self, registry):
        registry.add("project.open", "Open a registered project via structured Explorer/VS Code/Unreal adapter", self.open_project, {"project": S, "application": S}, ["project"], Risk.LOCAL)
        registry.add("project.inspect", "Inspect project Git status, build markers, commands and timeline", self.inspect_project, {"project": S}, ["project"])
        registry.add("project.run", "Run one registered project command; host binds the preview to exact command and working directory", self.run_project, {"project": S, "command": S, "expected_command": S, "expected_cwd": S}, ["project", "command"], Risk.SENSITIVE)
