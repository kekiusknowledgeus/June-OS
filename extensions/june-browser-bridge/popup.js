const status=document.getElementById('status');
document.getElementById('pair').onclick=async()=>{try{
  if(!await chrome.permissions.request({origins:['https://*/*','http://*/*']}))throw Error('Page access was not granted');
  const response=await fetch('http://127.0.0.1:8765/bridge/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.getElementById('code').value.trim(),extension:chrome.runtime.id})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Pairing failed');
  await chrome.storage.local.set({token:data.token});document.getElementById('code').value='';await chrome.runtime.sendMessage({start:true});status.textContent='Paired with local June';
}catch(e){status.textContent=e.message}};
document.getElementById('revoke').onclick=async()=>{await chrome.storage.local.remove('token');status.textContent='Disconnected. You can also revoke access in June Settings.'};
