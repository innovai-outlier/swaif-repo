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
from estoque.infra.logger import (
    log_system_event, log_database_operation, system_logger
)


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

def relatorio_alerta_ruptura(horizonte_dias: int = 7, db_path: str = DB_PATH) -> tuple[list[str], list[list], str | None]:
    """
    Retorna colunas, linhas e mensagem para exibição tabular no DataTable do Textual.
    Lista itens cuja projeção de cobertura (estoque_alvo / mu_d) é <= horizonte_dias.
    Considera unidade alvo conforme o tipo de consumo:
        - dose_fracionada -> unidade_clinica
        - dose_unica      -> unidade_apresentacao
    """
    log_system_event("relatorio_alerta_ruptura_start", {
        "horizonte_dias": horizonte_dias,
        "db_path": db_path
    })
    
    try:
        system_logger.info(f"REPORT_RUPTURA: Iniciando com horizonte={horizonte_dias} dias")
        
        apply_migrations(db_path)
        log_database_operation("migrations", "APPLY", 0)
        
        create_views(db_path)
        log_database_operation("views", "CREATE", 0)

        # repos e params
        produto_repo = ProdutoRepo(db_path)
        dim_repo = DimConsumoRepo(db_path)
        snap_repo = SnapshotRepo(db_path)
        dem_repo = DemandaRepo(db_path)

        system_logger.debug("REPORT_RUPTURA: Repositórios inicializados")

        # dimensões e métricas
        dim_by = dim_repo.map_by_codigo()
        log_database_operation("dim_consumo", "SELECT_MAP", len(dim_by))
        
        dem_repo.rebuild_demanda(dim_by)
        system_logger.info("REPORT_RUPTURA: Demanda reconstruída")
        
        met = dem_repo.metricas_demanda()
        log_database_operation("demanda", "SELECT_METRICS", len(met))
        m_by: Dict[Tuple[str, str], Dict] = {(m["codigo"], m["unidade"].upper()): m for m in met}

        # estoque consolidado e produtos
        est_by = {r["codigo"]: r for r in snap_repo.fetch_consolidado()}
        log_database_operation("estoque_snapshot", "SELECT_CONSOLIDATED", len(est_by))
        
        produtos = produto_repo.get_all()
        log_database_operation("produto", "SELECT_ALL", len(produtos))

        out: List[Dict] = []
        produtos_processados = 0
        produtos_com_ruptura = 0

        for p in produtos:
            produtos_processados += 1
            codigo = str(p["codigo"])
            dim = dim_by.get(codigo)
            if not dim:
                system_logger.debug(f"REPORT_RUPTURA: Produto {codigo} sem dimensão de consumo")
                continue
            if (dim.get("tipo_consumo") or "").lower() == "excluir":
                system_logger.debug(f"REPORT_RUPTURA: Produto {codigo} marcado para exclusão")
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
                system_logger.debug(f"REPORT_RUPTURA: Produto {codigo} sem mu_d válido")
                continue

            cobertura = estoque_alvo / mu_d if mu_d > 0 else None
            if cobertura is not None and cobertura <= float(horizonte_dias):
                produtos_com_ruptura += 1
                system_logger.info(f"REPORT_RUPTURA: Ruptura detectada - {codigo}: {cobertura:.2f} dias")
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

        log_system_event("relatorio_alerta_ruptura_success", {
            "produtos_processados": produtos_processados,
            "produtos_com_ruptura": produtos_com_ruptura,
            "total_resultados": len(out)
        })

        system_logger.info(f"REPORT_RUPTURA: Concluído - {produtos_com_ruptura}/{produtos_processados} produtos em ruptura")

        # Define colunas para DataTable
        columns = [
            "Código", "Nome", "Tipo Consumo", "Unidade Alvo",
            "Estoque Alvo", "Mu D", "Cobertura (dias)", "Limiar"
        ]
        # Monta linhas para DataTable
        rows = [
            [
                r.get("codigo", ""),
                r.get("nome", ""),
                r.get("tipo_consumo", ""),
                r.get("unidade_alvo", ""),
                r.get("estoque_alvo", ""),
                r.get("mu_d", ""),
                r.get("cobertura_dias", ""),
                r.get("limiar", "")
            ]
            for r in out
        ]
        msg = None
        if not rows:
            msg = "Nenhum produto em ruptura encontrado."
        return columns, rows, msg
        
    except Exception as e:
        error_msg = str(e)
        log_system_event("relatorio_alerta_ruptura_error", {
            "horizonte_dias": horizonte_dias,
            "error": error_msg
        }, level="error")
        system_logger.error(f"REPORT_RUPTURA: Erro - {error_msg}")
        raise


