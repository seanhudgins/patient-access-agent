"""Shared test setup: mock data only, and a scripted stand-in for the Anthropic client so the agent
loop runs offline. No test makes a network call or needs an API key."""
import os
import pathlib
import sys
from dataclasses import dataclass, field

os.environ["DATA_BACKEND"] = "mock"  # before data_store is imported
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import agent  # noqa: E402
import tools  # noqa: E402


@dataclass
class Block:
    type: str
    text: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = ""

    def model_dump(self, exclude_none: bool = True) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


@dataclass
class Response:
    content: list
    stop_reason: str


def text(t: str, stop: str = "end_turn") -> Response:
    return Response([Block("text", text=t)], stop)


def tool(name: str, **inp) -> Response:
    tool.n += 1
    return Response([Block("tool_use", name=name, input=inp, id=f"toolu_{tool.n}")], "tool_use")


tool.n = 0


class FakeClient:
    """Returns the scripted responses in order; raises if a step is an exception."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self
        self.beta = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("model called more times than scripted")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture
def fake_model(monkeypatch):
    """fake_model(responses...) installs a scripted client and returns it."""
    monkeypatch.setattr(agent, "MODEL", "claude-haiku-5-5")

    def install(*script):
        client = FakeClient(script)
        agent.set_client(client)
        return client

    yield install
    agent.set_client(None)


def run_turn(message: str, session: dict) -> tuple[str, list[dict]]:
    """One patient turn through agent.chat; returns (final reply, events)."""
    events: list[dict] = []
    reply = ""
    for chunk in agent.chat(message, [], session, on_event=events.append):
        reply = chunk
    return reply, events


def verified(first: str, last: str, dob: str, channel: str = "web") -> dict:
    s = tools.new_session()
    s["channel"] = channel
    assert tools.verify_patient(first, last, dob, s)["success"]
    return s


MARIA = ("Maria", "Lopez", "1984-03-12")      # APT-2002 is inside 24 hours
SARAH = ("Sarah", "Bellum", "1985-06-14")     # has a controlled prescription (alprazolam)
JAMES = ("James", "Okafor", "1971-11-02")
ALEX = ("Alex", "Kim", "1995-07-28")          # no referrals, never seen by Dr. Shah's dermatology for a new visit
