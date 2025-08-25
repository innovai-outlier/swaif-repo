# estoque/infra/db.py
"""
Utilidades de conexão SQLite.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """
    Context manager para abrir conexão SQLite com:
    - foreign_keys ON
    - row_factory = sqlite3.Row
    - commit ao sair (rollback em caso de exceção)
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
