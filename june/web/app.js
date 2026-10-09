let requestedView=new URLSearchParams(location.search).get('view');
let focusedJob=new URLSearchParams(location.search).get('job');
let token=location.hash.slice(1)||sessionStorage.getItem('june-token')||'';if(token){sessionStorage.setItem('june-token',token);history.replaceState(null,'',location.pathname+location.search)}
let tab=['brain','jobs','notification'].includes(requestedView)?requestedView:'conversation',state=null,previous='',busy=false;const $=id=>document.getElementById(id);
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
async function api(path,body,method){const r=await fetch('/api/'+path,{method:method||(body?'POST':'GET'),headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await r.json().catch(()=>({error:'Local service returned HTTP '+r.status}));if(!r.ok)throw Error(data.error||JSON.stringify(data.detail)||r.statusText);return data}
function button(text,fn){const b=el('button',text);b.type='button';b.onclick=()=>Promise.resolve().then(fn).catch(error);return b}
function error(e){$('error').textContent=e.message||String(e)}
async function send(text){$('error').textContent='';await api('chat',{text});$('message').value='';await refresh()}
$('composer').onsubmit=e=>{e.preventDefault();send($('message').value).catch(error)};$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('composer').requestSubmit()}};
$('stop').onclick=()=>api('stop',{}).then(refresh).catch(error);$('privacy').onclick=()=>api('settings',{privacy:!state.health.privacy}).then(refresh).catch(error);$('talk').onclick=()=>api('voice/talk',{}).catch(error);
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;previous='';document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x===b));$('title').textContent=b.textContent;render().catch(error)});
function form(fields,submit){const f=el('form',undefined,'form-grid');for(const [name,placeholder]of fields){const input=el('input');input.name=name;input.placeholder=placeholder;input.setAttribute('aria-label',placeholder);input.required=true;f.append(input)}const b=el('button','Save');b.type='submit';f.append(b);f.onsubmit=e=>{e.preventDefault();const values=Object.fromEntries(new FormData(f));submit(values).then(()=>{f.reset();previous='';return render()}).catch(error)};return f}
async function render(){if(!state)return;const content=$('content');$('composer').hidden=tab!=='conversation';if(tab==='conversation'){const key=JSON.stringify([state.messages,state.jobs]);if(key===previous)return;previous=key;content.replaceChildren();if(!state.messages.length){const w=el('div',undefined,'welcome');w.append(el('div','JUNE IS HERE','eyebrow'),el('h2','A little less to carry.'),el('p','Your projects, thoughts and next steps — together in one place. Ask June to investigate, remember, or help you move something forward.'));const s=el('div',undefined,'suggestions');['What needs my attention?','Show me the projects you know about.','What can you do on this computer?'].forEach(t=>s.append(button(t,()=>send(t))));w.append(s);content.append(w)}for(const m of state.messages){const box=el('article',undefined,'message '+m.role);box.append(el('div',m.role==='user'?'Mayank':'June','label'),el('pre',m.content));content.append(box)}for(const job of state.jobs.filter(j=>j.status!=='completed')){const b=el('div',job.status+' · '+job.request,'job');if(job.error)b.append(el('pre',job.error));if(job.progress)b.append(el('p',job.progress));if(['queued','running','waiting_for_permission'].includes(job.status))b.append(button('Cancel',()=>api('cancel/'+job.id,{})));content.append(b)}content.scrollTop=content.scrollHeight;return}
if(tab==='settings'){await renderSettings(content);return}
if(tab==='brain'){
  await renderBrain(content);return;
}
if(tab==='devices'||tab==='integrations'){content.replaceChildren();if(tab==='devices'){content.append(el('h2','Devices'),el('p','No physical devices are configured. Camera and screen remain controlled by Settings & Health.'),button('List local audio devices',async()=>content.append(el('pre',JSON.stringify(await api('voice/devices'),null,2)))))}else{for(const[name,info]of Object.entries(state.health.integrations)){const card=el('article',undefined,'card');card.append(el('h3',name),el('p',info.status),el('p',(info.capabilities||[]).join(' · ')));content.append(card)}}return}
if(tab==='jobs'){
  content.replaceChildren(button('Pause all jobs',()=>api('pause',{}).then(refresh)),button('Resume paused jobs',()=>send('resume everything')));
  for(const job of state.jobs){const card=el('article',undefined,'card');card.append(el('div',job.status+' · '+(job.agent_state||''),'label'),el('strong',job.request));if(job.progress)card.append(el('p',job.progress));if(job.error)card.append(el('pre',job.error));if(job.workflow)card.append(el('pre',JSON.stringify(job.workflow,null,2)));if(['paused','interrupted','waiting_external','failed'].includes(job.status))card.append(button('Retry with fresh permissions',()=>api('resume/'+job.id,{}).then(refresh)));if(['queued','running','waiting_for_permission'].includes(job.status))card.append(button('Cancel',()=>api('cancel/'+job.id,{}).then(refresh)));if(job.id===focusedJob){card.classList.add('focused-job');card.setAttribute('tabindex','-1')}content.append(card)}if(focusedJob){content.querySelector('.focused-job')?.scrollIntoView({block:'nearest'});focusedJob=null}return;
}
if(tab==='timeline'){
  const rows=await api('timeline');content.replaceChildren();if(!rows.length)content.append(el('p','No June events recorded yet.'));
  for(const row of rows){const card=el('article',undefined,'card');card.append(el('div',new Date(row.created_at*1000).toLocaleString()+' · '+row.type,'label'),el('p',row.summary));content.append(card)}return;
}
const rows=await api('records/'+tab);
content.replaceChildren();
if(tab==='task')content.append(form([['title','Task title']],v=>api('tasks',v)));
if(tab==='memory')content.append(form([['text','Remember something important']],v=>api('memory',v)));
if(tab==='project'){
  content.append(button('Refresh projects',()=>refresh().then(render)),el('p','Current project: '+(rows.find(p=>p.id===state.current.current_project?.value)?.name||'not selected')));
  for(const suggestion of state.current.project_suggestions?.value||[]){const box=el('article',undefined,'card');box.append(el('p','Registration suggestion: '+suggestion.name),button('Review registration',()=>api('projects/action',{action:'register',arguments:{path:suggestion.path,name:suggestion.name}})));content.append(box)}
  content.append(form([['name','Project name'],['root_path','Existing path inside approved workspace roots']],v=>api('projects/action',{action:'register',arguments:{name:v.name,path:v.root_path}})));
  content.append(form([['name','New project name'],['template','Template: python, node, react, static or empty']],v=>api('projects/action',{action:'create',arguments:v})),el('p','Trusted workspaces allow creation and development commands automatically in Owner Mode. Higher-risk actions require review.'),button('Discover projects',async()=>{const found=await api('projects/discover');for(const item of found){const row=el('article',undefined,'card');row.append(el('strong',item.name),el('p',item.path),button('Register',()=>api('projects/action',{action:'register',arguments:{path:item.path,name:item.name}})));content.append(row)}if(!found.length)content.append(el('p','No unregistered projects found.'))}));
}
if(tab==='schedule')content.append(form([['title','Reminder'],['due','Time with offset, e.g. 2026-10-03T18:00:00+05:30']],v=>api('schedules',v)));
if(!rows.length)content.append(el('p','Nothing here yet.'));
for(const row of rows){
  const card=el('article',undefined,'card');
  if(tab==='task'){
    card.append(el('div',row.status+' · Priority '+row.priority,'label'),el('strong',row.title));
    if(row.description)card.append(el('p',row.description));
    if(row.deadline)card.append(el('p','Due '+new Date(row.deadline).toLocaleString()));
    if(row.status!=='done')card.append(button('Mark done',()=>api('tasks',{title:row.title,id:row.id,status:'done'}).then(render)));
  }else if(tab==='project'){
    card.append(el('div',row.status,'label'),el('strong',row.name),el('p',row.description||row.root_path));
    if(row.current_goal)card.append(el('p','Current goal: '+row.current_goal));
    for(const action of row.next_actions||[])card.append(el('p','Next: '+action));
    card.append(el('small',row.root_path+' · '+(row.technologies||[]).join(', ')),el('p',[row.language,row.framework,row.build_system].flat().filter(Boolean).join(' · ')),button('Work on this project',()=>api('projects/action',{action:'switch',arguments:{project:row.id}})),button('Inspect',()=>api('projects/action',{action:'inspect',arguments:{project:row.id}})),button('Unregister',()=>api('projects/action',{action:'unregister',arguments:{project:row.id}})));
    if(row.commands)card.append(el('pre',JSON.stringify(row.commands,null,2)));
  }else if(tab==='memory'){
    card.append(el('div',row.category+' · '+(row.explicit?'You asked June to remember':'Suggested memory')+' · '+(row.status||'active'),'label'),el('p',row.text),button(row.pinned?'Unpin':'Pin',()=>api('memory/'+row.id+'/manage',{action:row.pinned?'unpin':'pin'}).then(render)),button('Edit',()=>{const text=prompt('Update this memory',row.text);if(text)return api('memory/'+row.id+'/manage',{action:'update',text}).then(render)}),button('Forget',()=>api('memory/'+row.id,null,'DELETE').then(render)));
    if(row.conflicts?.length)card.append(el('p','Conflicting memories: '+row.conflicts.join(', ')));
  }else if(tab==='schedule'){
    card.append(el('div',row.enabled?'Scheduled':'Inactive','label'),el('strong',row.title),el('p',new Date(row.due*1000).toLocaleString()+(row.interval?' · Repeats every '+row.interval/60+' minutes':'')));
    if(row.prompt)card.append(el('p',row.prompt));
    if(row.enabled)card.append(button('Disable',()=>api('schedules/'+row.id+'/disable',{}).then(render)));
  }else if(tab==='notification'){
    card.append(el('div',new Date(row.created_at*1000).toLocaleString(),'label'),el('strong',row.title),el('p',row.body));
  }else{
    card.append(el('div',new Date(row.timestamp*1000).toLocaleString(),'label'),el('strong',row.tool||row.action||'Action'),el('pre',JSON.stringify(row,null,2)));
  }
  content.append(card);
}}
async function refresh(){if(busy)return;busy=true;try{state=await api('state');$('status').textContent=state.presence.state+' · '+state.health.active_jobs+' active';$('privacy').textContent=state.health.privacy?'Resume connections':'Privacy mode';$('provider').textContent=state.health.provider+' / '+state.health.model;$('permissions').replaceChildren();for(const a of state.approvals){const box=el('div',undefined,'permission');box.append(el('strong','Approval required · Level '+a.risk+' · '+a.tool),el('pre',a.parameters),button('Approve this action',()=>api('approve/'+a.id,{allow:true}).then(refresh)),button('Deny',()=>api('approve/'+a.id,{allow:false}).then(refresh)));const scope=el('select');for(const v of ['once','action','app','project','folder','service']){const o=el('option',v==='once'?'Allow/deny once':'Remember for '+v);o.value=v;scope.append(o)}const value=el('input');value.placeholder='Exact app, project/folder path, or service';box.append(scope,value,button('Apply remembered allow',()=>api('approve/'+a.id,{allow:true,remember:scope.value==='once'?null:scope.value,scope_value:value.value||null}).then(refresh)),button('Apply remembered deny',()=>api('approve/'+a.id,{allow:false,remember:scope.value==='once'?null:scope.value,scope_value:value.value||null}).then(refresh)));$('permissions').append(box)}if(tab==='conversation')await render()}catch(e){error(e)}finally{busy=false}}
document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('selected',b.dataset.tab===tab);if(b.dataset.tab===tab)$('title').textContent=b.textContent});
refresh().then(()=>{if(tab!=='conversation')render().catch(error)});setInterval(()=>refresh().then(()=>{if(['brain','jobs','timeline'].includes(tab))render().catch(error)}),2000);
