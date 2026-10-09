import asyncio
import hashlib
import json
from pathlib import Path
import pytest
from june.config import Config
from june.runtime import Runtime
from june.brain import JuneBrain
from june.workflows import Workflow


class OfflineBrain(JuneBrain):
    external=False
    async def respond(self,context,tools):
        raise AssertionError('No inference expected')


def runtime(tmp_path):
    config=Config.load(tmp_path/'June')
    config.projects_root=str(tmp_path/'Projects')
    config.allowed_workspace_roots=[str(config.root),config.projects_root]
    return Runtime(config,OfflineBrain())


async def approved(r,name,args):
    task=asyncio.create_task(r.execute('fixture',name,args))
    for _ in range(200):
        if task.done(): break
        for id in list(r.approvals): r.approve(id,True)
        await asyncio.sleep(.01)
    return await asyncio.wait_for(task,5)


async def test_create_switch_patch_and_undo_across_projects(tmp_path):
    r=runtime(tmp_path)
    try:
        a=(await r.projects.create_project('Orbit','python'))['project']
        b=(await r.projects.create_project('Nova','static'))['project']
        assert a['language']==['Python'] and b['commands']['build'].endswith('run build')
        assert (await r.commands.dispatch('June, work on Orbit.','fixture')).startswith('Current project')
        read=await r.execute('fixture','file.read',{'path':'main.py'})
        args={'path':'main.py','old_text':'Hello from Orbit','new_text':'Hello from Orbit improved','expected_sha256':read['result']['sha256']}
        result=await approved(r,'file.edit',args)
        assert result['status']=='success',result
        assert 'improved' in (Path(a['root_path'])/'main.py').read_text()
        assert r.current.value('project_inspection')['project']['id']==a['id']
        assert not (Path(b['root_path'])/'main.py').exists()
        change=result['result']['change_id']
        await r.files.undo(change)
        assert 'improved' not in (Path(a['root_path'])/'main.py').read_text()
        assert r.timeline.query(a['id'])
    finally: await r.close()


async def test_creation_refuses_escape_existing_and_workspace_without_permission(tmp_path):
    r=runtime(tmp_path)
    try:
        with pytest.raises(PermissionError):
            await r.projects.create_project('Escape','empty',str(tmp_path/'Outside'))
        with pytest.raises(ValueError): await r.projects.create_project('../Escape')
        p=await r.projects.create_project('Safe','empty')
        data_path=Path(p['project']['root_path'])/'data/settings.json'
        await r.files.create_file(str(data_path),'{}')
        assert any(row['path']==str(data_path) for row in await r.files.search(p['project']['root_path'],text='{}'))
        with pytest.raises(PermissionError): await r.files.read(str(r.config.root/'data/june.db'))
        with pytest.raises(FileExistsError): await r.projects.create_project('Safe','python')
        denied=asyncio.create_task(r.execute('fixture','project.create',{'name':'Denied','template':'python'}))
        for _ in range(100):
            if r.approvals: break
            await asyncio.sleep(.01)
        aid=next(iter(r.approvals))
        preview=r.store.get('approval',aid)['parameters']
        assert 'main.py' in preview and 'root_path' in preview
        r.approve(aid,False)
        assert (await denied)['status']=='permission_denied'
        assert not (Path(r.config.projects_root)/'Denied').exists()
        await r.projects.unregister_project(p['project']['id'])
        assert Path(p['project']['root_path']).is_dir()
    finally: await r.close()


async def test_detection_discovery_and_no_guessed_unreal_command(tmp_path):
    r=runtime(tmp_path)
    try:
        root=Path(r.config.projects_root);root.mkdir()
        for name,marker,contents,language in [('Rust','Cargo.toml','[package]\nname="rust-fixture"\nversion="0.1.0"','Rust'),('Cpp','CMakeLists.txt','cmake_minimum_required(VERSION 3.20)\nenable_testing()','C/C++'),('Java','pom.xml','<project/>','Java'),('Dotnet','Example.csproj','<Project/>','C#'),('Engine','Example.uproject','{}','C++'),('React','package.json',json.dumps({'dependencies':{'react':'*'},'scripts':{'test':'node --test'}}),'JavaScript/TypeScript')]:
            folder=root/name;folder.mkdir();(folder/marker).write_text(contents)
            data=await r.projects.detect_project_type(str(folder))
            assert language in data['language']
            if name=='Engine': assert not data['commands']
        found=await r.projects.discover()
        assert len(found)==6
        suggestions=await r.projects.suggest_from_window({'title':'React - Visual Studio Code'})
        assert len(suggestions)==1 and suggestions[0]['name']=='React'
        assert not r.store.list('project')
        p=await r.projects.register_project(str(root/'React'),'Frontend')
        again=await r.projects.register_project(str(root/'React'))
        assert p['project']['id']==again['project']['id']
    finally: await r.close()


async def test_patch_stale_ambiguous_and_reversible_file_operations(tmp_path):
    r=runtime(tmp_path)
    try:
        p=Path(r.config.root)/'one.txt'
        p.write_text('same same')
        current=await r.files.read(str(p))
        with pytest.raises(ValueError): await r.files.edit_file(str(p),'same','changed',current['sha256'])
        with pytest.raises(ValueError): await r.files.edit_file(str(p),'same same','changed','stale')
        move=await r.files.rename_file(str(p),'two.txt')
        await r.files.undo(move['change_id'])
        assert p.read_text()=='same same'
        copied=await r.files.copy_file(str(p),str(p.with_name('copy.txt')))
        p.with_name('copy.txt').write_text('new user content')
        with pytest.raises(ValueError): await r.files.undo(copied['change_id'])
        deleted=await r.files.delete(str(p))
        await r.files.undo(deleted['change_id'])
        assert p.read_text()=='same same'
    finally: await r.close()


def test_new_coding_tools_invalidate_verification():
    for tool in ('project.create','file.create','file.edit','file.append','file.rename','file.move','file.copy'):
        workflow=Workflow('coding')
        workflow.observe('shell.run',{'command':'npm test'},{'status':'success','result':{'returncode':0}})
        workflow.observe(tool,{'path':'a.py'},{'status':'success','result':{}})
        assert workflow.completion_problem()
