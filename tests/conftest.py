"""Project-wide pytest fixtures and policy enforcement.

- Unit tests never touch the network. Tests that need network must opt in
  via ``@pytest.mark.network`` (see ``plans/08_testing.md``).
- Random order via ``pytest-randomly`` is mandatory project-wide.
"""

from __future__ import annotations

import socket
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _block_network(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    if "network" in request.keywords:
        yield
        return

    def _forbidden(*args: object, **kwargs: object) -> socket.socket:
        raise RuntimeError(
            "Network access is blocked in unit tests. "
            "Mark the test with @pytest.mark.network to opt in."
        )

    monkeypatch.setattr(socket, "socket", _forbidden)
    yield
