import json
from datetime import date, timedelta

import pytest

from estoque.config import DB_PATH
from estoque.infra.migrations import apply_migrations
from estoque.infra.views import create_views
from estoque.infra.db import connect
from estoque.infra.repositories import (
    ParamsRepo,
    ProdutoRepo,
    DimConsumoRepo,
    SnapshotRepo,
    SaidaRepo,
)
from estoque.usecases.relatorios import (
    relatorio_alerta_ruptura,
    relatorio_produtos_a_vencer,
    relatorio_mais_consumidos,
    relatorio_reposicao,
)
from estoque.usecases.verificar_estoque import run_verificar


def _seed_basic_params(db_path):
    params = ParamsRepo(db_path)
    params.set_many([
        ("nivel_servico", "0.95"),
        ("mu_t_dias_uteis", "6"),
        ("sigma_t_dias_uteis", "1"),
    ])


def _seed_produto_dim(db_path):
    prod = ProdutoRepo(db_path)
    dim = DimConsumoRepo(db_path)

    # P1: fracionado (ex.: FR -> ML), fator 10 (1 FR = 10 ML)
    prod.upsert([{
        "codigo": "P1",
        "nome": "Produto Fracionado",
        "categoria": "IM",
        "controle_lotes": 1,
        "controle_validade": 1,
        "lote_min": 1,
        "lote_mult": 1,
        "quantidade_minima": 0,
    }])
    dim.upsert([{
        "codigo": "P1",
        "tipo_consumo": "dose_fracionada",
        "unidade_apresentacao": "FR",
        "unidade_clinica": "ML",
        "fator_conversao": 10.0,
        "via_aplicacao": "IM",
        "observacao": None,
    }])

    # P2: dose única (apresentação já é a unidade de consumo)
    prod.upsert([{
        "codigo": "P2",
        "nome": "Produto Dose Única",
        "categoria": "SC",
        "controle_lotes": 1,
        "controle_validade": 1,
        "lote_min": 1,
        "lote_mult": 1,
        "quantidade_minima": 0,
    }])
    dim.upsert([{
        "codigo": "P2",
        "tipo_consumo": "dose_unica",
        "unidade_apresentacao": "AMP",
        "unidade_clinica": None,
        "fator_conversao": None,
        "via_aplicacao": "SC",
        "observacao": None,
    }])


def _seed_snapshot(db_path):
    snap = SnapshotRepo(db_path)
    snap.clear()

    hoje = date.today()
    v1 = (hoje + timedelta(days=30)).isoformat()
    v2 = (hoje + timedelta(days=15)).isoformat()

    # P1 – dois lotes; em apresentação e unidade
    snap.upsert_lotes([
        {
            "codigo": "P1",
            "lote": "L1",
            "qtd_apresentacao_raw": "2 FR - Frascos",
            "qtd_unidade_raw": "8 ML - Mililitro",
            "data_entrada": hoje.isoformat(),
            "data_validade": v1,
        },
        {
            "codigo": "P1",
            "lote": "L2",
            "qtd_apresentacao_raw": "1 FR - Frascos",
            "qtd_unidade_raw": "2 ML - Mililitro",
            "data_entrada": hoje.isoformat(),
            "data_validade": v2,
        },
    ])

    # P2 – um lote
    snap.upsert_lotes([{
        "codigo": "P2",
        "lote": "L3",
        "qtd_apresentacao_raw": "3 AMP - Ampolas",
        "qtd_unidade_raw": None,
        "data_entrada": hoje.isoformat(),
        "data_validade": v1,
    }])


