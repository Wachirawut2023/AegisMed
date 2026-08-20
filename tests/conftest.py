"""Shared pytest fixtures.

`anyio_backend` pinned to asyncio so `@pytest.mark.anyio` async tests run
without pulling in trio (not a project dependency). anyio itself ships as a
transitive dependency of httpx/starlette, so no new dev dependency is needed.
"""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
