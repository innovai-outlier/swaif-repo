# estoque/usecases/registrar_entrada.py
"""
UC: Registrar ENTRADAS (única e em lote).

Obs.:
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from estoque.config import DB_PATH
from estoque.adapters.gds_loader import load_entradas_from_xlsx
from estoque.infra.db import connect
from estoque.infra.repositories import EntradaRepo, ProdutoRepo, DimConsumoRepo
from estoque.infra.logger import (
    log_transaction, log_entrada, log_database_operation, 
    log_system_event, log_file_operation, print_system
)

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
    # Usa dados reais se disponíveis
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



def run_entrada_unica(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Coleta dados via stdin e insere uma única ENTRADA."""
    log_system_event("entrada_unica_start")
    
    try:
        print_system("=== Registrar ENTRADA Única ===")
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

        log_entrada("manual_input", codigo, quantidade, lote, **rec)

        # Verifica se o banco está vazio e importa produtos do arquivo se necessário
        prod_repo = ProdutoRepo(db_path)
        if not prod_repo.get_all():
            log_system_event("empty_database_warning", level="warning")
            print_system("Banco vazio. Importe os produtos antes das movimentações.")
            # Aqui você pode chamar uma função para importar todos os produtos de um arquivo padrão
            # Exemplo: importar_produtos_de_xlsx('produtos.xlsx', db_path)

        # Garante que o produto existe usando os dados reais
        _ensure_product_exists(codigo, rec, db_path)

        repo = EntradaRepo(db_path)
        repo.insert(rec)
        log_database_operation("entrada", "INSERT", 1, codigo=codigo, quantidade=quantidade)
        
        print_system(">> Entrada registrada com sucesso.")
        
        log_transaction("entrada_unica", rec, result="success")
        log_system_event("entrada_unica_success", {"codigo": codigo, "quantidade": quantidade})
        
        return rec
    except Exception as e:
        error_msg = str(e)
        log_transaction("entrada_unica", {"codigo": codigo if 'codigo' in locals() else "unknown"}, error=error_msg)
        log_system_event("entrada_unica_error", {"error": error_msg}, level="error")
        raise



def run_entrada_lote(path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Lê um XLSX de ENTRADAS e insere todas as linhas na tabela `entrada`."""
    log_system_event("entrada_lote_start", {"file_path": path})
    log_file_operation("import", path)
    
    try:
        rows: List[Dict[str, Any]] = load_entradas_from_xlsx(path)
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
                log_entrada("batch_prepare", codigo, row.get("quantidade_raw", ""), row.get("lote", ""))

        repo = EntradaRepo(db_path)
        repo.insert_many(rows)
        log_database_operation("entrada", "INSERT_MANY", len(rows), file_path=path)
        
        result = {"arquivo": path, "linhas_inseridas": len(rows)}
        
        log_transaction("entrada_lote", {"file": path, "rows_count": len(rows)}, result=result)
        log_system_event("entrada_lote_success", {"file_path": path, "rows_inserted": len(rows)})
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        log_transaction("entrada_lote", {"file": path}, error=error_msg)
        log_system_event("entrada_lote_error", {"file_path": path, "error": error_msg}, level="error")
        raise
