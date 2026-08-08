import os
from urllib.parse import quote_plus

import psycopg


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


def get_connection():
    return psycopg.connect(
        host=get_postgres_host(),
        port=get_postgres_port(),
        dbname=get_postgres_db(),
        user=get_postgres_user(),
        password=get_postgres_password(),
    )


def get_database_url():
    user = quote_plus(get_postgres_user())
    password = quote_plus(get_postgres_password())
    host = get_postgres_host()
    port = get_postgres_port()
    database = get_postgres_db()

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