# ----------------------
# 2) Produtos a vencer
# ----------------------

def relatorio_produtos_a_vencer(
    janela_dias: int = 60, detalhar_por_lote: bool = True, db_path: str = DB_PATH
) -> tuple[list[str], list[list], str | None]:
    """
    Retorna colunas, linhas e mensagem para exibição tabular no DataTable do Textual.
    Lotes com data_validade até hoje + janela_dias.
    Se detalhar_por_lote=False, agrega por código somando as quantidades numéricas (V2).
    """
    log_system_event("relatorio_produtos_a_vencer_start", {
        "janela_dias": janela_dias,
        "detalhar_por_lote": detalhar_por_lote,
        "db_path": db_path
    })
    
    try:
        system_logger.info(f"REPORT_VENCIMENTOS: Iniciando com janela={janela_dias} dias, detalhe={detalhar_por_lote}")
        
        apply_migrations(db_path)
        log_database_operation("migrations", "APPLY", 0)
        
        create_views(db_path)
        log_database_operation("views", "CREATE", 0)

        hoje = date.today()
        limite = hoje + timedelta(days=janela_dias)
        
        system_logger.info(f"REPORT_VENCIMENTOS: Período - hoje: {hoje.isoformat()}, limite: {limite.isoformat()}")

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
        
        log_database_operation("estoque_lote_snapshot", "SELECT_VENCIMENTOS", len(rows))
        system_logger.info(f"REPORT_VENCIMENTOS: {len(rows)} lotes encontrados a vencer")

        if detalhar_por_lote:
            rows.sort(key=lambda r: (r.get("data_validade") or "", r.get("codigo") or "", r.get("lote") or ""))
            log_system_event("relatorio_produtos_a_vencer_success", {
                "total_lotes": len(rows),
                "modo": "detalhado_por_lote"
            })
            system_logger.info(f"REPORT_VENCIMENTOS: Retornando {len(rows)} lotes detalhados")
            columns = [
                "Código", "Lote", "Data Validade", "Qtd Apres Num", "Qtd Apres Un", "Qtd Unid Num", "Qtd Unid Un"
            ]
            data_rows = [
                [
                    r.get("codigo", ""),
                    r.get("lote", ""),
                    r.get("data_validade", ""),
                    r.get("qtd_apres_num", ""),
                    r.get("qtd_apres_un", ""),
                    r.get("qtd_unid_num", ""),
                    r.get("qtd_unid_un", "")
                ]
                for r in rows
            ]
            msg = None
            if not data_rows:
                msg = "Nenhum produto a vencer encontrado."
            return columns, data_rows, msg

        #if detalhar_por_lote:
        #    rows.sort(key=lambda r: (r.get("data_validade") or "", r.get("codigo") or "", r.get("lote") or ""))
        #    
        #    log_system_event("relatorio_produtos_a_vencer_success", {
        #        "total_lotes": len(rows),
        #        "modo": "detalhado_por_lote"
        #    })
        #    
        #    system_logger.info(f"REPORT_VENCIMENTOS: Retornando {len(rows)} lotes detalhados")
        #    return rows

        # agrega por produto
        system_logger.info("REPORT_VENCIMENTOS: Agregando por produto...")
        agg: Dict[str, Dict] = {}
        produtos_agregados = 0
        
        for r in rows:
            cod = r["codigo"]
            if cod not in agg:
                produtos_agregados += 1
                agg[cod] = {
                    "codigo": cod,
                    "qtd_apres_num": 0.0,
                    "qtd_apres_un": r.get("qtd_apres_un"),
                    "qtd_unid_num": 0.0,
                    "qtd_unid_un": r.get("qtd_unid_un"),
                    "primeira_validade": r.get("data_validade"),
                }
            
            it = agg[cod]
            it["qtd_apres_num"] += float(r.get("qtd_apres_num") or 0.0)
            it["qtd_unid_num"] += float(r.get("qtd_unid_num") or 0.0)
            # menor data de validade
            dv = r.get("data_validade")
            if dv and (it["primeira_validade"] is None or dv < it["primeira_validade"]):
                it["primeira_validade"] = dv

        out = list(agg.values())
        out.sort(key=lambda r: (r.get("primeira_validade") or ""))
        
        log_system_event("relatorio_produtos_a_vencer_success", {
            "total_lotes": len(rows),
            "produtos_agregados": produtos_agregados,
            "total_resultados": len(out),
            "modo": "agregado_por_produto"
        })
        
        system_logger.info(f"REPORT_VENCIMENTOS: {produtos_agregados} produtos agregados de {len(rows)} lotes")
        
        columns = [
            "Código", "Qtd Apres Num", "Qtd Apres Un", "Qtd Unid Num", "Qtd Unid Un", "Primeira Validade"
        ]
        data_rows = [
            [
                r.get("codigo", ""),
                r.get("qtd_apres_num", ""),
                r.get("qtd_apres_un", ""),
                r.get("qtd_unid_num", ""),
                r.get("qtd_unid_un", ""),
                r.get("primeira_validade", "")
            ]
            for r in out
        ]
        msg = None
        if not data_rows:
            msg = "Nenhum produto a vencer encontrado."
        return columns, data_rows, msg

    except Exception as e:
        error_msg = str(e)
        log_system_event("relatorio_produtos_a_vencer_error", {
            "janela_dias": janela_dias,
            "detalhar_por_lote": detalhar_por_lote,
            "error": error_msg
        }, level="error")
        system_logger.error(f"REPORT_VENCIMENTOS: Erro - {error_msg}")
        raise


