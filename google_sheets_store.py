"""Camada SQLite transitória com estado autoritativo no Google Sheets.

Não usa arquivo local. A planilha mantém revisões completas; cada commit
envia os dados e só confirma localmente após receber confirmação remota.
"""
import json
import os
import sqlite3
import threading
import requests

TABLES = ("militares", "escala", "previsao_servico", "categoria_dia")


class GoogleSheetsError(RuntimeError):
    pass


class GoogleSheetsDatabase:
    def __init__(self):
        self.url = os.environ.get("GOOGLE_APPS_SCRIPT_URL", "").strip()
        self.token = os.environ.get("GOOGLE_SHEETS_TOKEN", "").strip()
        if not self.url.startswith("https://script.google.com/macros/s/") or not self.url.endswith("/exec"):
            raise GoogleSheetsError("GOOGLE_APPS_SCRIPT_URL inválida ou ausente.")
        if len(self.token) < 32:
            raise GoogleSheetsError("GOOGLE_SHEETS_TOKEN ausente ou muito curto (mínimo 32 caracteres).")
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
        self.in_transaction = False
        self.revision = None
        self._create_tables()
        data = self._request({"action": "load"})
        if "revision" not in data or "snapshot" not in data:
            raise GoogleSheetsError("Resposta incompleta do Apps Script: nenhuma gravação liberada.")
        self._restore(data["snapshot"])
        self.revision = int(data["revision"])

    def _request(self, payload):
        try:
            response = requests.post(
                self.url,
                json={"token": self.token, **payload},
                timeout=35,
                allow_redirects=True,
            )
            response.raise_for_status()
            parsed = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GoogleSheetsError("Não foi possível comunicar com o Google Sheets.") from exc
        if not isinstance(parsed, dict) or not parsed.get("ok"):
            error = parsed.get("error", "Erro não identificado") if isinstance(parsed, dict) else "Resposta inválida"
            raise GoogleSheetsError(f"Google Sheets recusou a operação: {error}")
        return parsed

    def carregar_ag(self):
        """Lê dados atuais da AG, sem alterar o banco de escalas."""
        with self.lock:
            dados = self._request({"action": "ag_load"})
        abas = dados.get("abas")
        if not isinstance(abas, list):
            raise GoogleSheetsError("Resposta da AG sem abas válidas.")
        return abas

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE militares (
                id INTEGER PRIMARY KEY, ord INTEGER NOT NULL, nome TEXT NOT NULL,
                su TEXT NOT NULL, status TEXT NOT NULL, obs TEXT NOT NULL DEFAULT '',
                tipo TEXT NOT NULL DEFAULT 'AMBAS'
            );
            CREATE TABLE escala (
                dia TEXT NOT NULL, militar_id INTEGER NOT NULL,
                valor TEXT NOT NULL, manual INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(dia, militar_id)
            );
            CREATE TABLE previsao_servico (
                dia TEXT NOT NULL, funcao TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(dia, funcao)
            );
            CREATE TABLE categoria_dia (
                dia TEXT PRIMARY KEY, tipo TEXT NOT NULL
                CHECK(tipo IN ('PRETA', 'VERMELHA'))
            );
        """)

    def _snapshot(self):
        resultado = {}
        for tabela in TABLES:
            cursor = self.conn.execute(f"SELECT * FROM {tabela}")
            nomes = [col[0] for col in cursor.description]
            resultado[tabela] = [dict(zip(nomes, linha)) for linha in cursor.fetchall()]
        return resultado

    def _restore(self, snapshot):
        if not isinstance(snapshot, dict) or set(snapshot.keys()) != set(TABLES):
            raise GoogleSheetsError("Snapshot inválido: confira as quatro tabelas.")
        for tabela in TABLES:
            registros = snapshot[tabela]
            if not isinstance(registros, list):
                raise GoogleSheetsError(f"Dados inválidos na tabela {tabela}.")
            colunas = [col[1] for col in self.conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
            for registro in registros:
                if not isinstance(registro, dict) or not set(registro).issubset(colunas):
                    raise GoogleSheetsError(f"Registro inválido em {tabela}.")
                keys = list(registro.keys())
                if keys:
                    self.conn.execute(
                        f"INSERT INTO {tabela} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                        tuple(registro[k] for k in keys)
                    )

    def execute(self, sql, params=None):
        normalized = sql.strip().upper()
        if normalized in ("BEGIN IMMEDIATE", "BEGIN"):
            self.lock.acquire()
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self.in_transaction = True
            except Exception:
                self.lock.release()
                raise
            return None
        with self.lock:
            return self.conn.execute(sql, params or ())

    def commit(self):
        if not self.in_transaction:
            return
        try:
            result = self._request({
                "action": "save",
                "expected_revision": self.revision,
                "snapshot": self._snapshot(),
            })
            self.conn.commit()
            self.revision = int(result["revision"])
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.in_transaction = False
            self.lock.release()

    def rollback(self):
        if self.in_transaction:
            try:
                self.conn.rollback()
            finally:
                self.in_transaction = False
                self.lock.release()

    def __enter__(self):
        self.execute("BEGIN IMMEDIATE")
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def conectar_google_sheets():
    return GoogleSheetsDatabase()
