from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from beanfeature_api.main import create_app


@pytest.fixture
def api_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    url = f"sqlite:///{tmp_path / 'test.sqlite'}"
    monkeypatch.setenv("BEANFEATURE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(create_app(url)) as client:
        yield client
