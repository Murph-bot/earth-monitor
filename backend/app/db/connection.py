"""Database connections. Plain psycopg3, no ORM — SQL is a feature here."""

import psycopg

from app.config import get_settings


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)
