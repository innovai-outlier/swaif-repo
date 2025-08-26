# estoque/usecases/registrar_entrada.py
"""
UC: Registrar ENTRADAS (única e em lote).
- run_entrada_unica(): modo interativo via stdin (input), insere 1 linha.
- run_entrada_lote(path): lê XLSX com o adapter e insere em lote.

Obs.:
- Mantém 'quantidade_raw' como string (parse é feito em outra etapa).
- Normaliza datas para ISO quando possível.
- Converte 'pago' para 0/1 quando possível.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from estoque.config import DB_PATH
from estoque.infra.repositories import EntradaRepo, ProdutoRepo, DimConsumoRepo
from estoque.adapters.gds_loader import load_entradas_from_xlsx

# Pequenos utilitários locais (repetidos aqui para evitar imports de privados)
def _to_bool01(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "sim", "s", "y", "yes"}:
        return 1
    if s in {"0", "false", "f", "nao", "não", "n", "no"}:
        return 0
    try:
        i = int(float(s))
        if i in (0, 1):
            return i
    except Exception:
        pass
    return None

def _normalize_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _ensure_product_exists(codigo: str, db_path: str) -> None:
    """Ensures a product exists in the database, creating it if necessary."""
    from estoque.infra.db import connect
    
    # Check if product exists
    with connect(db_path) as c:
        existing = c.execute("SELECT codigo FROM produto WHERE codigo = ?", (codigo,)).fetchone()
        if existing:
            return
    
    # Create product and dim_consumo entries
    prod_repo = ProdutoRepo(db_path)
    dim_repo = DimConsumoRepo(db_path)
    
    # Create basic product entry
    prod_repo.upsert([{
        "codigo": codigo,
        "nome": f"Auto-created: {codigo}",
        "categoria": "AUTO",
        "controle_lotes": 1,
        "controle_validade": 1,
        "lote_min": 1,
        "lote_mult": 1,
        "quantidade_minima": 0,
    }])
    
    # Create basic dim_consumo entry
    dim_repo.upsert([{
        "codigo": codigo,
        "tipo_consumo": "dose_unica",
        "unidade_apresentacao": "UN",
        "unidade_clinica": "UN",
        "fator_conversao": 1,
        "via_aplicacao": "ORAL",
        "observacao": "Auto-created product",
    }])


def run_entrada_unica(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Coleta dados via stdin e insere uma única ENTRADA."""
    print("=== Registrar ENTRADA Única ===")
    data_entrada  = input("Data de entrada (YYYY-MM-DD ou DD/MM/AAAA): ").strip()
    codigo        = input("Código do produto: ").strip()
    quantidade    = input("Quantidade (raw, ex.: '2 FR - Frascos' ou '5.00 MG - ...'): ").strip()
    lote          = input("Lote (opcional): ").strip()
    data_validade = input("Data de validade (opcional): ").strip()
    valor_unit    = input("Valor unitário (opcional): ").strip()
    nota_fiscal   = input("Nota fiscal (opcional): ").strip()
    representante = input("Representante (opcional): ").strip()
    responsavel   = input("Responsável (opcional): ").strip()
    pago          = input("Pago? (0/1, sim/nao, true/false) [opcional]: ").strip()

    rec = {
        "data_entrada":  _normalize_str(data_entrada),
        "codigo":        _normalize_str(codigo),
        "quantidade_raw":_normalize_str(quantidade),
        "lote":          _normalize_str(lote),
        "data_validade": _normalize_str(data_validade),
        "valor_unitario":_normalize_str(valor_unit),
        "nota_fiscal":   _normalize_str(nota_fiscal),
        "representante": _normalize_str(representante),
        "responsavel":   _normalize_str(responsavel),
        "pago":          _to_bool01(pago) if pago else None,
    }
    
    # Ensure product exists before inserting
    _ensure_product_exists(codigo, db_path)
    
    repo = EntradaRepo(db_path)
    repo.insert(rec)
    print(">> Entrada registrada com sucesso.")
    return rec


def run_entrada_lote(path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Lê um XLSX de ENTRADAS e insere todas as linhas na tabela `entrada`."""
    rows: List[Dict[str, Any]] = load_entradas_from_xlsx(path)
    
    # Ensure all products exist
    codigos_unicos = {row.get("codigo") for row in rows if row.get("codigo")}
    for codigo in codigos_unicos:
        _ensure_product_exists(codigo, db_path)
    
    repo = EntradaRepo(db_path)
    repo.insert_many(rows)
    return {"arquivo": path, "linhas_inseridas": len(rows)}
