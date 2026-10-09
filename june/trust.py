"""Host-only scoped trust. Model tools cannot create rules or alter risk labels."""
import re
import shlex
from pathlib import Path
from urllib.parse import urlsplit
from .security import Paths, Risk, action_digest


def shell_category(command):
    # Shell grammar is intentionally small; unknown syntax returns ASK.
    if re.search(r'[;|`\r\n<>$]',command): return None
    try: parts=[p.strip('\"\'') for p in shlex.split(command,posix=False)]
    except ValueError: return None
    if parts and parts[0]=='&': parts.pop(0)
    if not parts: return None
    exe=parts[0].replace('\\','/').rsplit('/',1)[-1].lower().removesuffix('.exe').removesuffix('.cmd')
    args=parts[1:]
    if any(a.split('=')[0] in {'-c','--eval','-e','--global','-g','--prefix','--target','--directory','--cwd','-C','--script-shell','--user','--system','--config','--require','--import'} for a in args): return None
    if any('..' in a.replace('\\','/').split('/') or re.match(r'^(?:[a-zA-Z]:|/|\\\\)',a) for a in args): return None
    if exe=='git':
        return 'git-local' if args and args[0] in {'status','diff','log','add'} and not any(a.startswith('-c') or a.startswith('--config') for a in args) else None
    if exe in {'python','python3'}:
        if args[:1]==['-m']:
            if args[1:3]==['pip','install'] and '/.venv/' in parts[0].replace('\\','/').lower(): return 'dependencies'
            return {'pytest':'test','unittest':'test','compileall':'build','ruff':'lint','black':'format'}.get(args[1] if len(args)>1 else '')
        return 'run' if len(args)==1 and args[0].endswith('.py') else None
    if exe in {'npm','pnpm','yarn'}:
        if args[:1] in [['install'],['ci'],['add']]: return 'dependencies'
        name=args[1] if args[:1]==['run'] and len(args)>1 else (args[0] if args else '')
        return {'test':'test','build':'build','dev':'run','start':'run','lint':'lint','format':'format','check':'test'}.get(name)
    if exe=='node': return 'test' if args[:1]==['--test'] else 'run' if len(args)==1 and args[0].endswith(('.js','.mjs')) else None
    if exe in {'pytest','ruff','black'}: return {'pytest':'test','ruff':'lint','black':'format'}[exe]
    if exe in {'cargo','dotnet','mvn','mvnw'}:
        return {'test':'test','build':'build','check':'test','run':'run','package':'build','verify':'test','fmt':'format'}.get(args[0] if args else '')
    if exe=='cmake': return 'build' if args[:1]==['--build'] or args[:2]==['-S','.'] else None
    if exe=='ctest': return 'test'
    if exe=='uv':
        if args[:1] in [['sync'],['add']]: return 'dependencies'
        if args[:1]==['run']: return shell_category(' '.join(args[1:]))
    return None


