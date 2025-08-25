# estoque/usecases/verificar_estoque.py
"""
Caso de uso: verificar estoque (recalcular demanda, ROP/SS, quantidade sugerida e status).

Fluxo:
1) Aplica migrações e cria views.
2) Lê parâmetros (nível de serviço, lead time médio e desvio).
3) Rebuild de demanda diária/mensal a partir de `saida` (descarte_flag=0).
4) Calcula métricas de demanda (µd, σd) por (codigo, unidade).
5) Consolida estoque por produto (apresentação e unidade).
6) Para cada produto (exceto `excluir`), calcula SS, ROP, necessidade e sugestões
   de compra nas escalas alvo (clínica e apresentação), cobertura e status.

Observações:
- Para `dose_fracionada`, a escala alvo é a unidade clínica.
- Para `dose_unica`, a escala alvo é a unidade de apresentação.
- Retornamos também a sugestão convertida para a outra escala (se houver fator de conversão),
  pois compras tipicamente ocorrem em apresentação.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from estoque.config import DB_PATH, DEFAULTS
from estoque.domain.formulas import (
    z_from_service_level,
    demanda_leadtime,
    sigma_leadtime,
    estoque_seguranca,
    ponto_pedido,
)
from estoque.domain.policies import status_por_escala, arredonda_multiplo
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views
from estoque.infra.repositories import (
    ParamsRepo,
    ProdutoRepo,
    DimConsumoRepo,
    SnapshotRepo,
    DemandaRepo,
)


def _pick_params(params_repo: ParamsRepo):
    """Carrega parâmetros globais, com fallback para DEFAULTS."""
    nivel_servico = params_repo.get_float("nivel_servico", DEFAULTS.nivel_servico)
    mu_t = params_repo.get_float("mu_t_dias_uteis", DEFAULTS.mu_t_dias_uteis)
    sigma_t = params_repo.get_float("sigma_t_dias_uteis", DEFAULTS.sigma_t_dias_uteis)
    return nivel_servico, mu_t, sigma_t


def _metrics_map(metrics: List[Dict]) -> Dict[Tuple[str, str], Dict]:
    """Mapeia (codigo, unidade) -> métricas {mu_d, sigma_d}."""
    out: Dict[Tuple[str, str], Dict] = {}
    for m in metrics:
        k = (str(m["codigo"]), str(m["unidade"]).upper())
        out[k] = {"mu_d": float(m["mu_d"]), "sigma_d": float(m["sigma_d"])}
    return out


def _estoque_map(consol: List[Dict]) -> Dict[str, Dict]:
    """Mapeia codigo -> estoque consolidado nas duas escalas."""
    emap: Dict[str, Dict] = {}
    for r in consol:
        emap[str(r["codigo"])] = {
            "apres_num": float(r.get("estoque_total_apres") or 0.0),
            "apres_un": (r.get("unidade_apresentacao") or None),
            "unid_num": float(r.get("estoque_total_unid") or 0.0),
            "unid_un": (r.get("unidade_unidade") or None),
        }
    return emap


def _convert_between_scales(
    qtd: Optional[float],
    src_unit: Optional[str],
    dst_unit: Optional[str],
    fator: Optional[float],
) -> Optional[float]:
    """Converte quantidade entre apresentação e clínica usando `fator_conversao`."""
    if qtd is None:
        return None
    if not src_unit or not dst_unit:
        return None
    if src_unit.upper() == dst_unit.upper():
        return float(qtd)
    if fator is None:
        return None
    try:
        fator = float(fator)
    except Exception:
        return None
    if fator == 0:
        return None
    # apresentação -> clínica: multiplica; clínica -> apresentação: divide
    # Não sabemos aqui qual lado é qual; chamador garante coerência.
    # Se der mismatch, ainda assim a conversão abaixo atende:
    if src_unit.isupper() and dst_unit.isupper():
        # Tenta os dois caminhos mas retorna None para forçar decisão explícita
        # to_cli = float(qtd) * fator
        # to_apr = float(qtd) / fator
        return None
    return None


def run_verificar(db_path: str = DB_PATH) -> List[Dict]:
    # 1) migra e views
    apply_migrations(db_path)
    create_views(db_path)

    # 2) repositórios
    params_repo = ParamsRepo(db_path)
    produto_repo = ProdutoRepo(db_path)
    dim_repo = DimConsumoRepo(db_path)
    snap_repo = SnapshotRepo(db_path)
    dem_repo = DemandaRepo(db_path)

    # 3) parâmetros globais
    nivel_servico, mu_t, sigma_t = _pick_params(params_repo)
    z = z_from_service_level(nivel_servico)

    # 4) dimensões e rebuild de demanda
    dim_by_cod = dim_repo.map_by_codigo()
    dem_repo.rebuild_demanda(dim_by_cod)
    metrics = dem_repo.metricas_demanda()
    m_by_cod_un = _metrics_map(metrics)

    # 5) estoque consolidado e produtos
    estoque_c = _estoque_map(snap_repo.fetch_consolidado())
    produtos = produto_repo.get_all()

    resultados: List[Dict] = []

    # 6) cálculo por produto
    for p in produtos:
        codigo = str(p["codigo"])
        nome = p.get("nome")
        dim = dim_by_cod.get(codigo)
        if not dim:
            # sem dimensão → não sabemos unidade alvo
            resultados.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "motivo": "sem_dimensao_consumo",
                    "status": "VERIFICAR",
                }
            )
            continue

        tipo = (dim.get("tipo_consumo") or "").strip().lower()
        if tipo == "excluir":
            # não entra no dashboard
            continue

        # Define unidades e fator
        un_apr = (dim.get("unidade_apresentacao") or "").strip().upper() or None
        un_cli = (dim.get("unidade_clinica") or "").strip().upper() or None
        fator = dim.get("fator_conversao")
        try:
            fator = float(fator) if fator is not None else None
        except Exception:
            fator = None

        # Estoque atual nas duas escalas
        est = estoque_c.get(codigo, {})
        est_apr = float(est.get("apres_num") or 0.0)
        est_cli = float(est.get("unid_num") or 0.0)

        # Escala alvo (unidade de cálculo)
        if tipo == "dose_fracionada":
            unidade_alvo = un_cli
            estoque_alvo = est_cli
        else:
            unidade_alvo = un_apr
            estoque_alvo = est_apr

        # Métricas de demanda na escala alvo
        mu_d = sigma_d = None
        if unidade_alvo:
            key = (codigo, unidade_alvo)
            if key in m_by_cod_un:
                mu_d = float(m_by_cod_un[key]["mu_d"])
                sigma_d = float(m_by_cod_un[key]["sigma_d"])

        # Sem métricas → manter VERIFICAR com dados básicos
        if mu_d is None or sigma_d is None:
            resultados.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "tipo_consumo": tipo,
                    "unidade_alvo": unidade_alvo,
                    "estoque_atual": estoque_alvo,
                    "mu_d": mu_d,
                    "sigma_d": sigma_d,
                    "mu_t": mu_t,
                    "sigma_t": sigma_t,
                    "status": "VERIFICAR",
                    "motivo": "sem_metricas_demanda",
                }
            )
            continue

        # 7) Cálculos SS/ROP
        mu_DL = demanda_leadtime(mu_d, mu_t)
        sigma_DL = sigma_leadtime(mu_d, sigma_d, mu_t, sigma_t)
        SS = estoque_seguranca(z, sigma_DL)
        ROP = ponto_pedido(mu_DL, SS)

        # 8) Necessidade e quantidades sugeridas (na escala alvo)
        necessidade = max(0.0, ROP - float(estoque_alvo or 0.0))

        # Políticas de lote
        lote_min = p.get("lote_min")
        lote_mult = p.get("lote_mult")
        try:
            lote_min = float(lote_min) if lote_min is not None else None
        except Exception:
            lote_min = None
        try:
            lote_mult = float(lote_mult) if lote_mult is not None else None
        except Exception:
            lote_mult = None

        q_sug_alvo = arredonda_multiplo(necessidade, lote_mult)
        if q_sug_alvo and lote_min:
            q_sug_alvo = max(q_sug_alvo, lote_min)

        # 9) Converter sugestão para a outra escala (se possível)
        q_sug_apresentacao = None
        q_sug_unidade = None
        if tipo == "dose_fracionada":
            # cálculo em clínica; tentar converter para apresentação
            if fator and unidade_alvo and un_apr:
                try:
                    q_sug_apresentacao = (q_sug_alvo or 0.0) / fator
                    # aplicar múltiplo também na apresentação
                    q_sug_apresentacao = arredonda_multiplo(q_sug_apresentacao, lote_mult)
                    if q_sug_apresentacao and lote_min:
                        q_sug_apresentacao = max(q_sug_apresentacao, lote_min)
                except Exception:
                    q_sug_apresentacao = None
            q_sug_unidade = q_sug_alvo
        else:
            # cálculo em apresentação; converter para clínica
            if fator and unidade_alvo and un_cli:
                try:
                    q_sug_unidade = (q_sug_alvo or 0.0) * fator
                except Exception:
                    q_sug_unidade = None
            q_sug_apresentacao = q_sug_alvo

        # 10) Cobertura (dias)
        cobertura_dias = None
        if mu_d and mu_d > 0:
            cobertura_dias = (float(estoque_alvo or 0.0)) / mu_d

        # 11) Status
        status = status_por_escala(float(estoque_alvo or 0.0), SS, ROP)

        resultados.append(
            {
                "codigo": codigo,
                "nome": nome,
                "tipo_consumo": tipo,
                "unidade_alvo": unidade_alvo,
                "estoque_atual": float(estoque_alvo or 0.0),
                "mu_d": float(mu_d),
                "sigma_d": float(sigma_d),
                "mu_t": float(mu_t),
                "sigma_t": float(sigma_t),
                "z": float(z),
                "mu_DL": float(mu_DL),
                "sigma_DL": float(sigma_DL),
                "SS": float(SS),
                "ROP": float(ROP),
                "necessidade": float(necessidade),
                "q_sug_unidade": q_sug_unidade,
                "q_sug_apresentacao": q_sug_apresentacao,
                "unidade_apresentacao": un_apr,
                "unidade_clinica": un_cli,
                "cobertura_dias": cobertura_dias,
                "status": status,
            }
        )

    # Ordena por criticidade e menor cobertura
    prioridade = {"CRITICO": 0, "REPOR": 1, "OK": 2, "VERIFICAR": 3}
    resultados.sort(key=lambda r: (prioridade.get(r.get("status", "VERIFICAR"), 9), r.get("cobertura_dias") or 1e9))

    return resultados
