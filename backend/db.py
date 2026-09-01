import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from psycopg_pool import ConnectionPool, PoolTimeout

from errors import DatabaseUnavailableError


_pool = None


def get_pool_settings():
    min_size = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
    max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
    timeout = float(os.getenv("DB_POOL_TIMEOUT", "5"))

    if min_size <= 0 or max_size < min_size or timeout <= 0:
        raise ValueError("Database pool settings must use positive, ordered values.")

    return min_size, max_size, timeout


def initialize_pool():
    global _pool

    close_pool()
    min_size, max_size, timeout = get_pool_settings()
    _pool = ConnectionPool(
        conninfo=get_pool_conninfo(),
        min_size=min_size,
        max_size=max_size,
        timeout=timeout,
    )
    _pool.open(wait=True)


def close_pool():
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_connection():
    if _pool is None:
        raise DatabaseUnavailableError("Database connection pool is not initialized.")

    try:
        with _pool.connection() as connection:
            yield connection
    except PoolTimeout as caught_error:
        raise DatabaseUnavailableError("Database connection pool timed out.") from caught_error


def get_postgres_host():
    return os.getenv("POSTGRES_HOST", "db")


def get_postgres_port():
    return os.getenv("POSTGRES_PORT", "5432")


def get_postgres_db():
    return os.getenv("POSTGRES_DB", "territorio_argentino")


def get_postgres_user():
    return os.getenv("POSTGRES_USER", "territorio")


def get_postgres_password():
    return os.getenv("POSTGRES_PASSWORD", "territorio")


def get_database_url():
    user = quote_plus(get_postgres_user())
    password = quote_plus(get_postgres_password())
    host = get_postgres_host()
    port = get_postgres_port()
    database = get_postgres_db()

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def get_pool_conninfo():
    user = quote_plus(get_postgres_user())
    password = quote_plus(get_postgres_password())
    host = get_postgres_host()
    port = get_postgres_port()
    database = get_postgres_db()

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"
