"""
Políticas de cálculo e utilidades para o sistema de estoque.

Este módulo contém funções que encapsulam regras de negócio de
classificação de status e de arredondamento de quantidades de compra.
As funções aqui expostas são utilizadas pela camada de aplicação ao
construir o dashboard de estoque e sugerir quantidades de reposição.
"""

from __future__ import annotations

from math import ceil
from typing import Optional


def status_por_escala(estoque_num: Optional[float], ss: Optional[float], rop: Optional[float]) -> str:
    """Classifica o status do estoque de um item.

    Determina o estado de um produto de acordo com sua posição em
    relação ao estoque de segurança (SS) e ao ponto de pedido (ROP).

    Regras:
        - Se algum dos parâmetros for ``None``, retorna ``'VERIFICAR'``.
        - ``estoque_num <= ss`` → ``'CRITICO'``
        - ``estoque_num <= rop`` → ``'REPOR'``
        - ``estoque_num > rop`` → ``'OK'``

    Args:
        estoque_num: Quantidade atual de estoque (na escala relevante).
        ss: Estoque de segurança calculado.
        rop: Ponto de pedido calculado.

    Returns:
        Uma string representando o status: ``'CRITICO'``, ``'REPOR'``,
        ``'OK'`` ou ``'VERIFICAR'``.
    """
    try:
        # Converte para float se possível
        esto = float(estoque_num) if estoque_num is not None else None
        s = float(ss) if ss is not None else None
        r = float(rop) if rop is not None else None
    except Exception:
        return "VERIFICAR"

    if esto is None or s is None or r is None:
        return "VERIFICAR"
    if esto <= s:
        return "CRITICO"
    if esto <= r:
        return "REPOR"
    return "OK"


def arredonda_multiplo(x: Optional[float], mult: Optional[float]) -> Optional[float]:
    """Arredonda ``x`` para cima ao múltiplo ``mult``.

    Utilizado ao sugerir quantidades de compra em função de lotes mínimos
    ou múltiplos de pedido. Caso ``mult`` seja ``None`` ou menor ou igual a
    zero, a função retorna ``x`` sem alteração.

    Args:
        x: Quantidade a ser arredondada.
        mult: Múltiplo base.

    Returns:
        ``ceil(x / mult) * mult`` se ``mult`` for positivo; caso
        contrário, ``x``.
    """
    if x is None:
        return None
    try:
        val = float(x)
    except Exception:
        return None
    if mult is None:
        return val
    try:
        m = float(mult)
    except Exception:
        return val
    if m <= 0:
        return val
    # Usa ceil para arredondar para cima
    return ceil(val / m) * m
