"""
conftest.py — Shared pytest fixtures.

Sets the working directory to the project root so all relative paths
(kpi_contract.yaml, data/*.csv, etc.) resolve correctly regardless of
where pytest is invoked from.
"""

import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="session", autouse=True)
def set_project_root():
    os.chdir(ROOT)
    yield


@pytest.fixture(scope="session")
def db():
    from backend.database import init_db, get_db_connection
    init_db(os.path.join(ROOT, "data"))
    return get_db_connection()
