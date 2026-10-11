import asyncio
from dataclasses import dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import subprocess
import uuid
import base64
from typing import Callable
import psutil
from .security import Risk, Paths


@dataclass
class Tool:
    name: str
    description: str
    function: Callable
    properties: dict
    required: list[str]
    risk: Risk = Risk.OBSERVE
    external: bool = False
    sensor: str = ""

    def schema(self):
        return {"type": "function", "name": self.name.replace(".", "__"), "description": self.description, "parameters": {"type": "object", "properties": self.properties, "required": self.required, "additionalProperties": False}, "strict": False}


class Registry:
    def __init__(self):
        self.tools = {}

    def add(self, name, description, function, properties=None, required=None, risk=Risk.OBSERVE, external=False, sensor=""):
        if name in self.tools:
            raise ValueError("Duplicate tool")
        self.tools[name] = Tool(name, description, function, properties or {}, required or [], risk, external, sensor)

    def get(self, name):
        return self.tools[name.replace("__", ".")]

    def schemas(self):
        return [t.schema() for t in self.tools.values()]

    def validate(self, name, args):
        tool = self.get(name)
        if not isinstance(args, dict) or set(args) - set(tool.properties) or any(k not in args for k in tool.required):
            raise ValueError("Invalid tool arguments")
        types = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list}
        for key, value in args.items():
            kind = tool.properties[key].get("type")
            if kind in types and (not isinstance(value, types[kind]) or (kind == "integer" and isinstance(value, bool))):
                raise ValueError(f"Invalid type for {key}")
            if kind == "array" and (len(value) > 100 or any(not isinstance(x, str) for x in value)):
                raise ValueError("Invalid string array")
        return tool

    async def execute(self, name, args):
        tool = self.validate(name, args)
        return await tool.function(**args)


S = {"type": "string"}
N = {"type": "integer"}
B = {"type": "boolean"}
O = {"type": "object"}
A = {"type": "array", "items": S}


