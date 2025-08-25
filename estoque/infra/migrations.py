# estoque/infra/migrations.py
"""
Migrações de schema usando PRAGMA user_version.

V1: tabelas base
V2: adiciona colunas numéricas e de unidade no snapshot de lotes
"""

from __future__ import annotations

from typing import List
from .db import connect


SCHEMA_V1: List[str] = [
    # Parâmetros K/V
    """
    CREATE TABLE IF NOT EXISTS params (
        chave TEXT PRIMARY KEY,
        valor TEXT
    );
    """,
    # Cadastro de produtos
    """
    CREATE TABLE IF NOT EXISTS produto (
        codigo TEXT PRIMARY KEY,
        nome TEXT,
        categoria TEXT,
        controle_lotes INTEGER DEFAULT 1,
        controle_validade INTEGER DEFAULT 1,
        lote_min REAL,
        lote_mult REAL,
        quantidade_minima REAL
    );
    """,
    # Dimensão de consumo (config por produto)
    """
    CREATE TABLE IF NOT EXISTS dim_consumo (
        codigo TEXT PRIMARY KEY,
        tipo_consumo TEXT NOT NULL, -- 'dose_fracionada' | 'dose_unica' | 'excluir'
        unidade_apresentacao TEXT,
        unidade_clinica TEXT,
        fator_conversao REAL,
        via_aplicacao TEXT,
        observacao TEXT,
        FOREIGN KEY (codigo) REFERENCES produto(codigo) ON DELETE CASCADE
    );
    """,
    # Movimentações de entrada
    """
    CREATE TABLE IF NOT EXISTS entrada (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_entrada TEXT,
        codigo TEXT,
        quantidade_raw TEXT,
        lote TEXT,
        data_validade TEXT,
        valor_unitario TEXT,
        nota_fiscal TEXT,
        representante TEXT,
        responsavel TEXT,
        pago INTEGER,
        FOREIGN KEY (codigo) REFERENCES produto(codigo)
    );
    """,
    # Movimentações de saída
    """
    CREATE TABLE IF NOT EXISTS saida (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_saida TEXT,
        codigo TEXT,
        quantidade_raw TEXT,
        lote TEXT,
        data_validade TEXT,
        custo TEXT,
        paciente TEXT,
        responsavel TEXT,
        descarte_flag INTEGER,
        FOREIGN KEY (codigo) REFERENCES produto(codigo)
    );
    """,
    # Snapshot de lotes (estado atual por lote)
    """
    CREATE TABLE IF NOT EXISTS estoque_lote_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT,
        lote TEXT,
        qtd_apresentacao_raw TEXT,
        qtd_unidade_raw TEXT,
        data_entrada TEXT,
        data_validade TEXT,
        FOREIGN KEY (codigo) REFERENCES produto(codigo)
    );
    """,
    # Demanda diária consolidada (resultado do rebuild)
    """
    CREATE TABLE IF NOT EXISTS demanda_diaria (
        data TEXT,
        codigo TEXT,
        unidade TEXT,
        qtd_total REAL,
        PRIMARY KEY (data, codigo, unidade)
    );
    """,
    # Demanda mensal consolidada (resultado agregado)
    """
    CREATE TABLE IF NOT EXISTS demanda_mensal (
        ano_mes TEXT,
        codigo TEXT,
        unidade TEXT,
        qtd_total REAL,
        PRIMARY KEY (ano_mes, codigo, unidade)
    );
    """,
]

# V2: colunas numéricas no snapshot (preenchidas pelo repositorio SnapshotRepo.upsert_lotes)
SCHEMA_V2: List[str] = [
    # Add columns if not exists (SQLite não tem IF NOT EXISTS em ADD COLUMN,
    # então garantimos na mão usando PRAGMA table_info)
    # Executaremos via função auxiliar que checa presença antes.
]


def _ensure_column(conn, table: str, column: str, ddl: str) -> None:
    """Adiciona coluna se não existir."""
    cur = conn.execute(f"PRAGMA table_info({table});")
    cols = [r[1] for r in cur.fetchall()]  # r[1] é o nome da coluna
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl};")


def _apply_v1(conn) -> None:
    for sql in SCHEMA_V1:
        conn.executescript(sql)


def _apply_v2(conn) -> None:
    # estoque_lote_snapshot: colunas numéricas e unidade parseadas
    _ensure_column(conn, "estoque_lote_snapshot", "qtd_apres_num", "qtd_apres_num REAL")
    _ensure_column(conn, "estoque_lote_snapshot", "qtd_apres_un", "qtd_apres_un TEXT")
    _ensure_column(conn, "estoque_lote_snapshot", "qtd_unid_num", "qtd_unid_num REAL")
    _ensure_column(conn, "estoque_lote_snapshot", "qtd_unid_un", "qtd_unid_un TEXT")


def apply_migrations(db_path: str) -> None:
    """Aplica migrações incrementais de acordo com PRAGMA user_version."""
    with connect(db_path) as conn:
        ver = conn.execute("PRAGMA user_version;").fetchone()[0] or 0

        if ver < 1:
            _apply_v1(conn)
            conn.execute("PRAGMA user_version = 1;")
            ver = 1

        if ver < 2:
            _apply_v2(conn)
            conn.execute("PRAGMA user_version = 2;")
            ver = 2

        # versões futuras: if ver < 3: _apply_v3(...)
