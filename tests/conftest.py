
import os
os.environ["DATABASE_URL"] = "postgresql://user:password@localhost:5432/testdb"

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.main import app
from app.db.session import get_db

@pytest.fixture(scope="module")
def client():
    # Override get_db dependency
    async def override_get_db():
        from unittest.mock import AsyncMock, MagicMock
        mock_session = AsyncMock()
        
        # Mock execute result - needs to be a regular Mock, not AsyncMock
        # because the result of await execute() is a Result object, not a coroutine
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        
        # execute() is async and returns the mock_result when awaited
        mock_session.execute.return_value = mock_result
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()  # add is synchronous
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}