class Trust:
    def __init__(self,runtime):
        self.r=runtime
        # Running jobs cannot grant permissions by planting a generic SQLite record.
        # Only owner API decisions update this live policy snapshot.
        self.rules=runtime.store.list('trust_rule',100000)

    def trusted_path(self,value):
        try:
            path=Paths(self.r.config).resolve(value)
            return any(path.is_relative_to(Path(root).resolve()) for root in self.r.config.trusted_workspace_roots)
        except (ValueError,OSError,PermissionError): return False

    def protected_engine(self,args):
        root=self.r.config.root.resolve()
        for key in ('path','source','destination','parent','expected_cwd','cwd'):
            if not args.get(key): continue
            path=Path(args[key]).resolve()
            if path in {root/'config.json',root/'Start-June.cmd',root/'pyproject.toml',root/'requirements.lock'} or any(path.is_relative_to(root/x) for x in ('june','extensions','data','.codex')):
                return True
        return False

    def decision(self,tool,args,job=None,observation=None):
        c=self.r.config; name=tool.name; risk=int(tool.risk)
        target=str(args.get('path',args.get('url',args.get('expected_cwd',args.get('cwd',args.get('project',''))))))
        service=(observation or {}).get('service','')
        action=(observation or {}).get('service_action','')
        contact=(observation or {}).get('contact','')
        if observation: risk=max(risk,int(observation.get('risk',risk)))
        if name in {'shell.run','project.run'} and re.search(r'(?i)\b(format(?:\.com)?|diskpart|runas|set-mppreference|disable-windowsoptionalfeature)\b',args.get('expected_command',args.get('command',''))):
            risk=5
        rule='default risk'; verdict='ASK' if risk>=2 else 'ALLOW'
        url=args.get('url',(observation or {}).get('url',''))
        if c.owner_mode and url and not any(domain=='*' or urlsplit(url if '://' in url else 'https://'+url).hostname==domain for domain in c.trusted_browser_domains):
            verdict='ASK';rule='website outside trusted domains'
        if c.owner_mode and name=='app.open' and args.get('name') not in c.trusted_apps:
            verdict='ASK';rule='application outside trusted apps'
        if name.startswith('file.') and self.protected_engine(args): risk=max(risk,4);rule='protected June host files'
        if risk>=5: return {'verdict':'ASK','risk':risk,'rule':'critical: always confirm','target':target}
        # Explicit deny wins. Rules are authored only by authenticated owner UI.
        for item in sorted(self.rules,key=lambda x:x['decision']!='DENY'):
            if item.get('tool') not in {name,'*'}: continue
            scope=item.get('scope'); value=item.get('value','')
            matches=scope=='action' and value==action_digest(name,args)
            if scope in {'folder','project'}:
                paths=[args[k] for k in ('path','source','destination','cwd','expected_cwd','parent') if args.get(k)]
                matches=bool(paths) and all(Path(p).resolve().is_relative_to(Path(value).resolve()) for p in paths)
            if scope=='service': matches=bool(service and value==service)
            if scope=='app': matches=value==args.get('name',args.get('application'))
            if matches and item['decision']=='DENY': return {'verdict':'DENY','risk':risk,'rule':item['id'],'target':target}
            if matches and item['decision']=='ALLOW' and (risk<4 or scope=='action'):
                verdict='ALLOW';rule=item['id'];break
        if verdict!='ALLOW' and risk==3 and service:
            policy=c.trusted_contacts.get(service,{}).get(contact) if contact else None
            policy=policy or c.trusted_external_services.get(service,{}).get(action,'ASK')
            if policy in {'ALWAYS_ALLOW','DENY'}: verdict='ALLOW' if policy=='ALWAYS_ALLOW' else 'DENY';rule='service:'+service+':'+action
        if c.owner_mode and rule=='default risk':
            local_files={'file.create','file.write','file.edit','file.append','file.rename','file.move','file.copy','file.transfer','file.mkdir'}
            if name in local_files:
                targets=[args[k] for k in ('path','source','destination') if k in args]
                if targets and all(self.trusted_path(x) for x in targets) and risk<4: verdict='ALLOW';rule='owner:trusted-workspace'
            elif name=='project.create' and self.trusted_path(args.get('parent',c.projects_root)): verdict='ALLOW';risk=2;rule='owner:project-create'
            elif name=='file.undo':
                change=next((x for x in self.r.files.changes() if x['id']==args.get('change_id')),None)
                targets=[change[k] for k in ('path','source','destination') if change and change.get(k)]
                if targets and all(self.trusted_path(x) for x in targets) and not self.protected_engine(change): verdict='ALLOW';risk=2;rule='owner:recoverable-undo'
            elif name in {'project.register','project.save'} and self.trusted_path(args.get('path',args.get('root_path',''))): verdict='ALLOW';rule='owner:project-registry'
            elif name in {'task.save','memory.remember','memory.manage','schedule.create','watch.create','window.focus','path.open','project.switch','project.unregister'} and risk<4: verdict='ALLOW';rule='owner:local-action'
            elif name in {'shell.run','project.run'}:
                cwd=args.get('expected_cwd',args.get('cwd',''))
                category=shell_category(args.get('expected_command',args.get('command','')))
                if category in c.trusted_shell_categories and self.trusted_path(cwd): verdict='ALLOW';risk=2;rule='owner:shell:'+category
            elif name in {'web.search','web.read','browser.navigate','browser.automation.navigate','browser.personal.open','browser.personal.new_tab','browser.personal.navigate'}:
                verdict='ALLOW';risk=1;rule='owner:browser-navigation'
            elif name.startswith('browser.personal.') and observation and observation.get('risk',4)<=2:
                verdict='ALLOW';risk=observation['risk'];rule='owner:observed-browser-action'
        return {'verdict':verdict,'risk':risk,'rule':rule,'target':target}

    def task_context(self,job,project):
        """Record host-derived scope; this never broadens persistent trust."""
        root=project.get('root_path') if project else None
        return self.r.store.put('task_authorization',{'project':root,'owner_mode':self.r.config.owner_mode,
            'allowed':['read','create','edit','run_tests','run_build','launch_project','browser_test'] if root and self.r.config.owner_mode and self.trusted_path(root) else ['read'],
            'source':'host persistent trust; rechecked on every action'},job)

    def save_rule(self,tool,args,scope,decision,value=None):
        if scope not in {'action','folder','project','app','service'} or decision not in {'ALLOW','DENY'}: raise ValueError('Invalid trust rule')
        if scope=='action': value=action_digest(tool,args)
        if not value: raise ValueError('Choose an explicit scope')
        if scope in {'folder','project'}:
            value=str(Paths(self.r.config).resolve(value))
            if Path(value).parent==Path(value): raise ValueError('Whole drive trust is forbidden')
        rule=self.r.store.put('trust_rule',{'tool':tool,'scope':scope,'value':value,'decision':decision,'source':'authenticated owner UI'})
        self.rules.append(rule)
        return rule

    def revoke(self,id):
        self.r.store.delete('trust_rule',id)
        self.rules=[x for x in self.rules if x['id']!=id]
