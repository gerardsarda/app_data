"""Data access layer for the UE Valls analytics app.

Reads the FCF dataset (Lliga Elit, Grup 1) from the Supabase project `UEValls`
through PostgREST, using a read-only publishable key. All tables are protected
by row level security with SELECT-only policies, so the key cannot write.

Credentials are resolved in this order:
    1. Streamlit secrets (`.streamlit/secrets.toml`, or the Streamlit Cloud UI)
    2. Environment variables SB_URL / SB_KEY
    3. The bundled public defaults below
"""

from __future__ import annotations

import os
from typing import Dict

import pandas as pd
import requests

DEFAULT_URL = "https://ghkbgfxkhdjjsyvlywrx.supabase.co"
DEFAULT_KEY = "sb_publishable_RTfLa7gdNtKhwHZJYBgUsA_hBAPCwHi"

PAGE_SIZE = 1000
TIMEOUT = 60

# table -> deterministic ordering needed for safe pagination
TABLES: Dict[str, str] = {
    "equipos": "cod_equipo",
    "clubes": "cod_club",
    "campos": "cod_campo",
    "personas": "cod_persona",
    "partidos": "cod_acta",
    "goles": "id",
    "tarjetas": "id",
    "sustituciones": "id",
    "alineaciones": "cod_acta,cod_persona",
    "cuerpo_tecnico": "cod_acta,cod_persona",
    "sanciones": "id",
    "clasificacion_fcf": "posicion",
}


def _setting(name: str, default: str) -> str:
    try:
        import streamlit as st  # noqa: PLC0415

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def base_url() -> str:
    return _setting("SB_URL", DEFAULT_URL).rstrip("/")


def _headers(key: str, start: int, end: int) -> Dict[str, str]:
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "Range-Unit": "items",
        "Range": "%d-%d" % (start, end),
    }


def fetch_table(table: str, order: str, select: str = "*") -> pd.DataFrame:
    """Fetch a whole table, paginating with Range headers (PostgREST caps at 1000)."""
    url = base_url() + "/rest/v1/" + table
    key = _setting("SB_KEY", DEFAULT_KEY)
    rows: list = []
    offset = 0
    while True:
        resp = requests.get(
            url,
            params={"select": select, "order": order},
            headers=_headers(key, offset, offset + PAGE_SIZE - 1),
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        chunk = resp.json()
        rows.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return pd.DataFrame(rows)


def load_all() -> Dict[str, pd.DataFrame]:
    """Load every table used by the app into a dict of DataFrames."""
    return {name: fetch_table(name, order) for name, order in TABLES.items()}
