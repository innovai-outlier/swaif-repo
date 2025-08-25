# estoque/usecases/relatorios.py
"""
Relatórios de estoque:
- alerta de ruptura (horizonte em dias)
- produtos a vencer (janela de dias)
- produtos mais consumidos (intervalo de ano-mês)
- reposição de produtos (filtra do verificar)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Tuple

from estoque.config import DB_PATH
from estoque.infra.db import connect
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views
from estoque.infra.repositories import (
    ProdutoRepo,
    DimConsumoRepo,
    SnapshotRepo,
    DemandaRepo,
)
from estoque.usecases.verificar_estoque import run_verificar


# ----------------------
# util
# ----------------------

def _today_iso() -> str:
    return date.today().isoformat()


def _parse_ano_mes(s: str) -> Tuple[int, int]:
    # "YYYY-MM" -> (YYYY, MM)
    y, m = s.split("-", 1)
    return int(y), int(m)


def _between_ano_mes(a: str, b: str, x: str) -> bool:
    ya, ma = _parse_ano_mes(a)
    yb, mb = _parse_ano_mes(b)
    yx, mx = _parse_ano_mes(x)
    return (ya, ma) <= (yx, mx) <= (yb, mb)


# ----------------------
# 1) Alerta de ruptura
# ----------------------

def relatorio_alerta_ruptura(horizonte_dias: int = 7, db_path: str = DB_PATH) -> List[Dict]:
    """
    Lista itens cuja projeção de cobertura (estoque_alvo / mu_d) é <= horizonte_dias.
    Considera unidade alvo conforme o tipo de consumo:
      - dose_fracionada -> unidade_clinica
      - dose_unica      -> unidade_apresentacao
    """
    apply_migrations(db_path)
    create_views(db_path)

    # repos e params
    produto_repo = ProdutoRepo(db_path)
    dim_repo = DimConsumoRepo(db_path)
    snap_repo = SnapshotRepo(db_path)
    dem_repo = DemandaRepo(db_path)

    # dimensões e métricas
    dim_by = dim_repo.map_by_codigo()
    dem_repo.rebuild_demanda(dim_by)
    met = dem_repo.metricas_demanda()
    m_by: Dict[Tuple[str, str], Dict] = {(m["codigo"], m["unidade"].upper()): m for m in met}

    # estoque consolidado e produtos
    est_by = {r["codigo"]: r for r in snap_repo.fetch_consolidado()}
    produtos = produto_repo.get_all()

    out: List[Dict] = []
    for p in produtos:
        codigo = str(p["codigo"])
        dim = dim_by.get(codigo)
        if not dim:
            continue
        if (dim.get("tipo_consumo") or "").lower() == "excluir":
            continue

        un_apr = (dim.get("unidade_apresentacao") or "").upper() or None
        un_cli = (dim.get("unidade_clinica") or "").upper() or None
        tipo = (dim.get("tipo_consumo") or "").lower()

        est = est_by.get(codigo, {})
        est_apr = float(est.get("estoque_total_apres") or 0.0)
        est_cli = float(est.get("estoque_total_unid") or 0.0)

        if tipo == "dose_fracionada":
            unidade_alvo = un_cli
            estoque_alvo = est_cli
        else:
            unidade_alvo = un_apr
            estoque_alvo = est_apr

        mu_d = None
        if unidade_alvo:
            m = m_by.get((codigo, unidade_alvo))
            if m:
                mu_d = float(m["mu_d"])

        if not mu_d or mu_d <= 0:
            continue

        cobertura = estoque_alvo / mu_d if mu_d > 0 else None
        if cobertura is not None and cobertura <= float(horizonte_dias):
            out.append(
                {
                    "codigo": codigo,
                    "nome": p.get("nome"),
                    "tipo_consumo": tipo,
                    "unidade_alvo": unidade_alvo,
                    "estoque_alvo": estoque_alvo,
                    "mu_d": mu_d,
                    "cobertura_dias": cobertura,
                    "limiar": horizonte_dias,
                }
            )

    out.sort(key=lambda r: (r.get("cobertura_dias") or 1e9))
    return out


# ----------------------
# 2) Produtos a vencer
# ----------------------

def relatorio_produtos_a_vencer(janela_dias: int = 60, detalhar_por_lote: bool = True, db_path: str = DB_PATH) -> List[Dict]:
    """
    Lotes com data_validade até hoje + janela_dias.
    Se detalhar_por_lote=False, agrega por código somando as quantidades numéricas (V2).
    """
    apply_migrations(db_path)
    create_views(db_path)

    hoje = date.today()
    limite = hoje + timedelta(days=janela_dias)

    rows: List[Dict] = []
    with connect(db_path) as c:
        cur = c.execute(
            """
            SELECT
                codigo, lote, data_validade,
                COALESCE(qtd_apres_num, 0.0) AS qtd_apres_num,
                qtd_apres_un,
                COALESCE(qtd_unid_num, 0.0) AS qtd_unid_num,
                qtd_unid_un
            FROM estoque_lote_snapshot
            WHERE data_validade IS NOT NULL
              AND date(data_validade) <= date(?)
            """,
            (limite.isoformat(),),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    if detalhar_por_lote:
        rows.sort(key=lambda r: (r.get("data_validade") or "", r.get("codigo") or "", r.get("lote") or ""))
        return rows

    # agrega por produto
    agg: Dict[str, Dict] = {}
    for r in rows:
        cod = r["codigo"]
        it = agg.setdefault(
            cod,
            {
                "codigo": cod,
                "qtd_apres_num": 0.0,
                "qtd_apres_un": r.get("qtd_apres_un"),
                "qtd_unid_num": 0.0,
                "qtd_unid_un": r.get("qtd_unid_un"),
                "primeira_validade": r.get("data_validade"),
            },
        )
        it["qtd_apres_num"] += float(r.get("qtd_apres_num") or 0.0)
        it["qtd_unid_num"] += float(r.get("qtd_unid_num") or 0.0)
        # menor data de validade
        dv = r.get("data_validade")
        if dv and (it["primeira_validade"] is None or dv < it["primeira_validade"]):
            it["primeira_validade"] = dv

    out = list(agg.values())
    out.sort(key=lambda r: (r.get("primeira_validade") or ""))
    return out


# ----------------------
# 3) Mais consumidos
# ----------------------

def relatorio_mais_consumidos(
    inicio_ano_mes: str,
    fim_ano_mes: str,
    top_n: int = 20,
    db_path: str = DB_PATH,
) -> List[Dict]:
    """
    Ranking por consumo total em demanda_mensal entre [inicio_ano_mes, fim_ano_mes], inclusive.
    Formato de ano_mes: 'YYYY-MM'.
    Soma por código e ordena decrescente. Retorna até top_n com nome de produto.
    """
    apply_migrations(db_path)
    create_views(db_path)

    with connect(db_path) as c:
        cur = c.execute("SELECT codigo, nome FROM produto")
        nomes = {row[0]: row[1] for row in cur.fetchall()}

        cur = c.execute(
            """
            SELECT ano_mes, codigo, unidade, qtd_total
            FROM demanda_mensal
            ORDER BY ano_mes, codigo, unidade
            """
        )
        rows = cur.fetchall()

    agg: Dict[str, float] = {}
    for ano_mes, codigo, unidade, qtd_total in rows:
        if not (isinstance(ano_mes, str) and isinstance(codigo, str)):
            continue
        if _between_ano_mes(inicio_ano_mes, fim_ano_mes, ano_mes):
            agg[codigo] = agg.get(codigo, 0.0) + float(qtd_total or 0.0)

    out = [{"codigo": cod, "nome": nomes.get(cod), "qtd_total": qtd} for cod, qtd in agg.items()]
    out.sort(key=lambda r: -r["qtd_total"])
    return out[: max(0, int(top_n))]


# ----------------------
# 4) Reposição de produtos
# ----------------------

def relatorio_reposicao(db_path: str = DB_PATH) -> List[Dict]:
    """
    Usa o cálculo completo (verificar_estoque) e filtra itens com status CRITICO ou REPOR.
    Retorna os campos principais para compra.
    """
    todos = run_verificar(db_path=db_path)
    out = []
    for r in todos:
        if r.get("status") in {"CRITICO", "REPOR"}:
            out.append(
                {
                    "codigo": r.get("codigo"),
                    "nome": r.get("nome"),
                    "status": r.get("status"),
                    "unidade_alvo": r.get("unidade_alvo"),
                    "estoque_atual": r.get("estoque_atual"),
                    "mu_d": r.get("mu_d"),
                    "SS": r.get("SS"),
                    "ROP": r.get("ROP"),
                    "necessidade": r.get("necessidade"),
                    "q_sug_unidade": r.get("q_sug_unidade"),
                    "q_sug_apresentacao": r.get("q_sug_apresentacao"),
                    "unidade_apresentacao": r.get("unidade_apresentacao"),
                    "unidade_clinica": r.get("unidade_clinica"),
                }
            )
    # prioriza críticos, depois maior necessidade
    prioridade = {"CRITICO": 0, "REPOR": 1}
    out.sort(key=lambda r: (prioridade.get(r.get("status"), 9), -(r.get("necessidade") or 0.0)))
    return out
