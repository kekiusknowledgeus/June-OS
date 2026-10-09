"""Generic project metadata, conservative detection and small offline starters."""
import json
import re
import sys
import os
import tomllib
from pathlib import Path
from .security import Risk
from .tools import S, O


def starters(kind, name):
    """Reviewed local templates. Creation never installs or executes dependencies."""
    readme = f'# {name}\n\nCreated by June. Inspect before installing dependencies or running commands.\n'
    if kind == 'python':
        return {'README.md':readme, 'main.py':'def greet():\n    return "Hello from '+name+'"\n\nif __name__ == "__main__":\n    print(greet())\n', 'tests/test_main.py':'import unittest\nfrom main import greet\n\nclass TestApp(unittest.TestCase):\n    def test_greeting(self):\n        self.assertTrue(greet().startswith("Hello"))\n', 'pyproject.toml':f'[project]\nname = "{name.lower()}"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'}
    if kind in {'node','static','react'}:
        package={'name':name.lower(), 'version':'0.1.0','private':True,'type':'module','scripts':{'test':'node --test'}}
        files={'README.md':readme}
        if kind=='node':
            package['scripts']['start']='node index.js'
            files.update({'index.js':'export const greet = () => "Hello from '+name+'";\nconsole.log(greet());\n','test/app.test.js':"import {test} from 'node:test';\nimport assert from 'node:assert/strict';\nimport {greet} from '../index.js';\ntest('greeting', () => assert.match(greet(), /^Hello/));\n"})
        elif kind=='static':
            package['scripts'].update({'build':'node build.mjs','start':'node server.mjs'})
            files.update({'index.html':f'<!doctype html>\n<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name}</title><link rel="stylesheet" href="style.css"><main><h1>{name}</h1><p id="message"></p></main><script type="module" src="app.js"></script></html>\n','style.css':'body{font:18px system-ui;background:#10212b;color:#d9eee8;margin:10vh auto;max-width:800px;padding:24px}\n','app.js':'document.querySelector("#message").textContent = "Ready to build.";\n','build.mjs':"import {mkdir,copyFile} from 'node:fs/promises';\nawait mkdir('dist',{recursive:true});\nfor (const name of ['index.html','style.css','app.js']) await copyFile(name,'dist/'+name);\nconsole.log('Static build complete');\n",'server.mjs':"import http from 'node:http';\nimport {readFile} from 'node:fs/promises';\nconst files={'/':['index.html','text/html'],'/style.css':['style.css','text/css'],'/app.js':['app.js','text/javascript']};\nhttp.createServer(async(req,res)=>{const entry=files[req.url];if(!entry){res.writeHead(404);return res.end();}try{res.setHeader('Content-Type',entry[1]);res.end(await readFile(entry[0]));}catch{res.writeHead(500);res.end('Unavailable');}}).listen(4173,'127.0.0.1',()=>console.log('http://127.0.0.1:4173'));\n",'test/app.test.js':"import {test} from 'node:test';\nimport assert from 'node:assert/strict';\nimport {readFile} from 'node:fs/promises';\ntest('page links its assets',async()=>{const html=await readFile('index.html','utf8');assert.match(html,/app.js/);assert.match(html,/style.css/);for(const f of ['app.js','style.css']) assert.ok((await readFile(f)).length);});\n"})
        else:
            # Versions are intentionally not selected by detection; installation is a separate approval.
            package['dependencies']={'react':'*','react-dom':'*'}
            package['devDependencies']={'vite':'*'}
            package['scripts'].update({'start':'vite --host 127.0.0.1','build':'vite build'})
            files.update({'index.html':f'<html lang="en"><meta charset="utf-8"><title>{name}</title><div id="root"></div><script type="module" src="/src/main.jsx"></script></html>\n','src/main.jsx':"import React from 'react';\nimport {createRoot} from 'react-dom/client';\ncreateRoot(document.getElementById('root')).render(React.createElement('h1',null,'"+name+"'));\n",'test/app.test.js':"import {test} from 'node:test';\nimport assert from 'node:assert/strict';\nimport {readFile} from 'node:fs/promises';\ntest('entry references mount',async()=>assert.match(await readFile('src/main.jsx','utf8'),/getElementById\\('root'\\)/));\n"})
        files['package.json']=json.dumps(package,indent=2)+'\n'
        return files
    if kind=='empty':
        return {'README.md':readme}
    raise ValueError('Choose python, node, react, static or empty')


