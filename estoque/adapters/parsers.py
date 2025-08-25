"""
Utilidades de parsing para valores de quantidades.

Este módulo fornece funções para interpretar strings que representam
quantidades com unidades, no formato tipicamente encontrado nas
planilhas de entradas e saídas (por exemplo, "5.00 MG - Miligrama").
O objetivo é extrair de forma robusta o valor numérico, a unidade
abreviada e a descrição da unidade.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")

def parse_quantidade_raw(txt: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Interpreta uma string de quantidade com unidade.

    A string de entrada geralmente segue o padrão "<valor> <unidade> - <descrição>".
    O valor pode usar vírgula ou ponto como separador decimal. A unidade
    é extraída como a segunda palavra antes do hífen (se houver) e é
    retornada em letras maiúsculas. A descrição é o texto após o
    primeiro hífen.

    Exemplos:
        "5.00 MG - MILIGRAMAs" → (5.0, "MG", "MILIGRAMAS")
        "2 FR - Frascos"      → (2.0, "FR", "Frascos")
        "5,5 ml - mililitro"  → (5.5, "ML", "mililitro")

    Args:
        txt: Texto a ser interpretado.

    Returns:
        Uma tupla (numero, unidade, descricao). Qualquer valor que não
        possa ser determinado será retornado como None.
    """
    if txt is None:
        return None, None, None
    s = str(txt).strip()
    if not s:
        return None, None, None
    # Divide a string na primeira ocorrência de '-'
    head, desc = (s.split("-", 1) + [""])[:2]
    head = head.strip()
    desc = desc.strip() or None
    parts = head.split()
    # Tenta localizar o número na primeira parte
    num = None
    unidade = None
    try:
        if parts:
            m = _NUM_RE.search(parts[0])
            if m:
                num_str = m.group(0).replace(",", ".")
                num = float(num_str)
    except Exception:
        num = None
    # Unidade: a segunda palavra, se existir
    if len(parts) >= 2:
        unidade = parts[1].strip().upper() if parts[1].strip() else None
    return num, unidade, desc
