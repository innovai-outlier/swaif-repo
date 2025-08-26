# estoque/adapters/gds_loader.py
"""
Loaders para planilhas GDS (XLSX) de ENTRADAS e SAÍDAS.

Essas funções:
- leem planilhas XLSX usando pandas;
- normalizam cabeçalhos (acentos, variações, sinônimos);
- retornam listas de dicionários com as chaves esperadas pela camada infra.

Observações:
- Não realizam parsing de quantidade. O campo é preservado como `quantidade_raw`.
- Datas são normalizadas para ISO (YYYY-MM-DD) quando possível.
- Campos booleanos são mapeados para 0/1.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import re
from datetime import datetime


# ---------------------------
# utilitários de normalização
# ---------------------------

def _slug(s: str) -> str:
    """Normaliza cabeçalhos: minúsculas, sem acentos, sem não-alfanumérico."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    # remove acentos básicos
    acentos = dict(zip("áàâãäéèêëíìîïóòôõöúùûüç", "aaaaaeeeeiiiiooooouuuuc"))
    s = "".join(acentos.get(ch, ch) for ch in s)
    # troca não alfanum por espaço
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _safe_get(row, key):
    """Safely gets a value from pandas row, handling NA values."""
    val = row.get(key)
    if pd.isna(val) or val is None:
        return None
    return val


def _first_nonnull(*vals):
    for v in vals:
        if v is not None and not pd.isna(v):
            return v
    return None


def _to_bool01(val: Any) -> Optional[int]:
    """Converte valores variados em 0/1 (ou None)."""
    if val is None:
        return None
    # Check for pandas NA
    if hasattr(pd, 'isna') and pd.isna(val):
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if hasattr(val, '__class__') and 'NAType' in str(type(val)):
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "sim", "s", "y", "yes"}:
        return 1
    if s in {"0", "false", "f", "nao", "não", "n", "no"}:
        return 0
    # números?
    try:
        i = int(float(s))
        if i in (0, 1):
            return i
    except Exception:
        pass
    return None


def _to_date_iso(val: Any) -> Optional[str]:
    """Converte valor para data ISO (YYYY-MM-DD) se possível."""
    if val is None:
        return None
    # Check for pandas NA
    if hasattr(pd, 'isna') and pd.isna(val):
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if hasattr(val, '__class__') and 'NAType' in str(type(val)):
        return None
    # pandas já pode vir como Timestamp
    if isinstance(val, (pd.Timestamp, )):
        try:
            return val.date().isoformat()
        except Exception:
            return None
    s = str(val).strip()
    if not s:
        return None
    # tenta parsing robusto com pandas
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(d):
            return None
        return d.date().isoformat()
    except Exception:
        pass
    # fallback manual rápido
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    return None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas com base em sinônimos/variações."""
    # mapeamentos por 'slug' para chaves canônicas
    aliases = {
        # comuns
        "codigo": "codigo",
        "cod": "codigo",
        "id": "codigo",

        "quantidade": "quantidade_raw",
        "qtde": "quantidade_raw",
        "qtd": "quantidade_raw",
        "quantidade apresentacao": "quantidade_raw",
        "quantidade unidade": "quantidade_raw",

        "lote": "lote",

        "data": "data",
        "data entrada": "data_entrada",
        "entrada": "data_entrada",
        "data de entrada": "data_entrada",

        "data saida": "data_saida",
        "saida": "data_saida",
        "data de saida": "data_saida",

        "validade": "data_validade",
        "data validade": "data_validade",

        "valor unitario": "valor_unitario",
        "valor": "valor_unitario",
        "preco": "valor_unitario",
        "preco unitario": "valor_unitario",

        "nota fiscal": "nota_fiscal",
        "nf": "nota_fiscal",

        "representante": "representante",
        "responsavel": "responsavel",

        "pago": "pago",
        "pagamento": "pago",
        "quitado": "pago",

        "custo": "custo",
        "paciente": "paciente",

        "descarte": "descarte_flag",
        "descarte flag": "descarte_flag",
        "descartado": "descarte_flag",
    }

    new_cols = {}
    for col in df.columns:
        key = _slug(col)
        new_cols[col] = aliases.get(key, key)  # se não houver alias, mantém slug
    df = df.rename(columns=new_cols)
    return df


def _ensure_str_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que todas as colunas lidas venham como string (para preservar formatos)."""
    for c in df.columns:
        df[c] = df[c].astype("string")
    return df


# ---------------------------
# loaders públicos (XLSX)
# ---------------------------

def load_entradas_from_xlsx(path: str) -> List[Dict[str, Any]]:
    """Lê XLSX de ENTRADAS e retorna registros compatíveis com a tabela `entrada`.

    Campos de saída (chaves do dict por linha):
      - data_entrada: ISO date (YYYY-MM-DD) ou None
      - codigo: str | None
      - quantidade_raw: str | None
      - lote: str | None
      - data_validade: ISO date | None
      - valor_unitario: str | None  (não convertemos para float aqui)
      - nota_fiscal: str | None
      - representante: str | None
      - responsavel: str | None
      - pago: 0/1 | None
    """
    df = pd.read_excel(path, dtype="string")
    df = _ensure_str_cols(df)
    df = _normalize_columns(df)
    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        data_entrada = _first_nonnull(_safe_get(row, "data_entrada"), _safe_get(row, "data"))
        rec = {
            "data_entrada": _to_date_iso(data_entrada),
            "codigo": _safe_get(row, "codigo"),
            "quantidade_raw": _safe_get(row, "quantidade_raw"),
            "lote": _safe_get(row, "lote"),
            "data_validade": _to_date_iso(_safe_get(row, "data_validade")),
            "valor_unitario": _safe_get(row, "valor_unitario"),
            "nota_fiscal": _safe_get(row, "nota_fiscal"),
            "representante": _safe_get(row, "representante"),
            "responsavel": _safe_get(row, "responsavel"),
            "pago": _to_bool01(_safe_get(row, "pago")),
        }
        out.append(rec)
    return out


def load_saidas_from_xlsx(path: str) -> List[Dict[str, Any]]:
    """Lê XLSX de SAÍDAS e retorna registros compatíveis com a tabela `saida`.

    Campos de saída (chaves do dict por linha):
      - data_saida: ISO date (YYYY-MM-DD) ou None
      - codigo: str | None
      - quantidade_raw: str | None
      - lote: str | None
      - data_validade: ISO date | None
      - custo: str | None (não convertemos para float aqui)
      - paciente: str | None
      - responsavel: str | None
      - descarte_flag: 0/1 | None
    """
    df = pd.read_excel(path, dtype="string")
    df = _ensure_str_cols(df)
    df = _normalize_columns(df)
    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        data_saida = _first_nonnull(_safe_get(row, "data_saida"), _safe_get(row, "data"))
        rec = {
            "data_saida": _to_date_iso(data_saida),
            "codigo": _safe_get(row, "codigo"),
            "quantidade_raw": _safe_get(row, "quantidade_raw"),
            "lote": _safe_get(row, "lote"),
            "data_validade": _to_date_iso(_safe_get(row, "data_validade")),
            "custo": _safe_get(row, "custo"),
            "paciente": _safe_get(row, "paciente"),
            "responsavel": _safe_get(row, "responsavel"),
            "descarte_flag": _to_bool01(_safe_get(row, "descarte_flag")),
        }
        out.append(rec)
    return out
