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
from estoque.infra.repositories import EntradaRepo, ProdutoRepo
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
    repo = EntradaRepo(db_path)
    repo.insert(rec)
    print(">> Entrada registrada com sucesso.")
    return rec


def run_entrada_lote(path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Lê um XLSX de ENTRADAS e insere todas as linhas na tabela `entrada`.
    
    Automaticamente cria produtos para códigos que não existem na base.
    """
    rows: List[Dict[str, Any]] = load_entradas_from_xlsx(path)
    
    # Extrai produtos únicos dos dados de entrada para criar automaticamente
    produtos_para_criar = {}
    for row in rows:
        codigo = row.get('codigo')
        if codigo and codigo not in produtos_para_criar:
            produtos_para_criar[codigo] = {
                'codigo': codigo,
                'nome': f'Produto {codigo}',  # Nome genérico temporário
                'categoria': 'GERAL',
                'controle_lotes': 1,  # Assume controle de lotes
                'controle_validade': 1,  # Assume controle de validade
                'lote_min': 1,
                'lote_mult': 1,
                'quantidade_minima': 0
            }
    
    # Cria produtos se necessário
    if produtos_para_criar:
        produto_repo = ProdutoRepo(db_path)
        produto_repo.upsert(produtos_para_criar.values())
        print(f">> {len(produtos_para_criar)} produtos criados/atualizados automaticamente")
    
    # Insere entradas
    repo = EntradaRepo(db_path)
    repo.insert_many(rows)
    return {
        "arquivo": path, 
        "linhas_inseridas": len(rows),
        "produtos_criados": len(produtos_para_criar)
    }