class FileTools:
    def __init__(self, config):
        self.config, self.paths = config, Paths(config)
        self.backups = config.root / "data/backups"
        self.backups.mkdir(parents=True, exist_ok=True)

    def changes(self):
        records = []
        for path in sorted(self.backups.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            item = json.loads(path.read_text("utf-8"))
            records.append({k: v for k, v in item.items() if k not in {"previous","previous_bytes"}})
        return records

    async def list(self, path="."):
        p = self.paths.resolve(path)
        return [{"name": c.name, "directory": c.is_dir(), "bytes": c.stat().st_size} for c in list(p.iterdir())[:500] if not c.name.startswith(".env")]

    async def read(self, path):
        p = self.paths.resolve(path)
        if p.stat().st_size > self.config.max_file_bytes:
            raise ValueError("File exceeds read size limit")
        raw = p.read_bytes()
        if b"\0" in raw:
            raise ValueError("Binary file; use an appropriate media tool")
        return {"path": str(p), "text": raw.decode("utf-8"), "sha256": hashlib.sha256(raw).hexdigest()}

    async def write(self, path, text, expected_sha256=None, append=False):
        p = self.paths.resolve(path)
        if len(text.encode()) > self.config.max_file_bytes:
            raise ValueError("Write exceeds size limit")
        previous = None
        if p.exists():
            old = await self.read(path)
            previous = old["text"]
            if not expected_sha256 or old["sha256"] != expected_sha256:
                raise ValueError("Existing file requires matching expected_sha256 from a fresh read")
            if append:
                text = old["text"] + text
        if len(text.encode()) > self.config.max_file_bytes:
            raise ValueError('Result exceeds write size limit')
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".june-tmp")
        if tmp.exists():
            raise FileExistsError("Temporary write path already exists")
        change_id = uuid.uuid4().hex
        record = {"id": change_id, "path": str(p), "previous": previous, "previous_hash": hashlib.sha256(previous.encode()).hexdigest() if previous is not None else None, "after_hash": hashlib.sha256(text.encode()).hexdigest(), "created_at": time.time(), "status": "prepared"}
        history = self.backups / (change_id + ".json")
        history.write_text(json.dumps(record), "utf-8")
        with tmp.open("x", encoding="utf-8", newline="") as output:
            output.write(text)
        tmp.replace(p)
        record["status"] = "applied"
        history.write_text(json.dumps(record), "utf-8")
        return {"path": str(p), "bytes": p.stat().st_size, "change_id": change_id, "undo_available": True}

    async def create_file(self, path, text=''):
        if self.paths.resolve(path).exists():
            raise FileExistsError('Create never overwrites an existing file')
        return await self.write(path,text)

    async def edit_file(self, path, old_text, new_text, expected_sha256):
        if not old_text:
            raise ValueError('Patch must identify nonempty existing text')
        current=await self.read(path)
        if current['sha256']!=expected_sha256 or current['text'].count(old_text)!=1:
            raise ValueError('Stale or ambiguous patch; read the file and choose one exact match')
        return await self.write(path,current['text'].replace(old_text,new_text,1),expected_sha256)

    async def append_file(self, path, text, expected_sha256):
        return await self.write(path,text,expected_sha256,append=True)

    async def copy_file(self, source, destination):
        return await self.transfer(source,destination)

    async def move_file(self, source, destination):
        return await self.transfer(source,destination,move=True)

    async def rename_file(self, path, name):
        if Path(name).name!=name or name in {'.','..'} or '/' in name or '\\' in name:
            raise ValueError('Rename requires one filename, not a path')
        return await self.transfer(path,str(self.paths.resolve(path).with_name(name)),move=True)

    async def undo(self, change_id):
        if not isinstance(change_id, str) or len(change_id) != 32 or not all(c in "0123456789abcdef" for c in change_id):
            raise ValueError("Invalid change identifier")
        manifest = self.backups / (change_id + ".json")
        record = json.loads(manifest.read_text("utf-8"))
        if record["status"] != "applied":
            raise ValueError("Change is unavailable for undo")
        operation=record.get('operation','write')
        if operation in {'copy','move','delete'}:
            source=self.paths.resolve(record['source'])
            if operation=='delete':
                if source.exists(): raise ValueError('A newer file occupies the deleted path; undo refused')
                with source.open('xb') as output: output.write(base64.b64decode(record['previous_bytes']))
            else:
                destination=self.paths.resolve(record['path'])
                if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest()!=record['after_hash']:
                    raise ValueError('Destination changed; undo refused to preserve newer work')
                if operation=='move':
                    if source.exists(): raise ValueError('Original path has newer content; undo refused')
                    shutil.move(str(destination),str(source))
                else: destination.unlink()
            record['status']='undone'
            manifest.write_text(json.dumps(record),'utf-8')
            return {'operation':operation,'undone':True,'path':str(source)}
        p = self.paths.resolve(record["path"])
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != record["after_hash"]:
            raise ValueError("File changed since June's edit; undo refused to preserve newer work")
        if record["previous"] is None:
            p.unlink()
        else:
            tmp = p.with_name(p.name + ".june-undo")
            with tmp.open("x", encoding="utf-8", newline="") as output:
                output.write(record["previous"])
            tmp.replace(p)
        record["status"] = "undone"
        manifest.write_text(json.dumps(record), "utf-8")
        return {"path": str(p), "restored": record["previous"] is not None, "removed_new_file": record["previous"] is None}

    async def mkdir(self, path):
        p = self.paths.resolve(path)
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    async def transfer(self, source, destination, move=False):
        a, b = self.paths.resolve(source), self.paths.resolve(destination)
        if b.exists() or not a.is_file():
            raise ValueError("Only individual files; destination must not exist")
        b.parent.mkdir(parents=True, exist_ok=True)
        change_id=uuid.uuid4().hex
        record={'id':change_id,'operation':'move' if move else 'copy','source':str(a),'path':str(b),'after_hash':hashlib.sha256(a.read_bytes()).hexdigest(),'created_at':time.time(),'status':'prepared'}
        history=self.backups/(change_id+'.json')
        history.write_text(json.dumps(record),'utf-8')
        if move:
            # Windows rename fails if another file appeared at the destination.
            a.rename(b)
        else:
            with a.open('rb') as source_file, b.open('xb') as destination_file:
                shutil.copyfileobj(source_file,destination_file)
        record['status']='applied'
        history.write_text(json.dumps(record),'utf-8')
        return {"destination": str(b),'change_id':change_id,'undo_available':True}

    async def delete(self, path):
        p = self.paths.resolve(path)
        if not p.is_file():
            raise ValueError("Recursive/directory deletion is not supported")
        if p.stat().st_size>self.config.max_file_bytes:
            raise ValueError('File exceeds reversible-delete size limit')
        change_id=uuid.uuid4().hex
        record={'id':change_id,'operation':'delete','source':str(p),'path':str(p),'previous_bytes':base64.b64encode(p.read_bytes()).decode(),'created_at':time.time(),'status':'prepared'}
        history=self.backups/(change_id+'.json')
        history.write_text(json.dumps(record),'utf-8')
        p.unlink()
        record['status']='applied'
        history.write_text(json.dumps(record),'utf-8')
        return {"deleted": str(p),'change_id':change_id,'undo_available':True}

    async def search(self, path=".", pattern="*", text=None):
        root = self.paths.resolve(path)
        found = []
        scanned = 0
        for directory, dirs, files in os.walk(root, followlinks=False):
            scanned += 1
            if scanned > 10000:
                break
            def searchable(name):
                child=Path(directory)/name
                if name.startswith('.') or name=='node_modules' or child.is_symlink(): return False
                try: self.paths.resolve(child)
                except PermissionError: return False
                return True
            dirs[:] = [d for d in dirs if searchable(d)]
            for name in files:
                if not fnmatch.fnmatch(name, pattern):
                    continue
                p = Path(directory) / name
                try:
                    self.paths.resolve(p)
                    if text is not None:
                        result = await self.read(str(p))
                        lines = [{"line": i, "text": line[:500]} for i, line in enumerate(result["text"].splitlines(), 1) if text.lower() in line.lower()][:20]
                        if not lines:
                            continue
                        found.append({"path": str(p), "matches": lines})
                    else:
                        found.append({"path": str(p)})
                except (PermissionError, ValueError, OSError, UnicodeError):
                    continue
                if len(found) >= 100:
                    return found
        return found

    async def metadata(self, path):
        p = self.paths.resolve(path)
        st = p.stat()
        return {"path": str(p), "bytes": st.st_size, "modified": st.st_mtime, "directory": p.is_dir()}

    def register(self, r):
        r.add('file.create','Create a new UTF-8 file without overwriting',self.create_file,{'path':S,'text':S},['path','text'],Risk.MODIFY)
        r.add('file.edit','Apply one exact targeted replacement; observed hash and unique matching text required',self.edit_file,{'path':S,'old_text':S,'new_text':S,'expected_sha256':S},['path','old_text','new_text','expected_sha256'],Risk.MODIFY)
        r.add('file.append','Append to a freshly read file with its observed hash',self.append_file,{'path':S,'text':S,'expected_sha256':S},['path','text','expected_sha256'],Risk.MODIFY)
        r.add('file.rename','Rename one file without overwriting another',self.rename_file,{'path':S,'name':S},['path','name'],Risk.MODIFY)
        r.add('file.move','Move one file without overwriting another',self.move_file,{'source':S,'destination':S},['source','destination'],Risk.MODIFY)
        r.add('file.copy','Copy one file without overwriting another',self.copy_file,{'source':S,'destination':S},['source','destination'],Risk.MODIFY)
        r.add("file.undo", "Undo an identified June write only if file contents still match that change", self.undo, {"change_id": S}, ["change_id"], Risk.SENSITIVE)
        r.add("file.list", "List allowed directory", self.list, {"path": S})
        r.add("file.read", "Read UTF-8 code/text and obtain content hash", self.read, {"path": S}, ["path"])
        r.add("file.write", "Create/edit/append text. Existing files require observed hash. Preview full content before approval.", self.write, {"path": S, "text": S, "expected_sha256": S, "append": B}, ["path", "text"], Risk.MODIFY)
        r.add("file.mkdir", "Create directory", self.mkdir, {"path": S}, ["path"], Risk.MODIFY)
        r.add("file.transfer", "Copy, move or rename one file", self.transfer, {"source": S, "destination": S, "move": B}, ["source", "destination"], Risk.MODIFY)
        r.add("file.delete", "Delete ONE bounded file with a local undo backup; never directories", self.delete, {"path": S}, ["path"], Risk.SENSITIVE)
        r.add("file.search", "Search filenames or text within project", self.search, {"path": S, "pattern": S, "text": S})
        r.add("file.metadata", "Inspect file metadata", self.metadata, {"path": S}, ["path"])


