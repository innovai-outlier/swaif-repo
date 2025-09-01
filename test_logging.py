# Teste simples para verificar o sistema de logging
"""
Script de teste para o sistema de logging do estoque.
"""

from estoque.infra.logger import (
    log_transaction, log_entrada, log_saida, log_database_operation,
    log_system_event, log_file_operation, get_log_summary
)

def test_logging():
    """Testa todas as funcionalidades de logging."""
    
    print("🧪 Testando sistema de logging...")
    
    # Teste de log de sistema
    log_system_event("test_start", {"test_id": "logging_system_test"})
    
    # Teste de log de entrada
    log_entrada("test_insert", "PROD001", "10 UN", "LOTE123", 
                data_entrada="2025-01-15", representante="Test User")
    
    # Teste de log de saída
    log_saida("test_insert", "PROD001", "5 UN", "LOTE123",
              data_saida="2025-01-16", paciente="Test Patient")
    
    # Teste de log de banco de dados
    log_database_operation("produto", "INSERT", 1, codigo="PROD001", nome="Test Product")
    
    # Teste de log de arquivo
    log_file_operation("import", "test_file.xlsx", rows_processed=50)
    
    # Teste de log de transação
    log_transaction("test_operation", 
                   {"type": "test", "data": "sample"}, 
                   result={"success": True, "rows": 10})
    
    # Teste de erro
    log_transaction("test_error", 
                   {"type": "test_error"}, 
                   error="Test error message")
    
    log_system_event("test_complete", {"test_id": "logging_system_test"})
    
    print("✅ Logs de teste criados com sucesso!")
    print("\n📋 Resumo dos logs recentes:")
    
    # Mostra resumo dos logs
    for log_type in ["transactions", "entradas", "saidas", "database", "system"]:
        print(f"\n--- {log_type.upper()} ---")
        summary = get_log_summary(log_type, lines=5)
        if summary and summary.strip():
            print(summary.split('\n')[-5:] if len(summary.split('\n')) > 5 else summary)
        else:
            print("Nenhum log encontrado.")

if __name__ == "__main__":
    test_logging()
