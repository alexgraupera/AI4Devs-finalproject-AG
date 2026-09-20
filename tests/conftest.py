import pytest

from tests.database import DATABASE_URL, create_database, database_url, migrate

CORPUS_TEST_URL = database_url("test")


@pytest.fixture(scope="session", autouse=True)
def corpus_test_database() -> str:
    """Create and migrate the database the corpus tests share, once per run."""
    if not DATABASE_URL:
        return ""
    create_database(CORPUS_TEST_URL)
    migrate(CORPUS_TEST_URL)
    return CORPUS_TEST_URL