class Projects:
    def __init__(self, runtime):
        self.r=runtime

    def workspace_path(self, path):
        resolved=self.r.files.paths.resolve(path)
        roots=[Path(p).resolve() for p in self.r.config.allowed_workspace_roots]
        if not any(resolved.is_relative_to(p) for p in roots):
            raise PermissionError('Project path is outside approved workspace roots')
        return resolved

    async def detect_project_type(self, path):
        root=self.r.files.paths.resolve(path)
        if not root.is_dir():
            raise ValueError('Project directory does not exist')
        data={'language':[],'framework':[],'build_system':[],'dependencies':{},'commands':{},'evidence':[],'warnings':[]}
        def mark(file, language, system):
            data['evidence'].append(file)
            if language not in data['language']: data['language'].append(language)
            if system not in data['build_system']: data['build_system'].append(system)
        async def read(file):
            return (await self.r.files.read(str(root/file)))['text']
        python="& '"+sys.executable.replace("'","''")+"'"
        for filename in ['pyproject.toml','requirements.txt','package.json','Cargo.toml','CMakeLists.txt','pom.xml']:
            if not (root/filename).is_file(): continue
            try:
                text=await read(filename)
                if filename=='package.json':
                    p=json.loads(text);mark(filename,'JavaScript/TypeScript','npm')
                    for key,value in p.get('scripts',{}).items():
                        if isinstance(value,str) and re.fullmatch(r'[\w:-]+',key): data['commands'][{'start':'run'}.get(key,key)]=('npm.cmd' if os.name=='nt' else 'npm')+' run '+key
                    data['dependencies'].update(p.get('dependencies',{}));data['dependencies'].update(p.get('devDependencies',{}))
                    if 'react' in data['dependencies']: data['framework'].append('React')
                elif filename in {'pyproject.toml','requirements.txt'}:
                    mark(filename,'Python','Python packaging')
                    if filename.endswith('.toml'):
                        p=tomllib.loads(text)
                        data['dependencies']['python']=p.get('project',{}).get('dependencies',[])
                        if 'pytest' in p.get('tool',{}) or any('pytest' in str(x).lower() for x in p.get('project',{}).get('optional-dependencies',{}).values()): data['commands']['test']=python+' -m pytest'
                    if (root/'main.py').is_file(): data['commands']['run']=python+' main.py'
                    if (root/'tests').is_dir() and 'test' not in data['commands']:
                        for test in list((root/'tests').glob('test*.py'))[:20]:
                            if 'unittest' in await read(test.relative_to(root)):
                                data['commands']['test']=python+' -m unittest discover -s tests';break
                elif filename=='Cargo.toml':
                    p=tomllib.loads(text);mark(filename,'Rust','Cargo');data['dependencies']['cargo']=p.get('dependencies',{})
                    data['commands'].update({'build':'cargo build','test':'cargo test'})
                    if (root/'src/main.rs').exists(): data['commands']['run']='cargo run'
                elif filename=='CMakeLists.txt':
                    mark(filename,'C/C++','CMake');data['commands']['configure']='cmake -S . -B build';data['commands']['build']='cmake --build build'
                    if 'enable_testing(' in text or 'include(CTest)' in text: data['commands']['test']='ctest --test-dir build --output-on-failure'
                    data['warnings'].append('CMake build requires configure and an installed compiler first')
                else:
                    mark(filename,'Java','Maven');data['commands'].update({'build':'mvn package','test':'mvn test'})
            except (ValueError,OSError,UnicodeError,TypeError,AttributeError) as exc:
                data['warnings'].append(filename+': '+type(exc).__name__)
        dotnet=list(root.glob('*.sln'))+list(root.glob('*.csproj'))
        if dotnet:
            for p in dotnet: mark(p.name,'C#','.NET')
            if len(dotnet)==1:
                data['commands']['build']='dotnet build'
                metadata=await read(dotnet[0].name)
                if 'Microsoft.NET.Test.Sdk' in metadata or '<IsTestProject>true' in metadata:
                    data['commands']['test']='dotnet test'
            else: data['warnings'].append('Multiple .NET entry points: select an explicit solution or project command')
        for p in root.glob('*.uproject'):
            mark(p.name,'C++','Unreal Build Tool');data['framework'].append('Unreal Engine');data['warnings'].append('Unreal commands require the actual engine/toolchain path; none guessed')
        if (root/'index.html').is_file(): mark('index.html','HTML/CSS','Static web')
        data['run_commands']={k:v for k,v in data['commands'].items() if k in {'run','dev','serve'}}
        data['test_commands']={k:v for k,v in data['commands'].items() if 'test' in k}
        return data

    async def register_project(self, path, name=None, details=None):
        root=self.workspace_path(path)
        detected=await self.detect_project_type(str(root))
        existing=next((p for p in self.r.store.list('project') if Path(p['root_path']).resolve()==root),None)
        metadata={k:detected[k] for k in ('language','framework','build_system','dependencies','commands','run_commands','test_commands')}
        if existing:
            metadata['commands'].update(existing.get('commands',{}))
        metadata.update(details or {})
        record=await self.r.project_save(name or (existing or {}).get('name') or root.name,str(root),metadata,(existing or {}).get('id'))
        await self.switch_project(record['id'])
        return {'project':record,'detection':detected}

    def creation_preview(self, name, template='empty', parent=None):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',name) or name.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise ValueError('Use a simple non-reserved project name, letters/numbers/dash/underscore')
        root=self.workspace_path(str(Path(parent or self.r.config.projects_root)/name))
        if root.exists(): raise FileExistsError('Project already exists; register it instead')
        return {'root_path':str(root),'files':starters(template,name),'template':template}

    async def create_project(self, name, template='empty', parent=None):
        preview=self.creation_preview(name,template,parent)
        root=Path(preview['root_path'])
        root.mkdir(parents=True,exist_ok=False)
        changes=[]
        try:
            for filename,text in preview['files'].items():
                changes.append(await self.r.files.write(str(root/filename),text))
            result=await self.register_project(str(root),name)
            result.update({'changes':changes,'validation':'not run; commands require separate approval'})
            return result
        except Exception:
            # Retain partial files and their undo records; never recursively erase user data.
            self.r.timeline.add('project.create.partial','Partial project creation; inspect before retry',details={'root':str(root),'changes':changes})
            raise

    async def unregister_project(self, project):
        p=self.r.current.project(project)
        if not p: raise ValueError('Project unavailable or ambiguous')
        self.r.store.delete('project',p['id'])
        if self.r.current.value('current_project')==p['id']: self.r.current.set('current_project',None,'explicit unregister')
        return {'unregistered':p['name'],'files_deleted':False}

    async def list_projects(self): return self.r.store.list('project')

    async def switch_project(self, project):
        p=self.r.current.project(project)
        if not p: raise ValueError('Project unavailable or ambiguous')
        self.r.files.paths.resolve(p['root_path'])
        self.r.current.set('current_project',p['id'],'explicit user project selection')
        return p

    async def discover(self):
        known={Path(p['root_path']).resolve() for p in self.r.store.list('project')}
        candidates=[]
        for base in self.r.config.allowed_workspace_roots:
            root=self.workspace_path(base)
            if not root.is_dir(): continue
            for child in list(root.iterdir())[:300]:
                try:
                    if not child.is_dir() or child.is_symlink() or child.resolve() in known: continue
                    detected=await self.detect_project_type(str(child))
                    if detected['evidence']: candidates.append({'path':str(child),'name':child.name,'evidence':detected['evidence'],'registered':False})
                except (ValueError,OSError,PermissionError): continue
        return candidates

    async def suggest_from_window(self, window):
        title=window.get('title','').casefold()
        candidates=await self.discover()
        suggestions=[c for c in candidates if re.search(r'(?<!\w)'+re.escape(c['name'].casefold())+r'(?!\w)',title)]
        self.r.current.set('project_suggestions',suggestions,'foreground title matched an approved workspace folder; suggestion only',.7)
        return suggestions

    def register(self,r):
        r.add('project.create','Create a new project from a local template; never install dependencies or overwrite existing folders',self.create_project,{'name':S,'template':S,'parent':S},['name'],Risk.MODIFY)
        r.add('project.register','Detect and register an existing project inside approved workspaces',self.register_project,{'path':S,'name':S,'details':O},['path'],Risk.MODIFY)
        r.add('project.unregister','Remove registry entry only; preserve every file',self.unregister_project,{'project':S},['project'],Risk.MODIFY)
        r.add('project.list','List all registered projects',self.list_projects)
        r.add('project.detect','Detect metadata and command candidates from project files; never execute them',self.detect_project_type,{'path':S},['path'])
        r.add('project.switch','Select a registered project for relative paths and follow-up commands',self.switch_project,{'project':S},['project'],Risk.LOCAL)
        r.add('project.discover','Suggest unregistered child projects under approved workspace roots; no auto-registration',self.discover)
