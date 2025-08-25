# estoque/domain/models.py
"""
Modelos (dataclasses) do domínio.

Observação importante:
- Os repositórios aceitam dicionários; as dataclasses são opcionais
  e servem para tipagem/clareza. Use-as quando fizer sentido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Params:
    """Parâmetros globais (armazenados na tabela `params` como chave/valor)."""
    nivel_servico: float = 0.95
    mu_t_dias_uteis: float = 6.0
    sigma_t_dias_uteis: float = 1.0


@dataclass
class Produto:
    """Cadastro de produto básico."""
    codigo: str
    nome: Optional[str] = None
    categoria: Optional[str] = None
    controle_lotes: int = 1          # 0/1
    controle_validade: int = 1       # 0/1
    lote_min: Optional[float] = None
    lote_mult: Optional[float] = None
    quantidade_minima: Optional[float] = None


@dataclass
class DimConsumo:
    """Configuração de consumo por produto."""
    codigo: str
    tipo_consumo: str                       # 'dose_fracionada' | 'dose_unica' | 'excluir'
    unidade_apresentacao: Optional[str] = None
    unidade_clinica: Optional[str] = None
    fator_conversao: Optional[float] = None # ex.: 1 FR = 10 ML => fator=10
    via_aplicacao: Optional[str] = None     # IM/EV/SC (livre)
    observacao: Optional[str] = None