# ----------------------
# 3) Mais consumidos
# ----------------------

def relatorio_mais_consumidos(
    inicio_ano_mes: str,
    fim_ano_mes: str,
    top_n: int = 20,
    db_path: str = DB_PATH,
) -> tuple[list[str], list[list], str | None]:
    """
    Retorna colunas, linhas e mensagem para exibição tabular no DataTable do Textual.
    Ranking por consumo total em demanda_mensal entre [inicio_ano_mes, fim_ano_mes], inclusive.
    Formato de ano_mes: 'YYYY-MM'.
    Soma por código e ordena decrescente. Retorna até top_n com nome de produto.
    """
    log_system_event("relatorio_mais_consumidos_start", {
        "inicio_ano_mes": inicio_ano_mes,
        "fim_ano_mes": fim_ano_mes,
        "top_n": top_n,
        "db_path": db_path
    })
    
    try:
        system_logger.info(f"REPORT_TOP_CONSUMO: Período {inicio_ano_mes} a {fim_ano_mes}, top {top_n}")
        
        apply_migrations(db_path)
        log_database_operation("migrations", "APPLY", 0)
        
        create_views(db_path)
        log_database_operation("views", "CREATE", 0)

        with connect(db_path) as c:
            cur = c.execute("SELECT codigo, nome FROM produto")
            nomes = {row[0]: row[1] for row in cur.fetchall()}
            log_database_operation("produto", "SELECT_NAMES", len(nomes))
            system_logger.info(f"REPORT_TOP_CONSUMO: {len(nomes)} produtos cadastrados")

            cur = c.execute(
                """
                SELECT ano_mes, codigo, unidade, qtd_total
                FROM demanda_mensal
                ORDER BY ano_mes, codigo, unidade
                """
            )
            rows = cur.fetchall()
            log_database_operation("demanda_mensal", "SELECT_ALL", len(rows))
            system_logger.info(f"REPORT_TOP_CONSUMO: {len(rows)} registros de demanda mensal")

        agg: Dict[str, float] = {}
        registros_processados = 0
        registros_no_periodo = 0
        
        for ano_mes, codigo, unidade, qtd_total in rows:
            registros_processados += 1
            
            if not (isinstance(ano_mes, str) and isinstance(codigo, str)):
                system_logger.debug(f"REPORT_TOP_CONSUMO: Registro inválido - ano_mes:{type(ano_mes)}, codigo:{type(codigo)}")
                continue
                
            if _between_ano_mes(inicio_ano_mes, fim_ano_mes, ano_mes):
                registros_no_periodo += 1
                qtd = float(qtd_total or 0.0)
                if codigo not in agg:
                    agg[codigo] = 0.0
                agg[codigo] += qtd
                
                system_logger.debug(f"REPORT_TOP_CONSUMO: {codigo} em {ano_mes}: +{qtd} (total: {agg[codigo]})")

        system_logger.info(f"REPORT_TOP_CONSUMO: {registros_no_periodo}/{registros_processados} registros no período")

        out = [{"codigo": cod, "nome": nomes.get(cod), "qtd_total": qtd} for cod, qtd in agg.items()]
        out.sort(key=lambda r: -r["qtd_total"])
        result = out[: max(0, int(top_n))]
        
        # Log dos top produtos
        for i, item in enumerate(result[:5]):  # Log apenas top 5 para não poluir
            system_logger.info(f"REPORT_TOP_CONSUMO: #{i+1} {item['codigo']} - {item['qtd_total']:.2f}")
        
        log_system_event("relatorio_mais_consumidos_success", {
            "registros_processados": registros_processados,
            "registros_no_periodo": registros_no_periodo,
            "produtos_com_consumo": len(agg),
            "total_resultados": len(result)
        })
        
        system_logger.info(f"REPORT_TOP_CONSUMO: Concluído - {len(agg)} produtos com consumo, retornando top {len(result)}")
        
        columns = ["Código", "Nome", "Qtd Total"]
        rows = [
            [r.get("codigo", ""), r.get("nome", ""), r.get("qtd_total", "")] for r in result
        ]
        msg = None
        if not rows:
            msg = "Nenhum produto consumido encontrado no período informado."
        return columns, rows, msg
        
    except Exception as e:
        error_msg = str(e)
        log_system_event("relatorio_mais_consumidos_error", {
            "inicio_ano_mes": inicio_ano_mes,
            "fim_ano_mes": fim_ano_mes,
            "top_n": top_n,
            "error": error_msg
        }, level="error")
        system_logger.error(f"REPORT_TOP_CONSUMO: Erro - {error_msg}")
        raise