def _seed_saidas_para_demanda(db_path):
    saida = SaidaRepo(db_path)
    hoje = date.today()

    # P1 fracionado – 4 dias de consumo 4,5,4,3 ML ⇒ média ~4.0 ML/dia
    # Isso deixa cobertura ≈ (8+2) / 4 = 2.5 dias (considerando estoque_unid=10 ML)
    dias = [4, 5, 4, 3]
    for i, qtd in enumerate(dias):
        saida.insert({
            "data_saida": (hoje - timedelta(days=(10 - i))).isoformat(),
            "codigo": "P1",
            "quantidade_raw": f"{qtd} ML - Mililitro",
            "lote": None,
            "data_validade": None,
            "custo": None,
            "paciente": None,
            "responsavel": "user",
            "descarte_flag": 0,
        })

    # P2 dose única – algumas saídas em AMP (média diária não influencia ruptura aqui)
    for i in range(3):
        saida.insert({
            "data_saida": (hoje - timedelta(days=(5 - i))).isoformat(),
            "codigo": "P2",
            "quantidade_raw": "1 AMP - Ampola",
            "lote": None,
            "data_validade": None,
            "custo": None,
            "paciente": None,
            "responsavel": "user",
            "descarte_flag": 0,
        })


def _setup_db_with_data(tmp_path):
    db_path = tmp_path / "estoque_test.sqlite"
    apply_migrations(str(db_path))
    create_views(str(db_path))
    _seed_basic_params(str(db_path))
    _seed_produto_dim(str(db_path))
    _seed_snapshot(str(db_path))
    _seed_saidas_para_demanda(str(db_path))
    return str(db_path)


# -----------------------------
# Testes de relatórios
# -----------------------------

def test_relatorio_alerta_ruptura(tmp_path):
    db = _setup_db_with_data(tmp_path)
    # Horizonte 3 dias deve pegar P1 (cobertura ~2.5d)
    res = relatorio_alerta_ruptura(horizonte_dias=3, db_path=db)
    cods = {r["codigo"] for r in res}
    assert "P1" in cods


def test_relatorio_produtos_a_vencer_por_lote(tmp_path):
    db = _setup_db_with_data(tmp_path)
    # Janela: 60 dias – nossos lotes têm validade <= 30 dias
    res = relatorio_produtos_a_vencer(janela_dias=60, detalhar_por_lote=True, db_path=db)
    assert len(res) >= 3  # P1 L1+L2 e P2 L3
    # Deve conter os campos de quantidade numérica (V2)
    assert {"qtd_apres_num", "qtd_unid_num"}.issubset(res[0].keys())


def test_relatorio_produtos_a_vencer_agregado(tmp_path):
    db = _setup_db_with_data(tmp_path)
    res = relatorio_produtos_a_vencer(janela_dias=60, detalhar_por_lote=False, db_path=db)
    # Agrega por código – deve conter P1 e P2
    cods = {r["codigo"] for r in res}
    assert {"P1", "P2"} <= cods


def test_relatorio_mais_consumidos(tmp_path):
    # Prepara DB com migrações e produtos (nomes)
    db_path = tmp_path / "estoque_top.sqlite"
    apply_migrations(str(db_path))
    create_views(str(db_path))
    _seed_produto_dim(str(db_path))

    # Escreve demanda_mensal diretamente (ranking simples)
    with connect(str(db_path)) as c:
        c.executemany(
            "INSERT INTO demanda_mensal (ano_mes, codigo, unidade, qtd_total) VALUES (?, ?, ?, ?)",
            [
                ("2025-01", "P1", "ML", 100.0),
                ("2025-02", "P1", "ML", 50.0),
                ("2025-01", "P2", "AMP", 120.0),
                ("2025-03", "P2", "AMP", 30.0),
            ],
        )

    res = relatorio_mais_consumidos("2025-01", "2025-03", top_n=1, db_path=str(db_path))
    assert len(res) == 1
    assert res[0]["codigo"] in {"P1", "P2"}
    # P2 total = 150; P1 total = 150 – empate possível, logo aceitamos qualquer um no topo


def test_relatorio_reposicao(tmp_path):
    db = _setup_db_with_data(tmp_path)
    # Reuso do cálculo completo; como P1 tem cobertura baixa, tende a cair em REPOR/CRITICO
    res = relatorio_reposicao(db_path=db)
    assert isinstance(res, list)
    codes = {r["codigo"] for r in res}
    assert "P1" in codes
    # Checa campos chave
    rP1 = [r for r in res if r["codigo"] == "P1"][0]
    for k in ("SS", "ROP", "necessidade", "status"):
        assert k in rP1
