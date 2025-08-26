# estoque/infra/repositories.py
"""
Repositórios (DAO) para acesso e manipulação de dados no SQLite.

Classes:
- ParamsRepo
- ProdutoRepo
- DimConsumoRepo
- SnapshotRepo
- EntradaRepo
- SaidaRepo
- DemandaRepo
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, is_dataclass
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .db import connect
from estoque.adapters.parsers import parse_quantidade_raw


# -------------------------
# Helpers
# -------------------------

def _as_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    if is_dataclass(row):
        return asdict(row)
    raise TypeError("row must be dict or dataclass")


def _execmany(conn, sql: str, rows: Iterable[Dict[str, Any]]):
    rows = list(rows)
    if not rows:
        return
    keys = list(rows[0].keys())
    placeholders = ",".join([f":{k}" for k in keys])
    sql_fmt = sql.format(cols=",".join(keys), vals=placeholders)
    conn.executemany(sql_fmt, rows)


# -------------------------
# Params
# -------------------------

class ParamsRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def set_many(self, items: Iterable[Tuple[str, str]]) -> None:
        with connect(self.db_path) as c:
            c.executemany(
                """
                INSERT INTO params (chave, valor)
                VALUES (?, ?)
                ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor
                """,
                list(items),
            )

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with connect(self.db_path) as c:
            row = c.execute("SELECT valor FROM params WHERE chave = ?", (key,)).fetchone()
            return row[0] if row else default

    def get_float(self, key: str, default: float) -> float:
        v = self.get(key, None)
        if v is None:
            return default
        try:
            return float(v)
        except Exception:
            return default


# -------------------------
# Produto
# -------------------------

class ProdutoRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def upsert(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = [ _as_dict(r) for r in rows ]
        with connect(self.db_path) as c:
            for r in rows:
                c.execute(
                    """
                    INSERT INTO produto
                        (codigo, nome, categoria, controle_lotes, controle_validade,
                         lote_min, lote_mult, quantidade_minima)
                    VALUES
                        (:codigo, :nome, :categoria, :controle_lotes, :controle_validade,
                         :lote_min, :lote_mult, :quantidade_minima)
                    ON CONFLICT(codigo) DO UPDATE SET
                        nome=excluded.nome,
                        categoria=excluded.categoria,
                        controle_lotes=excluded.controle_lotes,
                        controle_validade=excluded.controle_validade,
                        lote_min=excluded.lote_min,
                        lote_mult=excluded.lote_mult,
                        quantidade_minima=excluded.quantidade_minima
                    """,
                    r,
                )

    def get_all(self) -> List[Dict[str, Any]]:
        with connect(self.db_path) as c:
            cur = c.execute(
                """SELECT codigo, nome, categoria, controle_lotes, controle_validade,
                          lote_min, lote_mult, quantidade_minima
                   FROM produto"""
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


# -------------------------
# Dimensão de Consumo
# -------------------------

class DimConsumoRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def upsert(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = [ _as_dict(r) for r in rows ]
        with connect(self.db_path) as c:
            for r in rows:
                c.execute(
                    """
                    INSERT INTO dim_consumo
                        (codigo, tipo_consumo, unidade_apresentacao, unidade_clinica,
                         fator_conversao, via_aplicacao, observacao)
                    VALUES
                        (:codigo, :tipo_consumo, :unidade_apresentacao, :unidade_clinica,
                         :fator_conversao, :via_aplicacao, :observacao)
                    ON CONFLICT(codigo) DO UPDATE SET
                        tipo_consumo=excluded.tipo_consumo,
                        unidade_apresentacao=excluded.unidade_apresentacao,
                        unidade_clinica=excluded.unidade_clinica,
                        fator_conversao=excluded.fator_conversao,
                        via_aplicacao=excluded.via_aplicacao,
                        observacao=excluded.observacao
                    """,
                    r,
                )

    def map_by_codigo(self) -> Dict[str, Dict[str, Any]]:
        with connect(self.db_path) as c:
            cur = c.execute(
                """SELECT codigo, tipo_consumo, unidade_apresentacao, unidade_clinica,
                          fator_conversao, via_aplicacao, observacao
                   FROM dim_consumo"""
            )
            cols = [d[0] for d in cur.description]
            return {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}


# -------------------------
# Snapshot de lotes
# -------------------------

class SnapshotRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def clear(self) -> None:
        with connect(self.db_path) as c:
            c.execute("DELETE FROM estoque_lote_snapshot")

    def upsert_lotes(self, rows: Iterable[Dict[str, Any]]) -> None:
        """Insere lotes no snapshot, preenchendo as colunas numéricas (V2)."""
        rows = [ _as_dict(r) for r in rows ]
        with connect(self.db_path) as c:
            for r in rows:
                qtd_apres_num, qtd_apres_un, _ = parse_quantidade_raw(r.get("qtd_apresentacao_raw"))
                qtd_unid_num,  qtd_unid_un,  _ = parse_quantidade_raw(r.get("qtd_unidade_raw"))
                payload = {
                    "codigo": r.get("codigo"),
                    "lote": r.get("lote"),
                    "qtd_apresentacao_raw": r.get("qtd_apresentacao_raw"),
                    "qtd_unidade_raw": r.get("qtd_unidade_raw"),
                    "data_entrada": r.get("data_entrada"),
                    "data_validade": r.get("data_validade"),
                    "qtd_apres_num": qtd_apres_num,
                    "qtd_apres_un": qtd_apres_un,
                    "qtd_unid_num": qtd_unid_num,
                    "qtd_unid_un": qtd_unid_un,
                }
                c.execute(
                    """
                    INSERT INTO estoque_lote_snapshot
                        (codigo, lote, qtd_apresentacao_raw, qtd_unidade_raw,
                         data_entrada, data_validade,
                         qtd_apres_num, qtd_apres_un, qtd_unid_num, qtd_unid_un)
                    VALUES
                        (:codigo, :lote, :qtd_apresentacao_raw, :qtd_unidade_raw,
                         :data_entrada, :data_validade,
                         :qtd_apres_num, :qtd_apres_un, :qtd_unid_num, :qtd_unid_un)
                    """,
                    payload,
                )

    def fetch_consolidado(self) -> List[Dict[str, Any]]:
        with connect(self.db_path) as c:
            cur = c.execute(
                """
                SELECT
                    codigo,
                    COALESCE(SUM(qtd_apres_num), 0.0) AS estoque_total_apres,
                    MAX(qtd_apres_un)                 AS unidade_apresentacao,
                    COALESCE(SUM(qtd_unid_num), 0.0)  AS estoque_total_unid,
                    MAX(qtd_unid_un)                  AS unidade_unidade
                FROM estoque_lote_snapshot
                GROUP BY codigo
                """
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


# -------------------------
# Movimentações: Entrada / Saída
# -------------------------

class EntradaRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, row: Dict[str, Any]) -> None:
        row = _as_dict(row)
        # Provide default None for responsavel if missing (for backwards compatibility)
        if "responsavel" not in row:
            row["responsavel"] = None
        with connect(self.db_path) as c:
            c.execute(
                """
                INSERT INTO entrada
                    (data_entrada, codigo, quantidade_raw, lote, data_validade,
                     valor_unitario, nota_fiscal, representante, responsavel, pago)
                VALUES
                    (:data_entrada, :codigo, :quantidade_raw, :lote, :data_validade,
                     :valor_unitario, :nota_fiscal, :representante, :responsavel, :pago)
                """,
                row,
            )

    def insert_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = [ _as_dict(r) for r in rows ]
        if not rows:
            return
        # Provide default None for responsavel if missing (for backwards compatibility)
        for row in rows:
            if "responsavel" not in row:
                row["responsavel"] = None
        with connect(self.db_path) as c:
            c.executemany(
                """
                INSERT INTO entrada
                    (data_entrada, codigo, quantidade_raw, lote, data_validade,
                     valor_unitario, nota_fiscal, representante, responsavel, pago)
                VALUES
                    (:data_entrada, :codigo, :quantidade_raw, :lote, :data_validade,
                     :valor_unitario, :nota_fiscal, :representante, :responsavel, :pago)
                """,
                rows,
            )


class SaidaRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, row: Dict[str, Any]) -> None:
        row = _as_dict(row)
        with connect(self.db_path) as c:
            c.execute(
                """
                INSERT INTO saida
                    (data_saida, codigo, quantidade_raw, lote, data_validade,
                     custo, paciente, responsavel, descarte_flag)
                VALUES
                    (:data_saida, :codigo, :quantidade_raw, :lote, :data_validade,
                     :custo, :paciente, :responsavel, :descarte_flag)
                """,
                row,
            )

    def insert_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = [ _as_dict(r) for r in rows ]
        if not rows:
            return
        with connect(self.db_path) as c:
            c.executemany(
                """
                INSERT INTO saida
                    (data_saida, codigo, quantidade_raw, lote, data_validade,
                     custo, paciente, responsavel, descarte_flag)
                VALUES
                    (:data_saida, :codigo, :quantidade_raw, :lote, :data_validade,
                     :custo, :paciente, :responsavel, :descarte_flag)
                """,
                rows,
            )


# -------------------------
# Demanda
# -------------------------

class DemandaRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # --------- util interno de conversão ---------
    @staticmethod
    def _convert_quantity(
        num: Optional[float],
        unit_out: Optional[str],
        dim: Dict[str, Any],
    ) -> Tuple[Optional[float], Optional[str]]:
        """Converte quantidade da saída para a unidade-alvo da dimensão."""
        if num is None:
            return None, None
        tipo = (dim.get("tipo_consumo") or "").strip().lower()
        un_apr = (dim.get("unidade_apresentacao") or "").strip().upper() or None
        un_cli = (dim.get("unidade_clinica") or "").strip().upper() or None
        fator = dim.get("fator_conversao")  # pode ser None ou str/float
        try:
            fator = float(fator) if fator is not None else None
        except Exception:
            fator = None

        # Define a unidade alvo
        if tipo == "dose_fracionada":
            target = un_cli
        else:
            target = un_apr

        if target is None:
            return None, None

        u_out = (unit_out or "").strip().upper() or None
        if u_out == target:
            return float(num), target

        if fator is None:
            # Sem fator não há conversão segura
            return None, None

        # Conversões: apresentação <-> clínica
        if u_out == un_apr and target == un_cli:
            return float(num) * fator, target
        if u_out == un_cli and target == un_apr:
            # evitar divisão por zero
            if fator == 0:
                return None, None
            return float(num) / fator, target

        # Unidades diferentes e não mapeadas
        return None, None

    def rebuild_demanda(self, dim_consumo_by_codigo: Dict[str, Dict[str, Any]]) -> None:
        """Reconstrói demanda_diaria e demanda_mensal a partir das saídas."""
        # Carrega todas as saídas não-descarte
        with connect(self.db_path) as c:
            cur = c.execute(
                """
                SELECT data_saida, codigo, quantidade_raw
                FROM saida
                WHERE COALESCE(descarte_flag, 0) = 0
                """
            )
            rows = cur.fetchall()

        # Agrega por (data, codigo, unidade_alvo)
        agg: Dict[Tuple[str, str, str], float] = defaultdict(float)

        for data_saida, codigo, quantidade_raw in rows:
            if not codigo:
                continue
            dim = dim_consumo_by_codigo.get(codigo)
            if not dim:
                # Sem dimensão de consumo, não temos a unidade alvo
                continue
            num, unit_out, _ = parse_quantidade_raw(quantidade_raw)
            num_conv, unit_target = self._convert_quantity(num, unit_out, dim)
            if num_conv is None or unit_target is None:
                # pula linhas não conversíveis
                continue
            # normaliza data para YYYY-MM-DD
            d = (str(data_saida)[:10]) if data_saida else None
            if not d:
                continue
            agg[(d, codigo, unit_target)] += float(num_conv)

        # Regrava demanda_diaria e demanda_mensal
        with connect(self.db_path) as c:
            c.execute("DELETE FROM demanda_diaria")
            c.execute("DELETE FROM demanda_mensal")

            # diária
            for (data, codigo, unidade), qtd_total in agg.items():
                c.execute(
                    """
                    INSERT INTO demanda_diaria (data, codigo, unidade, qtd_total)
                    VALUES (?, ?, ?, ?)
                    """,
                    (data, codigo, unidade, float(qtd_total)),
                )

            # mensal
            mens: Dict[Tuple[str, str, str], float] = defaultdict(float)
            for (data, codigo, unidade), qtd_total in agg.items():
                ano_mes = data[:7]  # YYYY-MM
                mens[(ano_mes, codigo, unidade)] += float(qtd_total)

            for (ano_mes, codigo, unidade), qtd_total in mens.items():
                c.execute(
                    """
                    INSERT INTO demanda_mensal (ano_mes, codigo, unidade, qtd_total)
                    VALUES (?, ?, ?, ?)
                    """,
                    (ano_mes, codigo, unidade, float(qtd_total)),
                )

    def metricas_demanda(self) -> List[Dict[str, Any]]:
        """Calcula métricas (mu_d, sigma_d) por (codigo, unidade) a partir da demanda diária."""
        with connect(self.db_path) as c:
            cur = c.execute(
                """
                SELECT codigo, unidade, data, qtd_total
                FROM demanda_diaria
                ORDER BY codigo, unidade, data
                """
            )
            rows = cur.fetchall()

        series: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        for codigo, unidade, _data, qtd_total in rows:
            try:
                v = float(qtd_total)
            except Exception:
                continue
            series[(codigo, unidade)].append(v)

        out: List[Dict[str, Any]] = []
        for (codigo, unidade), valores in series.items():
            if not valores:
                continue
            mu = mean(valores)
            # desvio padrão populacional; se preferir amostral, troque por statistics.stdev
            sigma = pstdev(valores) if len(valores) > 1 else 0.0
            out.append(
                {
                    "codigo": codigo,
                    "unidade": unidade,
                    "mu_d": float(mu),
                    "sigma_d": float(sigma),
                }
            )
        return out
