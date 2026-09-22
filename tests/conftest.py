import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database


@pytest.fixture
def db(monkeypatch):
    """Points the database module at a throwaway SQLite file for the duration of a test.

    Every database.py helper opens its own connection from the module-level DB_PATH,
    so redirecting that one attribute is enough to isolate a test from the real DB.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_db()
    yield database
    os.unlink(path)
