"""Conexão ao armazenamento. PostgreSQL no Render; SQLite apenas para testes locais."""
import os
import sqlite3
from contextlib import contextmanager
import psycopg


class Store:
    def __init__(self, local_path):
        self.postgres = bool(os.environ.get("DATABASE_URL"))
        if self.postgres:
            self.conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, sslmode="require")
        else:
            self.conn = sqlite3.connect(local_path, timeout=20, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
        self._manual_transaction = None

    def execute(self, query, params=()):
        if self.postgres:
            query = query.replace("?", "%s")
        return self.conn.execute(query, tuple(params))

    @contextmanager
    def transaction(self):
        if self.postgres:
            with self.conn.transaction():
                yield
        else:
            with self.conn:
                yield

    def begin(self):
        if self.postgres:
            self._manual_transaction = self.conn.transaction()
            self._manual_transaction.__enter__()
        else:
            self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        if self.postgres:
            if self._manual_transaction is not None:
                self._manual_transaction.__exit__(None, None, None)
                self._manual_transaction = None
        else:
            self.conn.commit()

    def rollback(self):
        if self.postgres:
            if self._manual_transaction is not None:
                self._manual_transaction.__exit__(Exception, Exception("rollback"), None)
                self._manual_transaction = None
        else:
            self.conn.rollback()

    def init_schema(self):
        identifier = "BIGSERIAL PRIMARY KEY" if self.postgres else "INTEGER PRIMARY KEY"
        with self.transaction():
            self.execute(f"""CREATE TABLE IF NOT EXISTS militares
                (id {identifier}, ord INTEGER NOT NULL, nome TEXT NOT NULL,
                 su TEXT NOT NULL, status TEXT NOT NULL, obs TEXT NOT NULL DEFAULT '',
                 tipo TEXT NOT NULL DEFAULT 'AMBAS')""")
            self.execute("""CREATE TABLE IF NOT EXISTS escala
                (dia TEXT NOT NULL, militar_id BIGINT NOT NULL,
                 valor TEXT NOT NULL, manual INTEGER NOT NULL DEFAULT 0,
                 PRIMARY KEY (dia, militar_id))""")

    def frame(self, query, params=()):
        import pandas as pd
        cur = self.execute(query, params)
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=[col.name if hasattr(col, "name") else col[0] for col in cur.description])
