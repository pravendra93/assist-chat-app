
import os
import pytest
from sqlalchemy import text
from app.db.session import get_engine

@pytest.fixture
def anyio_backend():
    return 'asyncio'

def test_database_url_env_var():
    """
    Verify that the DATABASE_URL environment variable is set.
    """
    database_url = os.getenv("DATABASE_URL")
    assert database_url is not None, "DATABASE_URL environment variable is not set"
    assert len(database_url) > 0, "DATABASE_URL is empty"
    # Basic check to see if it looks like a postgres URL (optional but helpful)
    assert "postgresql" in database_url, "DATABASE_URL does not look like a PostgreSQL URL"

@pytest.mark.anyio
async def test_database_connection():
    """
    Verify that the application can connect to the database using the
    configuration from app.db.session.
    """
    engine = get_engine()
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1, "Database query 'SELECT 1' did not return 1"
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")
