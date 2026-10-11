"""Default-browser navigation and a narrowly authenticated local extension channel."""
import asyncio
import json
import secrets
import time
import webbrowser
from urllib.parse import urlsplit, quote
from .security import Risk
from .tools import S,N


def navigation_url(url, runtime_port=8765):
    if not url.startswith(('http://','https://')): url='https://'+url
    parsed=urlsplit(url)
    if not parsed.hostname or parsed.scheme not in {'http','https'} or parsed.username or parsed.password:
        raise PermissionError('Only ordinary HTTP(S) browser URLs are allowed')
    if parsed.hostname in {'localhost','127.0.0.1','::1'} and parsed.port==runtime_port:
        raise PermissionError('The browser bridge cannot control June administration')
    if any(x in (parsed.path+' '+parsed.query).lower() for x in ('access_token=','api_key=','password=','authorization=')):
        raise PermissionError('Secret-bearing navigation is blocked')
    return url


class BrowserBridge:
    def __init__(self,runtime):
        self.r=runtime;self.queue=asyncio.Queue(maxsize=50);self.pending={};self.last_seen=0
        self.claimed = set()
        self.pair_code=None;self.pair_expires=0
        self.path=runtime.config.root/'data/browser-bridge.json'
        self.credentials=json.loads(self.path.read_text()) if self.path.exists() else {}

    def pairing(self):
        self.pair_code=secrets.token_urlsafe(18);self.pair_expires=time.time()+300
        return {'code':self.pair_code,'expires':self.pair_expires,'runtime':'http://127.0.0.1:'+str(self.r.config.port)}

    def pair(self,code,extension):
        import re
        if not re.fullmatch('[a-p]{32}',extension) or not self.pair_code or time.time()>self.pair_expires or not secrets.compare_digest(code,self.pair_code):
            raise PermissionError('Pairing code invalid or expired')
        self.credentials={'extension':extension,'token':secrets.token_urlsafe(32)}
        self.path.write_text(json.dumps(self.credentials),'utf-8')
        self.pair_code=None
        return {'token':self.credentials['token']}

    def authenticate(self,token,origin):
        expected=self.credentials.get('token','')
        return bool(expected and secrets.compare_digest(token,expected) and origin in {None,'chrome-extension://'+self.credentials.get('extension','')})

    def status(self):
        return {'paired':bool(self.credentials),'connected':time.time()-self.last_seen<40,'mode':'personal_browser','extension_id':self.credentials.get('extension')}

    async def request(self,operation,args=None):
        if not self.status()['connected']: raise RuntimeError('June Browser Bridge is not connected. Default-browser URL opening still works; pair the extension for tab interaction.')
        id=secrets.token_urlsafe(18);future=asyncio.get_running_loop().create_future()
        self.pending[id]=future
        try:
            try:
                self.queue.put_nowait({'id':id,'operation':operation,'arguments':args or {},'expires':time.time()+30})
            except asyncio.QueueFull:
                raise RuntimeError('Browser Bridge queue is full; wait for pending requests') from None
            result=await asyncio.wait_for(future,30)
            if result.get('error'): raise RuntimeError(result['error'])
            return result.get('result')
        finally:
            self.pending.pop(id,None)
            self.claimed.discard(id)

    def claim(self, id):
        future = self.pending.get(id)
        if self.r.config.privacy or not future or future.done() or id in self.claimed:
            raise PermissionError('Browser request cancelled, already claimed, or privacy enabled')
        self.claimed.add(id)

    def cancel_pending(self):
        for future in self.pending.values():
            if not future.done():
                future.cancel()
        self.claimed.clear()
        while not self.queue.empty():
            self.queue.get_nowait()

    async def poll(self):
        self.last_seen=time.time()
        try:
            async with asyncio.timeout(20):
                while True:
                    item=await self.queue.get()
                    if item['id'] in self.pending and item['expires']>time.time(): return item
        except TimeoutError: return {'operation':'idle'}

    def complete(self,id,result):
        future=self.pending.get(id)
        if not future or future.done() or id not in self.claimed: raise ValueError('Unknown, unclaimed, or expired browser request')
        future.set_result(result)


