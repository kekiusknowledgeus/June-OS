import asyncio
from unittest.mock import AsyncMock
import pytest
from june.browser_commands import resolve_browser_command
from june.config import Config
from june.v0_brain import JuneV0Brain
from june.runtime import Runtime


CASES = [
    ('open coursera','https://www.coursera.org'),
    ('open github','https://github.com'),
    ('open reddit','https://www.reddit.com'),
    ('open wikipedia','https://www.wikipedia.org'),
    ('open paulgraham.com','https://paulgraham.com'),
    ('go to python.org','https://python.org'),
    ('search for best machine learning course','https://www.google.com/search?q=best%20machine%20learning%20course'),
    ('search youtube for quantum mechanics','https://www.youtube.com/results?search_query=quantum%20mechanics'),
    ('google quantum mechanics','https://www.google.com/search?q=quantum%20mechanics'),
    ('open spotify','https://open.spotify.com'),
    ('open amazon','https://www.amazon.com'),
    ('open openai','https://openai.com'),
    ('open never-before-seen-site','https://www.google.com/search?q=never-before-seen-site'),
    ('open a new obscure site','https://www.google.com/search?q=a%20new%20obscure%20site'),
    ('open github.com/OpenAI/Example?x=1&y=2#Section','https://github.com/OpenAI/Example?x=1&y=2#Section'),
    ('open HTTPS://EXAMPLE.COM/Case?q=why?','https://example.com/Case?q=why?'),
    ('example.com','https://example.com'),
    ('go to docs.example.co.uk:8443/foo','https://docs.example.co.uk:8443/foo'),
    ('June, open yt.','https://youtube.com'),
    ('open YouTube and search for quantum mechanics','https://www.youtube.com/results?search_query=quantum%20mechanics'),
    ('search for C++ & C#','https://www.google.com/search?q=C%2B%2B%20%26%20C%23'),
]


@pytest.mark.parametrize('command,url',CASES)
def test_local_resolution(command,url):
    assert resolve_browser_command(command)['url']==url


@pytest.mark.parametrize('command',['open notepad','open calculator','open vs code','open neural explorer','open it','open project','open D:\\Projects\\Nova','open Nova','run tests','remember my preference'])
def test_preserves_local_commands(command):
    assert resolve_browser_command(command,lambda name:name=='nova') is None


@pytest.mark.parametrize('command',['open javascript:alert(1)','open file:///C:/secret','open https://user:password@example.com','open https://example.com:bad','open https://example.com/white space'])
def test_rejects_unsafe_or_malformed_urls_locally(command):
    with pytest.raises(ValueError): resolve_browser_command(command)


async def test_all_commands_through_jobs_without_model_inference(tmp_path,monkeypatch):
    config=Config.load(tmp_path);config.owner_mode=True;config.provider='june_v0'
    # Browser commands must use the local dispatcher, not model inference.
    provider=AsyncMock(side_effect=AssertionError('June V0 must not be called for this command'))
    monkeypatch.setattr(JuneV0Brain,'respond_stream',provider)
    opened=[]
    monkeypatch.setattr('june.personal_browser.webbrowser.open_new_tab',lambda url:opened.append(url) or True)
    r=Runtime(config)
    isolated=AsyncMock(side_effect=AssertionError('Personal command launched Playwright'))
    monkeypatch.setattr(r.browser,'start',isolated)
    try:
        for command,url in CASES:
            job=r.submit(command)
            await asyncio.wait_for(r.jobs[job['id']],5)
            result=r.store.get('job',job['id'])
            assert result['status']=='completed',result
            assert result['route']=='local_browser_command' and result['provider_calls']==0
            assert opened[-1]==url
        assert len(opened)==len(CASES)
        assert not r.store.list('inference') and not r.store.list('usage')
        assert not r.store.list('approval')
        provider.assert_not_awaited();isolated.assert_not_awaited()
        assert len([a for a in r.store.audits(500) if a.get('route')=='local_browser_command'])==len(CASES)
    finally: await r.close()


async def test_failure_and_privacy_do_not_fall_through_to_provider(tmp_path,monkeypatch):
    config=Config.load(tmp_path);config.owner_mode=True
    provider=AsyncMock(side_effect=AssertionError('Unexpected June V0 model inference'))
    monkeypatch.setattr(JuneV0Brain,'respond_stream',provider)
    monkeypatch.setattr('june.personal_browser.webbrowser.open_new_tab',lambda url:False)
    r=Runtime(config)
    try:
        for command in ['open unknownsite','open javascript:alert(1)']:
            job=r.submit(command);await asyncio.wait_for(r.jobs[job['id']],5)
            record=r.store.get('job',job['id'])
            assert record['provider_calls']==0 and record['route']=='local_browser_command'
        r.config.privacy=True
        assert 'Privacy mode' in await r.commands.dispatch('open coursera','privacy-test')
        provider.assert_not_awaited()
    finally: await r.close()