async def run_process(argv, cwd, timeout=60, environment=None):
    env = {k: v for k, v in os.environ.items() if not any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    if environment:
        if any(k.upper() in {"PATH", "COMSPEC", "PYTHONPATH", "LD_PRELOAD"} for k in environment):
            raise ValueError("Unsafe environment override")
        env.update(environment)
    start = time.monotonic()
    process = await asyncio.create_subprocess_exec(*argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    async def drain(stream):
        data = bytearray()
        while chunk := await stream.read(8192):
            if len(data) < 64000:
                data.extend(chunk[:64000 - len(data)])
        return data.decode("utf-8", errors="replace")
    readers = [asyncio.create_task(drain(process.stdout)), asyncio.create_task(drain(process.stderr))]
    try:
        await asyncio.wait_for(process.wait(), max(1, min(timeout, 300)))
        out, err = await asyncio.gather(*readers)
        return {"stdout": out, "stderr": err, "returncode": process.returncode, "duration": time.monotonic() - start}
    finally:
        if process.returncode is None:
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except psutil.Error:
                pass
            await process.wait()
        await asyncio.gather(*readers, return_exceptions=True)


class ShellTools:
    def __init__(self, config):
        self.paths = Paths(config)

    async def run(self, command, cwd=".", timeout=60, environment=None):
        # Every arbitrary command requires human approval. This is not an OS sandbox.
        return await run_process(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], self.paths.resolve(cwd), timeout, environment)

    async def git(self, operation="status", cwd="."):
        allowed = {"status": ["status", "--short", "--branch"], "diff": ["diff", "--no-ext-diff", "--no-textconv"], "log": ["log", "-15", "--oneline"], "branch": ["branch", "--show-current"]}
        if operation not in allowed:
            raise ValueError("Unsupported read-only Git operation")
        return await run_process(["git", "--no-pager", "-c", "core.fsmonitor=false", *allowed[operation]], self.paths.resolve(cwd))

    def register(self, r):
        r.add("shell.run", "Run PowerShell with timeout and cancellation. Requires explicit human approval; inspect stdout/stderr/returncode.", self.run, {"command": S, "cwd": S, "timeout": N, "environment": O}, ["command"], Risk.SENSITIVE)
        r.add("git.inspect", "Read status/diff/log/branch without hooks or external diff", self.git, {"operation": S, "cwd": S})
