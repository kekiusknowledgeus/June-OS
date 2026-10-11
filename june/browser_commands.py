"""Pure local navigation resolution. No provider, DNS lookup or network discovery."""
import re
from urllib.parse import quote, urlsplit, urlunsplit


ALIASES = {
    'x': 'https://x.com', 'twitter': 'https://x.com',
    'youtube': 'https://youtube.com', 'yt': 'https://youtube.com',
    'github': 'https://github.com', 'whatsapp': 'https://web.whatsapp.com',
    'whatsapp web': 'https://web.whatsapp.com', 'google': 'https://www.google.com',
}
# Deliberately small, reviewed local registry. Unknown names become searches,
# never guessed name.com addresses. This is data, not an exhaustive router.
SITE_REGISTRY = {
    'coursera': 'https://www.coursera.org', 'reddit': 'https://www.reddit.com',
    'wikipedia': 'https://www.wikipedia.org', 'spotify': 'https://open.spotify.com',
    'amazon': 'https://www.amazon.com', 'openai': 'https://openai.com',
}
LOCAL_TARGETS = {'it','this','project','the project','neural explorer','notepad',
                 'calculator','explorer','vs code','vscode','file','folder','tabs','browser tabs'}


def search_url(query, site='google'):
    base = 'https://www.youtube.com/results?search_query=' if site=='youtube' else 'https://www.google.com/search?q='
    return base + quote(query, safe='')


def domain_url(target):
    """Return a normalized explicit URL/domain, None for a name, reject unsafe URLs."""
    explicit = bool(re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I)) and not bool(re.match(r'^[\w.-]+\.\w+:\d+(?:[/?#]|$)',target))
    if explicit and not re.match(r'^https?://', target, re.I):
        raise ValueError('Only HTTP(S) browser URLs are supported.')
    if re.search(r'[\s\x00-\x1f\\]',target):
        if explicit: raise ValueError('Browser URLs cannot contain whitespace or backslashes.')
        return None
    try:
        parsed = urlsplit(target if explicit else 'https://' + target)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
        port = parsed.port
    except (ValueError,UnicodeError):
        if explicit or '.' in target: raise ValueError('Invalid browser URL.')
        return None
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('Credentials must not be included in browser URLs.')
    if not host: raise ValueError('Browser URL requires a host.')
    domain = re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]+)\.?',host)
    if not explicit and not domain: return None
    # IPv6 is allowed only in an explicitly supplied HTTP(S) URL.
    authority = '['+host+']' if ':' in host else host
    if port is not None: authority += ':'+str(port)
    return urlunsplit((parsed.scheme.lower(),authority,parsed.path,parsed.query,parsed.fragment))


def resolve_browser_command(text, is_project=lambda name: False):
    command = re.sub(r'^june[,.?\s]+','',text.strip(),flags=re.I)
    if re.match(r'^search memory for\s', command, re.I):
        return None
    search = re.fullmatch(r'(?:search(?:\s+(youtube|google))?(?:\s+for)?|google|open youtube and search for)\s+(.+)',command,re.I)
    if search:
        site=(search[1] or ('youtube' if command.lower().startswith('open youtube') else 'google')).lower()
        return {'url':search_url(search[2],site),'resolution':'search','query':search[2]}
    # Compound action requests belong to the agent loop, not a guessed search.
    if re.search(r'\b(?:and(?:\s+then)?|then)\s+(?:open|read|click|type|write|search|summarize|find|create|run|send|check|play|pause|close|switch)\b', command, re.I):
        return None
    opening = re.fullmatch(r'(open|go to|focus)\s+(.+?)(\s+in my browser)?',command,re.I)
    target = opening[2].strip() if opening else command
    if not opening and not re.match(r'(?i)^https?://|^(?:[\w-]+\.)+[\w-]+(?::\d+)?(?:[/?#]|$)',target):
        return None
    # Keep existing app/project handling and local paths out of web search.
    local_name=target.lower().rstrip('.!?')
    if opening and not opening[3] and (local_name in LOCAL_TARGETS or re.match(r'^(?:[a-z]:[\\/]|[\\/]|(?:the )?(?:file|folder|project)\s)',target,re.I)):
        return None
    url=domain_url(target)
    if url: return {'url':url,'resolution':'explicit_url'}
    if not opening: return None
    if local_name in ALIASES: return {'url':ALIASES[local_name],'resolution':'alias'}
    if not opening[3] and is_project(local_name): return None
    if local_name in SITE_REGISTRY: return {'url':SITE_REGISTRY[local_name],'resolution':'local_registry'}
    if opening[1].lower()=='focus': return None
    return {'url':search_url(target),'resolution':'search_fallback','query':target}
