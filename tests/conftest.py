"""Project-wide pytest fixtures and policy enforcement.

- Unit tests never touch the *network*. Tests that need network must
  opt in via ``@pytest.mark.network`` (see ``plans/08_testing.md``).
- Random order via ``pytest-randomly`` is mandatory project-wide.

The block is surgical: it only refuses outgoing INET sockets (the only
thing that can actually reach the network). Local AF_UNIX sockets are
left alone so libraries that internally rely on ``asyncio`` (zarr 3.x,
fsspec, ...) can still create their self-pipes; otherwise unit tests
that load Zarr stores from a tmp path would fail with a confusing
"network blocked" error.
"""

from __future__ import annotations

import socket as _socket
from collections.abc import Generator

import pytest

_NETWORK_FAMILIES = {_socket.AF_INET, _socket.AF_INET6}
_REAL_SOCKET = _socket.socket


def _build_blocked_socket() -> type[_socket.socket]:
    """Return a ``socket.socket`` subclass that refuses INET families."""

    class _BlockedSocket(_REAL_SOCKET):
        def __init__(self, family: int = _socket.AF_INET, *args: object, **kwargs: object) -> None:  # type: ignore[override]
            if family in _NETWORK_FAMILIES:
                raise RuntimeError(
                    "Network access is blocked in unit tests. "
                    "Mark the test with @pytest.mark.network to opt in."
                )
            super().__init__(family, *args, **kwargs)  # type: ignore[arg-type]

    return _BlockedSocket


@pytest.fixture(autouse=True)
def _block_network(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    if "network" in request.keywords:
        yield
        return
    monkeypatch.setattr(_socket, "socket", _build_blocked_socket())
    yield
