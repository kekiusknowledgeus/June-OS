from dataclasses import dataclass, field
from typing import Protocol
import httpx


@dataclass
class Command:
    name: str
    parameters: dict = field(default_factory=dict)


@dataclass
class State:
    observed_at: float
    values: dict


class Sensor(Protocol):
    async def observe(self) -> State: ...


class Actuator(Protocol):
    async def execute(self, command: Command) -> dict: ...


class Device(Protocol):
    async def status(self) -> State: ...
    async def stop(self) -> dict: ...


class HttpDevice:
    """Adapter for user-registered hardware gateways. No devices are invented."""
    def __init__(self, url, token, commands):
        self.url, self.token, self.commands = url.rstrip("/"), token, commands

    async def status(self):
        import time
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(self.url + "/status", headers={"Authorization": "Bearer " + self.token})
            r.raise_for_status()
            return State(time.time(), r.json())

    async def execute(self, command):
        if command.name not in self.commands:
            raise PermissionError("Command not registered by hardware owner")
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(self.url + "/commands/" + command.name, headers={"Authorization": "Bearer " + self.token}, json=command.parameters)
            r.raise_for_status()
            return r.json()

    async def stop(self):
        return await self.execute(Command("stop"))


class Robot(Protocol):
    async def status(self) -> State: ...
    async def move(self, command: Command): ...
    async def stop(self): ...
    async def look_at(self, command: Command): ...
    async def navigate(self, command: Command): ...
    async def inspect(self): ...
    async def return_home(self): ...
