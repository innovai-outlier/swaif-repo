# estoque/config.py
"""
Configurações globais e valores padrão do sistema de estoque.
"""

import os
from dataclasses import dataclass


# Caminho padrão do banco de dados SQLite
DB_PATH = os.path.join(os.getcwd(), "estoque.db")


@dataclass
class DefaultConfig:
    """Valores padrão para parâmetros do sistema."""
    nivel_servico: float = 0.95  # 95% de nível de serviço
    mu_t_dias_uteis: float = 6.0  # Lead time médio em dias úteis
    sigma_t_dias_uteis: float = 1.0  # Desvio padrão do lead time em dias úteis


# Instância global dos valores padrão
DEFAULTS = DefaultConfig()
