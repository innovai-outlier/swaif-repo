# estoque/infra/logger.py
"""
Sistema de logging para transações do estoque.

Este módulo configura e fornece loggers para registrar todas as operações
críticas do sistema, incluindo entradas, saídas e operações no banco de dados.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


# Flag global para habilitar/desabilitar logging
ENABLE_LOGGING = False
# Flag global para habilitar/desabilitar prints/output
ENABLE_OUTPUT = False

def print_system(*args, **kwargs):
    """Print controlado pelo ENABLE_OUTPUT."""
    if ENABLE_OUTPUT:
        print(*args, **kwargs)

# Configuração base dos loggers
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configura um logger específico com arquivo de saída.
    
    Args:
        name: Nome do logger
        log_file: Caminho do arquivo de log
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Logger configurado
    """
    # Cria o diretório de logs se não existir
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configura o logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove todos os handlers existentes (incluindo root e console)
    while logger.handlers:
        logger.removeHandler(logger.handlers[0])
    
    # Handler para arquivo
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    
    # Formatação
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(formatter)
    
    # Adiciona apenas o handler de arquivo
    logger.addHandler(file_handler)
    
    return logger

# Diretório base para logs (na pasta do módulo)
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"

# Loggers específicos para cada operação
transaction_logger = setup_logger(
    'estoque.transactions', 
    str(LOGS_DIR / 'transactions.log')
)

entrada_logger = setup_logger(
    'estoque.entradas', 
    str(LOGS_DIR / 'entradas.log')
)

saida_logger = setup_logger(
    'estoque.saidas', 
    str(LOGS_DIR / 'saidas.log')
)

database_logger = setup_logger(
    'estoque.database', 
    str(LOGS_DIR / 'database.log')
)

system_logger = setup_logger(
    'estoque.system', 
    str(LOGS_DIR / 'system.log')
)

def log_transaction(operation: str, data: Dict[str, Any], result: Optional[Any] = None, error: Optional[str] = None) -> None:
    """
    Registra uma transação completa no log.
    
    Args:
        operation: Tipo de operação (entrada, saida, etc.)
        data: Dados da transação
        result: Resultado da operação (opcional)
        error: Mensagem de erro (opcional)
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "operation": operation,
        "data": data,
        "result": result,
        "error": error,
        "success": error is None
    }
    if error:
        transaction_logger.error(f"TRANSACTION_FAILED: {operation} - {error} - Data: {data}")
    else:
        transaction_logger.info(f"TRANSACTION_SUCCESS: {operation} - Result: {result} - Data: {data}")

def log_entrada(action: str, codigo: str, quantidade: str, lote: str = None, **kwargs) -> None:
    """
    Log específico para operações de entrada.
    
    Args:
        action: Ação realizada (insert, update, delete)
        codigo: Código do produto
        quantidade: Quantidade movimentada
        lote: Lote do produto (opcional)
        **kwargs: Dados adicionais
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    log_data = {
        "action": action,
        "codigo": codigo,
        "quantidade": quantidade,
        "lote": lote,
        **kwargs
    }
    entrada_logger.info(f"ENTRADA_{action.upper()}: {log_data}")

def log_saida(action: str, codigo: str, quantidade: str, lote: str = None, **kwargs) -> None:
    """
    Log específico para operações de saída.
    
    Args:
        action: Ação realizada (insert, update, delete)
        codigo: Código do produto
        quantidade: Quantidade movimentada
        lote: Lote do produto (opcional)
        **kwargs: Dados adicionais
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    log_data = {
        "action": action,
        "codigo": codigo,
        "quantidade": quantidade,
        "lote": lote,
        **kwargs
    }
    saida_logger.info(f"SAIDA_{action.upper()}: {log_data}")

def log_database_operation(table: str, operation: str, affected_rows: int = 0, **kwargs) -> None:
    """
    Log específico para operações no banco de dados.
    
    Args:
        table: Nome da tabela
        operation: Operação SQL (INSERT, UPDATE, DELETE, SELECT)
        affected_rows: Número de linhas afetadas
        **kwargs: Dados adicionais
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    log_data = {
        "table": table,
        "operation": operation,
        "affected_rows": affected_rows,
        **kwargs
    }
    database_logger.info(f"DB_{operation}: {log_data}")

def log_system_event(event: str, details: Dict[str, Any] = None, level: str = "info") -> None:
    """
    Log para eventos do sistema.
    
    Args:
        event: Descrição do evento
        details: Detalhes adicionais (opcional)
        level: Nível do log (info, warning, error)
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    log_data = {
        "event": event,
        "details": details or {}
    }
    log_method = getattr(system_logger, level.lower(), system_logger.info)
    log_method(f"SYSTEM_EVENT: {event} - {log_data}")

def log_file_operation(operation: str, file_path: str, rows_processed: int = 0, **kwargs) -> None:
    """
    Log para operações de arquivo (importação/exportação).
    
    Args:
        operation: Tipo de operação (import, export)
        file_path: Caminho do arquivo
        rows_processed: Número de linhas processadas
        **kwargs: Dados adicionais
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return
    log_data = {
        "operation": operation,
        "file_path": file_path,
        "rows_processed": rows_processed,
        **kwargs
    }
    system_logger.info(f"FILE_{operation.upper()}: {log_data}")

def get_log_summary(log_type: str = "transactions", lines: int = 100) -> str:
    """
    Obtém um resumo dos logs recentes.
    
    Args:
        log_type: Tipo de log (transactions, entradas, saidas, database, system)
        lines: Número de linhas a retornar
    
    Returns:
        Conteúdo do log como string
    """
    if not (ENABLE_LOGGING or ENABLE_OUTPUT):
        return

    log_files = {
        "transactions": LOGS_DIR / "transactions.log",
        "entradas": LOGS_DIR / "entradas.log",
        "saidas": LOGS_DIR / "saidas.log",
        "database": LOGS_DIR / "database.log",
        "system": LOGS_DIR / "system.log"
    }
    
    log_file = log_files.get(log_type)
    if not log_file or not log_file.exists():
        return f"Log {log_type} não encontrado."
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent_lines)
    except Exception as e:
        return f"Erro ao ler log {log_type}: {str(e)}"
