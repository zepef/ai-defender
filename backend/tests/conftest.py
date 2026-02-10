"""Shared test fixtures."""


import pytest

from honeypot.app import create_app
from honeypot.registry import ToolRegistry
from honeypot.session import SessionManager
from shared.config import Config
from shared.db import init_db


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def config(tmp_db):
    return Config(db_path=tmp_db)


@pytest.fixture
def session_manager(config):
    mgr = SessionManager(config)
    yield mgr
    mgr.shutdown()


@pytest.fixture
def registry(config, session_manager):
    reg = ToolRegistry(config, session_manager)
    reg.register_defaults()
    return reg


@pytest.fixture
def app(config):
    application = create_app(config)
    application.config["TESTING"] = True
    yield application
    # Shut down the session manager created inside create_app
    session_mgr = getattr(application, "_session_manager", None)
    if session_mgr:
        session_mgr.shutdown()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session_id(session_manager):
    return session_manager.create({"name": "test-client", "version": "1.0"})
