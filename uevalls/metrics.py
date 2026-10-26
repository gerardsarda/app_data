"""Metric layer: turns the raw FCF tables into analysis-ready frames.

Everything the app and the insight catalog display is derived here, so the
numbers stay identical between the validation report, the team reports and the
league rankings.

Conventions used throughout:
  * Only matches with `jugado = True` are considered. Unplayed fixtures carry
    no acta, so they have no events.
  * A goal belongs to the team it counts for (`cod_equipo_favor`). Own goals
    (`es_propia`) therefore sit with the beneficiary, never with the scorer's
    team, and they are excluded from individual scorer rankings.
  * Cards are split between players (`es_jugador = True`) and bench staff.
    Player cards are the ones used in every ranking.
  * The FCF buckets stoppage time: 45+X is published as minute 44 and 90+X as
    minute 89. Minute-based metrics inherit that distortion.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

TRAMOS = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75), (76, 90)]
TRAMO_LABELS = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"]

AMARILLA = 100
ROJA = 101

# A goal is treated as a "respuesta" when it arrives within this many minutes
# of the opponent scoring.
VENTANA_RESPUESTA = 10


def tramo(minuto: int) -> str:
    for (lo, hi), label in zip(TRAMOS, TRAMO_LABELS):
        if lo <= minuto <= hi:
            return label
    return TRAMO_LABELS[-1] if minuto > 90 else TRAMO_LABELS[0]


def _played(partidos: pd.DataFrame, jornadas: tuple | None = None) -> pd.DataFrame:
    p = partidos[partidos["jugado"]].copy()
    if jornadas:
        p = p[(p["jornada"] >= jornadas[0]) & (p["jornada"] <= jornadas[1])]
    return p


def build(raw: Dict[str, pd.DataFrame], jornadas: tuple | None = None) -> Dict[str, pd.DataFrame]:
    """Build every derived frame from the raw tables.

    `jornadas` restricts the whole app to a (first, last) matchday range; every
    derived frame is rebuilt from that subset, so the filter reaches the rankings
    and the team reports alike.
    """
    partidos = _played(raw["partidos"], jornadas)
    equipos = raw["equipos"][["cod_equipo", "nombre", "escudo"]].rename(
        columns={"nombre": "equipo"}
    )
    nombres = dict(zip(equipos["cod_equipo"], equipos["equipo"]))

    goles = _goles(raw["goles"], partidos, nombres)
    equipo_partido = _equipo_partido(partidos, goles, nombres)
    tarjetas = _tarjetas(raw["tarjetas"], partidos, raw["personas"], nombres)
    cambios = _cambios(raw["sustituciones"], partidos, raw["personas"], nombres)
    minutos = _minutos(raw["alineaciones"], raw["sustituciones"], raw["tarjetas"], partidos,
                       raw["personas"], nombres)
    resumen = _resumen_equipo(equipo_partido, goles, tarjetas, cambios,
                              raw["alineaciones"], partidos, equipos)

    return {
        "equipos": equipos,
        "personas": raw["personas"],
        "campos": raw["campos"],
        "sustituciones": raw["sustituciones"],
        "alineaciones": raw["alineaciones"],
        "partidos": partidos,
        "goles": goles,
        "equipo_partido": equipo_partido,
        "tarjetas": tarjetas,
        "cambios": cambios,
        "minutos": minutos,
        "resumen": resumen,
        "clasificacion_fcf": raw["clasificacion_fcf"],
    }


# --------------------------------------------------------------------------- #
# goals
# --------------------------------------------------------------------------- #
def _goles(goles: pd.DataFrame, partidos: pd.DataFrame, nombres: dict) -> pd.DataFrame:
    g = goles.merge(
        partidos[["cod_acta", "jornada", "fecha", "cod_equipo_local", "cod_equipo_visitante"]],
        on="cod_acta",
        how="inner",
    )
    g = g.sort_values(["cod_acta", "minuto", "id"]).reset_index(drop=True)

    local = g["favor_local"].astype(int)
    visit = 1 - local
    acum_local = local.groupby(g["cod_acta"]).cumsum() - local
    acum_visit = visit.groupby(g["cod_acta"]).cumsum() - visit

    g["marcador_local_antes"] = acum_local.values
    g["marcador_visitante_antes"] = acum_visit.values
    g["dif_antes"] = np.where(
        g["favor_local"],
        g["marcador_local_antes"] - g["marcador_visitante_antes"],
        g["marcador_visitante_antes"] - g["marcador_local_antes"],
    )
    # user-facing labels are Catalan; the column names stay as they are
    g["estado"] = np.select(
        [g["dif_antes"] < 0, g["dif_antes"] == 0],
        ["perdent", "empat"],
        default="guanyant",
    )

    # minutes elapsed since the opponent last scored; for the conceding team the
    # same value reads as "minutes since we scored".
    g["min_ultimo_gol_rival"] = np.nan
    for _, idx in g.groupby("cod_acta").groups.items():
        sub = g.loc[idx]
        ultimo_local = np.nan
        ultimo_visit = np.nan
        for i, row in sub.iterrows():
            previo = ultimo_visit if row["favor_local"] else ultimo_local
            g.at[i, "min_ultimo_gol_rival"] = previo
            if row["favor_local"]:
                ultimo_local = row["minuto"]
            else:
                ultimo_visit = row["minuto"]

    g["min_desde_gol_rival"] = g["minuto"] - g["min_ultimo_gol_rival"]
    g["es_respuesta"] = g["min_desde_gol_rival"] <= VENTANA_RESPUESTA
    g["tramo"] = g["minuto"].apply(tramo)
    g["equipo_favor"] = g["cod_equipo_favor"].map(nombres)
    g["equipo_contra"] = g["cod_equipo_contra"].map(nombres)
    g["favor_en_casa"] = g["cod_equipo_favor"] == g["cod_equipo_local"]
    g["tipo"] = np.select(
        [g["es_propia"], g["es_penal"]], ["en pròpia", "de penal"], default="de jugada"
    )
    return g


# --------------------------------------------------------------------------- #
# one row per team per match
# --------------------------------------------------------------------------- #
def _equipo_partido(partidos: pd.DataFrame, goles: pd.DataFrame, nombres: dict) -> pd.DataFrame:
    gpe = (
        goles.groupby(["cod_acta", "cod_equipo_favor"])
        .agg(
            gf_total=("id", "count"),
            gf_p1=("parte", lambda s: int((s == 1).sum())),
            gf_p2=("parte", lambda s: int((s == 2).sum())),
            gf_m20=("minuto", lambda s: int((s <= 20).sum())),
            gf_m75=("minuto", lambda s: int((s >= 75).sum())),
        )
        .reset_index()
        .rename(columns={"cod_equipo_favor": "cod_equipo"})
    )

    filas = []
    for es_local in (True, False):
        propio = "cod_equipo_local" if es_local else "cod_equipo_visitante"
        rival = "cod_equipo_visitante" if es_local else "cod_equipo_local"
        f = partidos[["cod_acta", "jornada", "fecha", propio, rival]].copy()
        f = f.rename(columns={propio: "cod_equipo", rival: "cod_equipo_rival"})
        f["es_local"] = es_local
        filas.append(f)
    ep = pd.concat(filas, ignore_index=True)

    ep = ep.merge(gpe, on=["cod_acta", "cod_equipo"], how="left")
    rival_cols = gpe.rename(
        columns={
            "cod_equipo": "cod_equipo_rival",
            "gf_total": "gc_total",
            "gf_p1": "gc_p1",
            "gf_p2": "gc_p2",
            "gf_m20": "gc_m20",
            "gf_m75": "gc_m75",
        }
    )
    ep = ep.merge(rival_cols, on=["cod_acta", "cod_equipo_rival"], how="left")
    num = [c for c in ep.columns if c.startswith(("gf_", "gc_"))]
    ep[num] = ep[num].fillna(0).astype(int)

    ep["signo"] = np.select(
        [ep["gf_total"] > ep["gc_total"], ep["gf_total"] == ep["gc_total"]],
        ["V", "E"],
        default="D",
    )
    ep["puntos"] = ep["signo"].map({"V": 3, "E": 1, "D": 0})
    ep["porteria_cero"] = ep["gc_total"] == 0
    ep["sin_marcar"] = ep["gf_total"] == 0
    ep["equipo"] = ep["cod_equipo"].map(nombres)
    ep["rival"] = ep["cod_equipo_rival"].map(nombres)
    return ep.sort_values(["cod_equipo", "jornada"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# cards / substitutions / minutes
# --------------------------------------------------------------------------- #
def _tarjetas(tarjetas: pd.DataFrame, partidos: pd.DataFrame, personas: pd.DataFrame,
              nombres: dict) -> pd.DataFrame:
    t = tarjetas.merge(partidos[["cod_acta", "jornada", "fecha"]], on="cod_acta", how="inner")
    t = t.merge(personas.rename(columns={"nombre": "persona"}), on="cod_persona", how="left")
    t["equipo"] = t["cod_equipo"].map(nombres)
    t["color"] = np.where(t["tipo_tarjeta"] == ROJA, "roja", "amarilla")
    t["tramo"] = t["minuto"].apply(tramo)
    return t


def _cambios(sustituciones: pd.DataFrame, partidos: pd.DataFrame, personas: pd.DataFrame,
             nombres: dict) -> pd.DataFrame:
    s = sustituciones.merge(partidos[["cod_acta", "jornada"]], on="cod_acta", how="inner")
    p = personas.rename(columns={"nombre": "persona"})
    s = s.merge(p.rename(columns={"cod_persona": "cod_persona_entra", "persona": "entra"}),
                on="cod_persona_entra", how="left")
    s = s.merge(p.rename(columns={"cod_persona": "cod_persona_sale", "persona": "sale"}),
                on="cod_persona_sale", how="left")
    s["equipo"] = s["cod_equipo"].map(nombres)
    return s


def _minutos(alineaciones: pd.DataFrame, sustituciones: pd.DataFrame, tarjetas: pd.DataFrame,
             partidos: pd.DataFrame, personas: pd.DataFrame, nombres: dict) -> pd.DataFrame:
    a = alineaciones.merge(partidos[["cod_acta", "jornada"]], on="cod_acta", how="inner")

    entra = sustituciones[["cod_acta", "cod_persona_entra", "minuto"]].rename(
        columns={"cod_persona_entra": "cod_persona", "minuto": "min_entra"}
    )
    sale = sustituciones[["cod_acta", "cod_persona_sale", "minuto"]].rename(
        columns={"cod_persona_sale": "cod_persona", "minuto": "min_sale"}
    )
    roja = tarjetas[tarjetas["tipo_tarjeta"] == ROJA][["cod_acta", "cod_persona", "minuto"]].rename(
        columns={"minuto": "min_roja"}
    )

    a = a.merge(entra, on=["cod_acta", "cod_persona"], how="left")
    a = a.merge(sale, on=["cod_acta", "cod_persona"], how="left")
    a = a.merge(roja, on=["cod_acta", "cod_persona"], how="left")

    jugo = a["titular"] | a["min_entra"].notna()
    inicio = np.where(a["titular"], 0, a["min_entra"].fillna(90))
    fin = np.minimum(a["min_sale"].fillna(90), a["min_roja"].fillna(90))
    a["minutos"] = np.where(jugo, np.maximum(fin - inicio, 0), 0).astype(int)
    a["jugo"] = jugo
    a = a.merge(personas.rename(columns={"nombre": "persona"}), on="cod_persona", how="left")
    a["equipo"] = a["cod_equipo"].map(nombres)
    return a


# --------------------------------------------------------------------------- #
# per-team summary
# --------------------------------------------------------------------------- #
def _resumen_equipo(ep: pd.DataFrame, goles: pd.DataFrame, tarjetas: pd.DataFrame,
                    cambios: pd.DataFrame, alineaciones: pd.DataFrame,
                    partidos: pd.DataFrame, equipos: pd.DataFrame) -> pd.DataFrame:
    base = (
        ep.groupby("cod_equipo")
        .agg(
            pj=("cod_acta", "count"),
            pj_casa=("es_local", "sum"),
            v=("signo", lambda s: int((s == "V").sum())),
            e=("signo", lambda s: int((s == "E").sum())),
            d=("signo", lambda s: int((s == "D").sum())),
            puntos=("puntos", "sum"),
            gf=("gf_total", "sum"),
            gc=("gc_total", "sum"),
            gf_p1=("gf_p1", "sum"),
            gf_p2=("gf_p2", "sum"),
            gc_p1=("gc_p1", "sum"),
            gc_p2=("gc_p2", "sum"),
            porterias_cero=("porteria_cero", "sum"),
            partidos_sin_marcar=("sin_marcar", "sum"),
        )
        .reset_index()
    )
    base["pj_fuera"] = base["pj"] - base["pj_casa"]

    casa = ep[ep["es_local"]].groupby("cod_equipo").agg(
        gf_casa=("gf_total", "sum"), gc_casa=("gc_total", "sum"),
        puntos_casa=("puntos", "sum"), v_casa=("signo", lambda s: int((s == "V").sum())),
    ).reset_index()
    fuera = ep[~ep["es_local"]].groupby("cod_equipo").agg(
        gf_fuera=("gf_total", "sum"), gc_fuera=("gc_total", "sum"),
        puntos_fuera=("puntos", "sum"), v_fuera=("signo", lambda s: int((s == "V").sum())),
    ).reset_index()

    gf_ctx = goles.groupby("cod_equipo_favor").agg(
        gf_perdiendo=("estado", lambda s: int((s == "perdent").sum())),
        gf_empate=("estado", lambda s: int((s == "empat").sum())),
        gf_ganando=("estado", lambda s: int((s == "guanyant").sum())),
        gf_respuesta=("es_respuesta", "sum"),
        gf_penal=("es_penal", "sum"),
        gf_m20=("minuto", lambda s: int((s <= 20).sum())),
        gf_m75=("minuto", lambda s: int((s >= 75).sum())),
    ).reset_index().rename(columns={"cod_equipo_favor": "cod_equipo"})

    gc_ctx = goles.groupby("cod_equipo_contra").agg(
        gc_tras_marcar=("es_respuesta", "sum"),
        gc_m20=("minuto", lambda s: int((s <= 20).sum())),
        gc_m75=("minuto", lambda s: int((s >= 75).sum())),
    ).reset_index().rename(columns={"cod_equipo_contra": "cod_equipo"})

    tj = tarjetas[tarjetas["es_jugador"]]
    tar = tj.groupby("cod_equipo").agg(
        amarillas=("color", lambda s: int((s == "amarilla").sum())),
        rojas=("color", lambda s: int((s == "roja").sum())),
        amarillas_p1=("parte", lambda s: int((s == 1).sum())),
    ).reset_index()
    tar_p2 = tj[tj["parte"] == 2].groupby("cod_equipo").size().rename("tarjetas_p2").reset_index()

    camb = cambios.groupby("cod_equipo").agg(
        cambios=("id", "count"), min_cambio_medio=("minuto", "mean"),
        primer_cambio_medio=("minuto", "min"),
    ).reset_index()

    plantilla = alineaciones.merge(partidos[["cod_acta"]], on="cod_acta", how="inner")
    plantilla = plantilla.groupby("cod_equipo")["cod_persona"].nunique().rename(
        "jugadores_usados"
    ).reset_index()

    out = base
    for extra in (casa, fuera, gf_ctx, gc_ctx, tar, tar_p2, camb, plantilla):
        out = out.merge(extra, on="cod_equipo", how="left")
    out = out.merge(equipos[["cod_equipo", "equipo"]], on="cod_equipo", how="left")

    enteros = [c for c in out.columns if c not in ("equipo", "min_cambio_medio")]
    out[enteros] = out[enteros].fillna(0).astype(int)

    out["gf_por_partido"] = (out["gf"] / out["pj"]).round(2)
    out["gc_por_partido"] = (out["gc"] / out["pj"]).round(2)
    out["puntos_por_partido"] = (out["puntos"] / out["pj"]).round(2)
    out["gf_casa_por_partido"] = (out["gf_casa"] / out["pj_casa"].replace(0, np.nan)).round(2)
    out["gf_fuera_por_partido"] = (out["gf_fuera"] / out["pj_fuera"].replace(0, np.nan)).round(2)
    out["gc_casa_por_partido"] = (out["gc_casa"] / out["pj_casa"].replace(0, np.nan)).round(2)
    out["gc_fuera_por_partido"] = (out["gc_fuera"] / out["pj_fuera"].replace(0, np.nan)).round(2)
    out["tarjetas_por_partido"] = ((out["amarillas"] + out["rojas"]) / out["pj"]).round(2)
    out["tarjetas_p2_por_partido"] = (out["tarjetas_p2"] / out["pj"]).round(2)
    out["pct_gf_p2"] = (100 * out["gf_p2"] / out["gf"].replace(0, np.nan)).round(1)
    out["pct_gc_p2"] = (100 * out["gc_p2"] / out["gc"].replace(0, np.nan)).round(1)
    out["min_cambio_medio"] = out["min_cambio_medio"].round(1)
    return out.sort_values("puntos", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# helpers used by the reports
# --------------------------------------------------------------------------- #
def goleadores(goles: pd.DataFrame, personas: pd.DataFrame, cod_equipo: int | None = None,
               incluir_propias: bool = False) -> pd.DataFrame:
    g = goles if incluir_propias else goles[~goles["es_propia"]]
    if cod_equipo is not None:
        g = g[g["cod_equipo_favor"] == cod_equipo]
    out = (
        g.groupby("cod_persona")
        .agg(
            goles=("id", "count"),
            penales=("es_penal", "sum"),
            p1=("parte", lambda s: int((s == 1).sum())),
            p2=("parte", lambda s: int((s == 2).sum())),
            primer_minuto=("minuto", "min"),
            ultimo_minuto=("minuto", "max"),
        )
        .reset_index()
        .merge(personas.rename(columns={"nombre": "jugador"}), on="cod_persona", how="left")
    )
    if cod_equipo is None:
        equipo = g.groupby("cod_persona")["equipo_favor"].first().reset_index()
        out = out.merge(equipo, on="cod_persona", how="left").rename(
            columns={"equipo_favor": "equipo"}
        )
    return out.sort_values(["goles", "p2"], ascending=False).reset_index(drop=True)


def distribucion_tramos(eventos: pd.DataFrame) -> pd.DataFrame:
    conteo = eventos["tramo"].value_counts().reindex(TRAMO_LABELS, fill_value=0)
    return pd.DataFrame({"tramo": TRAMO_LABELS, "n": conteo.values})


def evolucion(ep: pd.DataFrame, cod_equipo: int) -> pd.DataFrame:
    e = ep[ep["cod_equipo"] == cod_equipo].sort_values("jornada").copy()
    e["puntos_acum"] = e["puntos"].cumsum()
    e["gf_acum"] = e["gf_total"].cumsum()
    e["gc_acum"] = e["gc_total"].cumsum()
    e["donde"] = np.where(e["es_local"], "Casa", "Fuera")
    e["marcador"] = e["gf_total"].astype(str) + "-" + e["gc_total"].astype(str)
    return e
