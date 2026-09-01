import pytest
from psycopg.conninfo import conninfo_to_dict

import db
from errors import DatabaseUnavailableError


def test_pool_settings_use_bounded_environment_defaults(monkeypatch):
    monkeypatch.delenv("DB_POOL_MIN_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_MAX_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)

    assert db.get_pool_settings() == (2, 20, 5.0)


def test_pool_conninfo_uses_libpq_scheme(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "atlas")
    monkeypatch.setenv("POSTGRES_USER", "territorio")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    parsed = conninfo_to_dict(db.get_pool_conninfo())

    assert parsed["host"] == "localhost"
    assert parsed["dbname"] == "atlas"
    assert parsed["user"] == "territorio"


def test_get_connection_raises_when_pool_is_not_initialized():
    db.close_pool()

    with pytest.raises(DatabaseUnavailableError):
        with db.get_connection():
            pass


class FakePool:
    def __init__(self):
        self.kwargs = None
        self.opened = False
        self.closed = False

    def open(self, wait=False):
        self.opened = True

    def close(self):
        self.closed = True

    def connection(self):
        return self

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_initialize_pool_uses_configured_bounds(monkeypatch):
    fake_pool = FakePool()

    def create_pool(**kwargs):
        fake_pool.kwargs = kwargs
        return fake_pool

    monkeypatch.setattr(db, "ConnectionPool", create_pool, raising=False)
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "3")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "12")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "2.5")

    db.initialize_pool()

    assert fake_pool.kwargs["min_size"] == 3
    assert fake_pool.kwargs["max_size"] == 12
    assert fake_pool.kwargs["timeout"] == 2.5
    assert fake_pool.opened is True

    db.close_pool()
    assert fake_pool.closed is True
