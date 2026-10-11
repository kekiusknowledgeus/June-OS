const BASE='http://127.0.0.1:8765';
const tickets=new Map();let polling=false;
function safeURL(value){const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||/access_token=|api_key=|password=|authorization=/i.test(u.search+u.hash))throw Error('Protected browser URL');if(['localhost','127.0.0.1','[::1]'].includes(u.hostname)&&u.port==='8765')throw Error('June administration is protected');return u.href}
function safePage(url){safeURL(url);if(/(?:accounts\.|login\.|\/login\b|\/signin\b|\/oauth\b|\/checkout\b|\/payment\b|\/password\b|\/auth\b)/i.test(url))throw Error('Authentication and payment pages are protected')}
function summary(tab){let url;try{safePage(tab.url);url=safeURL(tab.url)}catch{url='[protected]'}return {tab:tab.id,title:url==='[protected]'?'[protected]':tab.title,url,mode:'personal_browser'}}
// Runs in an isolated world. Never returns form values or evaluates supplied code.
function pageAction(operation,a){
  if(location.href!==a.expectedURL)throw Error('Page navigated; observe again');
  const selectorFor=e=>{if(e.id&&document.querySelectorAll('#'+CSS.escape(e.id)).length===1)return '#'+CSS.escape(e.id);const parts=[];for(let node=e;node&&node.nodeType===1;node=node.parentElement){const siblings=node.parentElement?[...node.parentElement.children].filter(x=>x.tagName===node.tagName):[node];parts.unshift(node.tagName.toLowerCase()+':nth-of-type('+(siblings.indexOf(node)+1)+')')}return parts.join(' > ')};
  const sensitive=e=>!!e.closest('input[type=password],input[autocomplete*=password],input[autocomplete^=cc-],input[autocomplete=one-time-code]')||/password|credit.?card|cvv|cvc|secret|token|security.?code/i.test([e.name,e.id,e.getAttribute('aria-label')].join(' '));
  const visible=e=>!!(e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
  if(operation==='read'){
    // Only collect visible original text nodes; form values are never read.
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let text='',n;
    while((n=walker.nextNode())&&text.length<12000){const e=n.parentElement;if(e&&visible(e)&&!e.closest('input,textarea,select,script,style,noscript,[contenteditable]')&&!sensitive(e))text+=n.textContent.trim()+' ';}
    const controls=[...document.querySelectorAll('a,button,input,textarea,select,[role=button]')].filter(e=>visible(e)&&!sensitive(e)).slice(0,150).map(e=>({tag:e.tagName,role:e.getAttribute('role'),label:(e.getAttribute('aria-label')||e.getAttribute('placeholder')||(e.tagName==='INPUT'?'':e.innerText)||'').slice(0,160),selector:selectorFor(e)}));
    return {title:document.title,url:location.href,text:text.slice(0,12000),controls};
  }
  if(operation==='scroll'){scrollBy(0,a.amount);return {scrolled:a.amount}}
  if(operation==='media'){const m=document.querySelector('video,audio');if(!m)throw Error('No page media');if(a.action==='play')return m.play().then(()=>({media:'play'}));m.pause();return {media:'pause'}}
  const e=document.querySelector(a.selector);if(!e||!visible(e)||e.disabled||e.getAttribute('aria-disabled')==='true')throw Error('Target is absent, hidden, or disabled');if(document.querySelectorAll(a.selector).length!==1)throw Error('Target selector is ambiguous');if(sensitive(e)||e.closest('form')?.querySelector('input[type=password],input[autocomplete^=cc-],input[autocomplete=one-time-code]'))throw Error('Sensitive form is protected');
  const label=(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'').slice(0,250);
  globalThis.__juneNodes??=new WeakMap();if(!globalThis.__juneNodes.has(e))globalThis.__juneNodes.set(e,crypto.randomUUID());
  const fingerprint=JSON.stringify([globalThis.__juneNodes.get(e),location.href,e.tagName,e.id,e.name,e.getAttribute('type'),label,e.getAttribute('href'),e.closest('form')?.getAttribute('action')]);
  if(operation==='prepare'){
    let risk=3;const search=['www.google.com','www.youtube.com','127.0.0.1'].includes(location.hostname)&&e.matches('input[type=search],input[name=q],input[name=search_query]');
    if(a.action==='focus'||(a.action==='type'&&search))risk=1;
    if(/delete|remove|uninstall|terminate/i.test(label))risk=4;
    if(/buy|pay|purchase|transfer|delete account|password|security/i.test(label))risk=5;
    const navigation=a.action==='click'&&e.tagName==='A'&&e.href&&/^https?:/.test(e.href);
    // Anchor handlers can have side effects: execute safe navigation through tabs.update instead.
    if(navigation&&risk<4&&!/delete|remove|logout|send|purchase|checkout|payment|transfer/i.test(e.href))risk=1;
    return {risk,fingerprint,navigation:navigation?e.href:null,label,url:location.href};
  }
  if(fingerprint!==a.fingerprint)throw Error('Page target changed; request fresh approval');
  if(a.action==='focus'){e.focus();return {focused:true}}
  if(a.action==='type'){if(!e.matches('input,textarea')||e.type==='file')throw Error('Unsupported text field');e.focus();const setter=Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;setter.call(e,a.text);e.dispatchEvent(new Event('input',{bubbles:true}));return {typed:true}}
  if(a.action==='click'){e.click();return {clicked:true}}
  if(a.action==='submit'){const f=e.closest('form');if(!f)throw Error('No form');f.requestSubmit();return {submitted:true}}
  throw Error('Unsupported page action');
}
async function inject(tab,operation,args){const t=await chrome.tabs.get(tab);safePage(t.url);const results=await chrome.scripting.executeScript({target:{tabId:tab},func:pageAction,args:[operation,{...args,expectedURL:t.url}]});if(!results[0]?.result)throw Error('Page action failed');return results[0].result}
async function dispatch(op,a){
  if(op==='active_tab'){const [t]=await chrome.tabs.query({active:true,lastFocusedWindow:true});if(!t)throw Error('No active tab');return summary(t)}
  if(op==='list_tabs')return (await chrome.tabs.query({})).map(summary);
  if(['open','new_tab'].includes(op)){const url=safeURL(a.url);if(op==='open'&&new URL(url).hostname==='web.whatsapp.com'){const [found]=await chrome.tabs.query({url:'https://web.whatsapp.com/*'});if(found){await chrome.tabs.update(found.id,{active:true});await chrome.windows.update(found.windowId,{focused:true});return summary(found)}}return summary(await chrome.tabs.create({url,active:true}))}
  if(op==='activate'){const t=await chrome.tabs.update(a.tab,{active:true});await chrome.windows.update(t.windowId,{focused:true});return summary(t)}
  if(op==='navigate')return summary(await chrome.tabs.update(a.tab,{url:safeURL(a.url)}));
  if(op==='close_tab'){await chrome.tabs.remove(a.tab);return {closed:true}}
  if(['read','scroll','media'].includes(op))return inject(a.tab,op,a);
  if(op==='prepare'){
    const observed=await inject(a.tab,'prepare',a);const tab=await chrome.tabs.get(a.tab);const host=new URL(tab.url).hostname;const service=host==='web.whatsapp.com'?'whatsapp':host==='x.com'?'x':host.includes('mail.')?'email':host;
    const ticket=crypto.randomUUID();tickets.set(ticket,{...a,...observed,expires:Date.now()+300000});for(const[k,v]of tickets)if(v.expires<Date.now())tickets.delete(k);
    return {...observed,ticket,service,service_action:/call/i.test(observed.label)?'call':/upload/i.test(observed.label)?'upload':service==='x'?'post':a.action==='submit'||a.action==='click'?'send':a.action};
  }
  if(op==='apply'){const p=tickets.get(a.ticket);tickets.delete(a.ticket);if(!p||p.expires<Date.now())throw Error('Expired action ticket');const current=await inject(p.tab,'prepare',p);if(current.fingerprint!==p.fingerprint)throw Error('Target changed');if(p.navigation)return summary(await chrome.tabs.update(p.tab,{url:safeURL(p.navigation)}));return inject(p.tab,'apply',p)}
  throw Error('Unsupported bridge operation');
}
async function loop(){if(polling)return;polling=true;try{for(;;){const {token}=await chrome.storage.local.get('token');if(!token)return;const headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};const r=await fetch(BASE+'/bridge/poll',{headers,signal:AbortSignal.timeout(25000)});if(!r.ok)return;const cmd=await r.json();if(cmd.operation==='idle')continue;if(cmd.expires*1000<Date.now())continue;const claim=await fetch(BASE+'/bridge/claim',{method:'POST',headers,signal:AbortSignal.timeout(5000),body:JSON.stringify({id:cmd.id})});if(!claim.ok)continue;let response;try{response={result:await dispatch(cmd.operation,cmd.arguments)}}catch(e){response={error:e.message}}await fetch(BASE+'/bridge/result',{method:'POST',headers,signal:AbortSignal.timeout(5000),body:JSON.stringify({id:cmd.id,...response})})}}catch{}finally{polling=false}}
chrome.alarms.create('june-poll',{periodInMinutes:.5});chrome.alarms.onAlarm.addListener(()=>loop());chrome.runtime.onMessage.addListener(()=>{loop();return false});chrome.runtime.onStartup.addListener(()=>loop());loop();
