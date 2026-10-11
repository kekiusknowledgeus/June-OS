"""Offline tests must never use the owner's credentials or external services."""
import socket

import pytest


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    import keyring
    from june.security import Vault

    monkeypatch.setattr(keyring, 'get_password', lambda *args: None)
    monkeypatch.setattr(Vault, 'get', lambda self, name: self.values.get(name))
    observed = lambda: {'title': 'Offline test fixture', 'handle': 0, 'pid': 0,
                        'rect': [0, 0, 100, 100], 'observed_at': 0}
    monkeypatch.setattr('june.windows.active_window', observed)
    monkeypatch.setattr('june.context.active_window', observed)

    original_connect = socket.socket.connect

    def blocked(sock, address):
        # Windows asyncio implements its wakeup socketpair over loopback.
        if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
            return original_connect(sock, address)
        raise AssertionError('Network access is forbidden in offline regression tests')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
