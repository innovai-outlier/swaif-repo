# estoque/infra/views.py
"""
Criação de views auxiliares para consultas frequentes.

Views criadas:
- vw_lotes_detalhe:    espelha o snapshot de lotes (útil para depuração).
- vw_estoque_consolidado: consolida estoque por produto (apresentação e unidade).
- vw_demanda_mensal:   consolida demanda por ano_mes, produto e unidade.

Obs.:
- As views assumem que as migrações V1→V2 já foram aplicadas.
- Um conjunto de índices úteis também é criado, caso não existam.
"""

from __future__ import annotations

from .db import connect


def create_views(db_path: str) -> None:
    with connect(db_path) as c:
        # -----------------------
        # Views (drop + create)
        # -----------------------
        c.executescript(
            """
            ---------------------------
            -- Detalhe de lotes
            ---------------------------
            DROP VIEW IF EXISTS vw_lotes_detalhe;
            CREATE VIEW vw_lotes_detalhe AS
            SELECT
                id,
                codigo,
                lote,
                qtd_apresentacao_raw,
                qtd_unidade_raw,
                qtd_apres_num,
                qtd_apres_un,
                qtd_unid_num,
                qtd_unid_un,
                date(data_entrada)  AS data_entrada,
                date(data_validade) AS data_validade
            FROM estoque_lote_snapshot;

            ---------------------------
            -- Estoque consolidado (por produto)
            -- Usa as colunas numéricas (V2) para somatórios.
            ---------------------------
            DROP VIEW IF EXISTS vw_estoque_consolidado;
            CREATE VIEW vw_estoque_consolidado AS
            SELECT
                codigo,
                -- Estoque total na unidade de apresentação
                COALESCE(SUM(qtd_apres_num), 0.0) AS estoque_total_apres,
                -- Mantém a unidade de apresentação mais frequente/não-nula
                MAX(qtd_apres_un)                 AS unidade_apresentacao,
                -- Estoque total na unidade clínica (fracionada)
                COALESCE(SUM(qtd_unid_num), 0.0)  AS estoque_total_unid,
                MAX(qtd_unid_un)                  AS unidade_unidade
            FROM estoque_lote_snapshot
            GROUP BY codigo;

            ---------------------------
            -- Demanda mensal consolidada
            ---------------------------
            DROP VIEW IF EXISTS vw_demanda_mensal;
            CREATE VIEW vw_demanda_mensal AS
            SELECT
                ano_mes,
                codigo,
                unidade,
                SUM(qtd_total) AS qtd_total
            FROM demanda_mensal
            GROUP BY ano_mes, codigo, unidade;
            """
        )

        # --------------------------------
        # Índices úteis (IF NOT EXISTS)
        # --------------------------------
        c.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshot_codigo ON estoque_lote_snapshot(codigo);
            CREATE INDEX IF NOT EXISTS idx_snapshot_lote   ON estoque_lote_snapshot(lote);
            CREATE INDEX IF NOT EXISTS idx_saida_data      ON saida(data_saida);
            CREATE INDEX IF NOT EXISTS idx_saida_codigo    ON saida(codigo);
            CREATE INDEX IF NOT EXISTS idx_entrada_data    ON entrada(data_entrada);
            CREATE INDEX IF NOT EXISTS idx_entrada_codigo  ON entrada(codigo);
            CREATE INDEX IF NOT EXISTS idx_demanda_diaria  ON demanda_diaria(data, codigo, unidade);
            CREATE INDEX IF NOT EXISTS idx_demanda_mensal  ON demanda_mensal(ano_mes, codigo, unidade);
            """
        )