class PersonalBrowser:
    def __init__(self,runtime): self.r=runtime;self.bridge=BrowserBridge(runtime)

    async def open(self,url):
        url=navigation_url(url,self.r.config.port)
        if self.bridge.status()['connected']:
            result=await self.bridge.request('open',{'url':url})
            return {'mode':'personal_browser','status':'Using your browser tab',**result}
        opened=await asyncio.to_thread(webbrowser.open_new_tab,url)
        if not opened: raise RuntimeError('Windows default browser could not be opened')
        return {'mode':'personal_browser','url':url,'status':'Requested a new tab in your Windows default browser','verified':False}

    async def search(self,query,site='google'):
        url=('https://www.youtube.com/results?search_query=' if site=='youtube' else 'https://www.google.com/search?q=')+quote(query)
        return await self.open(url)

    async def active_tab(self): return await self.bridge.request('active_tab')
    async def list_tabs(self): return await self.bridge.request('list_tabs')
    async def activate(self,tab): return await self.bridge.request('activate',{'tab':tab})
    async def new_tab(self,url):
        if self.bridge.status()['connected']:
            return await self.bridge.request('new_tab',{'url':navigation_url(url,self.r.config.port)})
        return await self.open(url)
    async def navigate(self,url,tab): return await self.bridge.request('navigate',{'url':navigation_url(url,self.r.config.port),'tab':tab})
    async def read(self,tab): return await self.bridge.request('read',{'tab':tab})
    async def scroll(self,tab,amount=600): return await self.bridge.request('scroll',{'tab':tab,'amount':max(-3000,min(3000,amount))})
    async def media(self,tab,action):
        if action not in {'play','pause'}: raise ValueError('Choose play or pause')
        return await self.bridge.request('media',{'tab':tab,'action':action})
    async def prepare(self,action,args): return await self.bridge.request('prepare',{'action':action,**args})
    async def apply(self,tab,selector='',text='',ticket=''):
        if not ticket: raise PermissionError('Browser interaction requires a host-prepared target')
        return await self.bridge.request('apply',{'ticket':ticket})
    async def close_tab(self,tab): return await self.bridge.request('close_tab',{'tab':tab})

    def register(self,r):
        r.add('browser.personal.open','Open/focus URL in the existing personal browser, never isolated Chromium',self.open,{'url':S},['url'],Risk.LOCAL,external=True)
        r.add('browser.personal.new_tab','Create a tab in the existing personal browser session',self.new_tab,{'url':S},['url'],Risk.LOCAL,external=True)
        r.add('browser.personal.search','Search Google or YouTube in the personal browser',self.search,{'query':S,'site':S},['query'],Risk.LOCAL,external=True)
        r.add('browser.personal.active_tab','Read the active personal tab title and URL',self.active_tab,external=True)
        r.add('browser.personal.list_tabs','List personal tab titles and URLs; no cookies or browsing history',self.list_tabs,external=True)
        r.add('browser.personal.activate','Focus an existing personal tab',self.activate,{'tab':N},['tab'],Risk.LOCAL,external=True)
        r.add('browser.personal.navigate','Navigate an existing personal tab',self.navigate,{'url':S,'tab':N},['url','tab'],Risk.LOCAL,external=True)
        r.add('browser.personal.read','Read bounded visible text and accessible controls; sensitive fields/pages excluded',self.read,{'tab':N},['tab'],external=True)
        r.add('browser.personal.scroll','Scroll the personal tab',self.scroll,{'tab':N,'amount':N},['tab'],Risk.LOCAL,external=True)
        r.add('browser.personal.media','Play/pause page media, subject to browser playback restrictions',self.media,{'tab':N,'action':S},['tab','action'],Risk.LOCAL,external=True)
        r.add('browser.personal.close_tab','Close a tab; may discard an unsaved form',self.close_tab,{'tab':N},['tab'],Risk.SENSITIVE,external=True)
        for action in ('click','focus','type','submit'):
            r.add('browser.personal.'+action,'Interact with an observed element. Host classifies consequences and binds exact target before execution.',self.apply,{'tab':N,'selector':S,'text':S,'ticket':S},['tab','selector'],Risk.LOCAL,external=True)
