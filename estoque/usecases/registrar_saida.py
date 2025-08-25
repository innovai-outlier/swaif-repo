# estoque/usecases/registrar_saida.py
"""
UC: Registrar SAÍDAS (única e em lote).
- run_saida_unica(): modo interativo via stdin (input), insere 1 linha.
- run_saida_lote(path): lê XLSX com o adapter e insere em lote.

Obs.:
- Mantém 'quantidade_raw' como string (parse é feito em outra etapa).
- Normaliza datas para ISO quando possível.
- Converte 'descarte_flag' para 0/1 quando possível.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from estoque.config import DB_PATH
from estoque.infra.repositories import SaidaRepo
from estoque.adapters.gds_loader import load_saidas_from_xlsx

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


def run_saida_unica(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Coleta dados via stdin e insere uma única SAÍDA."""
    print("=== Registrar SAÍDA Única ===")
    data_saida    = input("Data de saída (YYYY-MM-DD ou DD/MM/AAAA): ").strip()
    codigo        = input("Código do produto: ").strip()
    quantidade    = input("Quantidade (raw, ex.: '1 FR - Frasco' ou '12.5 MG - ...'): ").strip()
    lote          = input("Lote (opcional): ").strip()
    data_validade = input("Data de validade (opcional): ").strip()
    custo         = input("Custo (opcional): ").strip()
    paciente      = input("Paciente (opcional): ").strip()
    responsavel   = input("Responsável (opcional): ").strip()
    descarte      = input("É descarte? (0/1, sim/nao, true/false) [opcional]: ").strip()

    rec = {
        "data_saida":    _normalize_str(data_saida),
        "codigo":        _normalize_str(codigo),
        "quantidade_raw":_normalize_str(quantidade),
        "lote":          _normalize_str(lote),
        "data_validade": _normalize_str(data_validade),
        "custo":         _normalize_str(custo),
        "paciente":      _normalize_str(paciente),
        "responsavel":   _normalize_str(responsavel),
        "descarte_flag": _to_bool01(descarte) if descarte else None,
    }
    repo = SaidaRepo(db_path)
    repo.insert(rec)
    print(">> Saída registrada com sucesso.")
    return rec


def run_saida_lote(path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Lê um XLSX de SAÍDAS e insere todas as linhas na tabela `saida`."""
    rows: List[Dict[str, Any]] = load_saidas_from_xlsx(path)
    repo = SaidaRepo(db_path)
    repo.insert_many(rows)
    return {"arquivo": path, "linhas_inseridas": len(rows)}
