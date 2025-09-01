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
from estoque.adapters.gds_loader import load_saidas_from_xlsx
from estoque.infra.db import connect
from estoque.infra.repositories import SaidaRepo, ProdutoRepo, DimConsumoRepo
from estoque.infra.logger import (
    log_transaction, log_saida, log_database_operation, 
    log_system_event, log_file_operation, print_system
)

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



def _ensure_product_exists(codigo: str, produto_data: Optional[Dict[str, Any]], db_path: str) -> None:
    """Garante que o produto existe no banco, criando com dados reais se necessário."""
    log_system_event("product_check", {"codigo": codigo})
    
    with connect(db_path) as c:
        existing = c.execute("SELECT codigo FROM produto WHERE codigo = ?", (codigo,)).fetchone()
        if existing:
            log_system_event("product_exists", {"codigo": codigo})
            return
    
    log_system_event("creating_auto_product", {"codigo": codigo, "data": produto_data})
    
    prod_repo = ProdutoRepo(db_path)
    dim_repo = DimConsumoRepo(db_path)
    prod_row = {
        "codigo": codigo,
        "nome": produto_data.get("produto") if produto_data and produto_data.get("produto") else f"Auto-created: {codigo}",
        "categoria": produto_data.get("categoria") if produto_data and produto_data.get("categoria") else "AUTO",
        "controle_lotes": 1,
        "controle_validade": 1,
        "lote_min": 1,
        "lote_mult": 1,
        "quantidade_minima": 0,
    }
    prod_repo.upsert([prod_row])
    log_database_operation("produto", "UPSERT", 1, codigo=codigo)
    
    dim_row = {
        "codigo": codigo,
        "tipo_consumo": produto_data.get("tipo_consumo") if produto_data and produto_data.get("tipo_consumo") else "dose_unica",
        "unidade_apresentacao": produto_data.get("unidade_apresentacao") if produto_data and produto_data.get("unidade_apresentacao") else "UN",
        "unidade_clinica": produto_data.get("unidade_clinica") if produto_data and produto_data.get("unidade_clinica") else "UN",
        "fator_conversao": produto_data.get("fator_conversao") if produto_data and produto_data.get("fator_conversao") else 1,
        "via_aplicacao": produto_data.get("via_aplicacao") if produto_data and produto_data.get("via_aplicacao") else "ORAL",
        "observacao": "Auto-created product",
    }
    dim_repo.upsert([dim_row])
    log_database_operation("dim_consumo", "UPSERT", 1, codigo=codigo)
    
    log_system_event("product_created", {"codigo": codigo})



def run_saida_unica(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Coleta dados via stdin e insere uma única SAÍDA."""
    log_system_event("saida_unica_start")
    
    try:
        print_system("=== Registrar SAÍDA Única ===")
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

        log_saida("manual_input", codigo, quantidade, lote, **rec)

        # Verifica se o banco está vazio e importa produtos do arquivo se necessário
        prod_repo = ProdutoRepo(db_path)
        if not prod_repo.get_all():
            log_system_event("empty_database_warning", level="warning")
            print_system("Banco vazio. Importe os produtos antes das movimentações.")
            # Aqui você pode chamar uma função para importar todos os produtos de um arquivo padrão
            # Exemplo: importar_produtos_de_xlsx('produtos.xlsx', db_path)

        # Garante que o produto existe usando os dados reais
        _ensure_product_exists(codigo, rec, db_path)

        repo = SaidaRepo(db_path)
        repo.insert(rec)
        log_database_operation("saida", "INSERT", 1, codigo=codigo, quantidade=quantidade)
        
        print_system(">> Saída registrada com sucesso.")
        
        log_transaction("saida_unica", rec, result="success")
        log_system_event("saida_unica_success", {"codigo": codigo, "quantidade": quantidade})
        
        return rec
    except Exception as e:
        error_msg = str(e)
        log_transaction("saida_unica", {"codigo": codigo if 'codigo' in locals() else "unknown"}, error=error_msg)
        log_system_event("saida_unica_error", {"error": error_msg}, level="error")
        raise



def run_saida_lote(path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Lê um XLSX de SAÍDAS e insere todas as linhas na tabela `saida`."""
    log_system_event("saida_lote_start", {"file_path": path})
    log_file_operation("import", path)
    
    try:
        rows: List[Dict[str, Any]] = load_saidas_from_xlsx(path)
        log_file_operation("import", path, rows_processed=len(rows))

        # Verifica se o banco está vazio e importa produtos do arquivo se necessário
        prod_repo = ProdutoRepo(db_path)
        if not prod_repo.get_all():
            log_system_event("empty_database_warning", level="warning")
            print_system("Banco vazio. Importe os produtos antes das movimentações.")
            # Aqui você pode chamar uma função para importar todos os produtos de um arquivo padrão
            # Exemplo: importar_produtos_de_xlsx('produtos.xlsx', db_path)

        # Garante que todos os produtos existem usando dados reais
        for row in rows:
            codigo = row.get("codigo")
            if codigo:
                _ensure_product_exists(codigo, row, db_path)
                log_saida("batch_prepare", codigo, row.get("quantidade_raw", ""), row.get("lote", ""))

        repo = SaidaRepo(db_path)
        repo.insert_many(rows)
        log_database_operation("saida", "INSERT_MANY", len(rows), file_path=path)
        
        result = {"arquivo": path, "linhas_inseridas": len(rows)}
        
        log_transaction("saida_lote", {"file": path, "rows_count": len(rows)}, result=result)
        log_system_event("saida_lote_success", {"file_path": path, "rows_inserted": len(rows)})
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_transaction("saida_lote", {"file": path}, error=error_msg)
        log_system_event("saida_lote_error", {"file_path": path, "error": error_msg}, level="error")
        raise