# ----------------------
# 4) Reposição de produtos
# ----------------------

def relatorio_reposicao(db_path: str = DB_PATH) -> tuple[list[str], list[list], str | None]:
    """
    Retorna colunas, linhas e mensagem para exibição tabular no DataTable do Textual.
    Usa o cálculo completo (verificar_estoque) e filtra itens com status CRITICO ou REPOR.
    Retorna os campos principais para compra.
    """
    log_system_event("relatorio_reposicao_start", {"db_path": db_path})
    
    try:
        system_logger.info("REPORT_REPOSICAO: Iniciando análise de reposição")
        
        # Chama o verificar_estoque que já tem seu próprio logging
        todos = run_verificar(db_path=db_path)
        log_database_operation("verificar_estoque", "CALL", len(todos))
        system_logger.info(f"REPORT_REPOSICAO: {len(todos)} produtos analisados pelo verificar_estoque")
        
        out = []
        produtos_criticos = 0
        produtos_repor = 0
        
        for r in todos:
            status = r.get("status")
            if status in {"CRITICO", "REPOR"}:
                if status == "CRITICO":
                    produtos_criticos += 1
                    system_logger.warning(f"REPORT_REPOSICAO: CRÍTICO - {r.get('codigo')} - necessidade: {r.get('necessidade')}")
                else:
                    produtos_repor += 1
                    system_logger.info(f"REPORT_REPOSICAO: REPOR - {r.get('codigo')} - necessidade: {r.get('necessidade')}")
                
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
        
        log_system_event("relatorio_reposicao_success", {
            "produtos_analisados": len(todos),
            "produtos_criticos": produtos_criticos,
            "produtos_repor": produtos_repor,
            "total_reposicao": len(out)
        })
        
        system_logger.info(f"REPORT_REPOSICAO: Concluído - {produtos_criticos} críticos, {produtos_repor} para repor")
        
        columns = [
            "Código", "Nome", "Status", "Unidade Alvo", "Estoque Atual", "Mu D", "SS", "ROP", "Necessidade", "Q Sug Unidade", "Q Sug Apresentação", "Unidade Apresentação", "Unidade Clínica"
        ]
        rows = [
            [
                r.get("codigo", ""),
                r.get("nome", ""),
                r.get("status", ""),
                r.get("unidade_alvo", ""),
                r.get("estoque_atual", ""),
                r.get("mu_d", ""),
                r.get("SS", ""),
                r.get("ROP", ""),
                r.get("necessidade", ""),
                r.get("q_sug_unidade", ""),
                r.get("q_sug_apresentacao", ""),
                r.get("unidade_apresentacao", ""),
                r.get("unidade_clinica", "")
            ]
            for r in out
        ]
        msg = None
        if not rows:
            msg = "Nenhum produto crítico ou para reposição encontrado."
        return columns, rows, msg
        
    except Exception as e:
        error_msg = str(e)
        log_system_event("relatorio_reposicao_error", {"error": error_msg}, level="error")
        system_logger.error(f"REPORT_REPOSICAO: Erro - {error_msg}")
        raise
