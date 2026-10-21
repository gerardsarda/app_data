"""Deeper per-team statistics derived from the match events.

Everything here is reconstructed from what the FCF acta publishes - goals with
their minute, lineups, substitutions, cards and the pitch coordinates. No shot,
possession or positional data exists in the source, so nothing here invents it.

The expensive part of each function is a walk over at most a few hundred rows,
so they are called straight from the UI without caching.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

DURACION = 90  # the acta has no stoppage time, so a match is 90 minutes here


# --------------------------------------------------------------------------- #
# scoreline timeline
# --------------------------------------------------------------------------- #
def _estado(dif: int) -> str:
    if dif > 0:
        return "guanyant"
    if dif < 0:
        return "perdent"
    return "empatant"


def temps_en_marcador(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """Minutes the team spent ahead, level and behind, across every match.

    Walks each match's goal timeline, so it answers "how long does this team
    actually lead?" rather than just how many matches it won.
    """
    g = frames["goles"]
    acumulado = {"guanyant": 0, "empatant": 0, "perdent": 0}
    partidos = frames["equipo_partido"]
    mis = partidos[partidos["cod_equipo"] == cod]

    for acta in mis["cod_acta"]:
        eventos: List[tuple] = []
        en_acta = g[g["cod_acta"] == acta]
        for _, gol in en_acta.iterrows():
            signo = 1 if gol["cod_equipo_favor"] == cod else -1
            eventos.append((min(int(gol["minuto"]), DURACION), signo))
        eventos.sort()
        dif = 0
        anterior = 0
        for minuto, signo in eventos:
            acumulado[_estado(dif)] += max(minuto - anterior, 0)
            anterior = minuto
            dif += signo
        acumulado[_estado(dif)] += max(DURACION - anterior, 0)

    total = sum(acumulado.values()) or 1
    salida = dict(acumulado)
    salida["total"] = total
    for clave in ("guanyant", "empatant", "perdent"):
        salida["pct_" + clave] = 100.0 * acumulado[clave] / total
    return salida


# --------------------------------------------------------------------------- #
# first goal, half time, comebacks
# --------------------------------------------------------------------------- #
def primer_gol(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """What happens when the team opens the scoring, and when it concedes first."""
    g = frames["goles"]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod]

    marca, encaixa, sense = [], [], []
    for _, p in mis.iterrows():
        en_acta = g[g["cod_acta"] == p["cod_acta"]].sort_values(["minuto", "id"])
        if en_acta.empty:
            sense.append(p)
            continue
        primero = en_acta.iloc[0]
        (marca if primero["cod_equipo_favor"] == cod else encaixa).append(p)

    def puntos(lista) -> tuple:
        if not lista:
            return 0, 0, 0.0
        df = pd.DataFrame(lista)
        return len(df), int(df["puntos"].sum()), float(df["puntos"].mean())

    n_m, pts_m, mitja_m = puntos(marca)
    n_e, pts_e, mitja_e = puntos(encaixa)
    minuts_marca = [
        int(g[g["cod_acta"] == p["cod_acta"]].sort_values(["minuto", "id"]).iloc[0]["minuto"])
        for p in marca
    ]
    return {
        "marca_primer": n_m,
        "encaixa_primer": n_e,
        "sense_gols": len(sense),
        "punts_marcant_primer": pts_m,
        "punts_encaixant_primer": pts_e,
        "mitjana_marcant_primer": mitja_m,
        "mitjana_encaixant_primer": mitja_e,
        "minut_mitja_primer_gol": float(np.mean(minuts_marca)) if minuts_marca else float("nan"),
    }


def descans_final(frames: Dict[str, pd.DataFrame], cod: int) -> pd.DataFrame:
    """Half-time standing versus the final one, match by match."""
    g = frames["goles"]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod].sort_values("jornada")

    filas = []
    for _, p in mis.iterrows():
        en_acta = g[(g["cod_acta"] == p["cod_acta"]) & (g["parte"] == 1)]
        gf1 = int((en_acta["cod_equipo_favor"] == cod).sum())
        gc1 = int((en_acta["cod_equipo_contra"] == cod).sum())
        signo_ht = "V" if gf1 > gc1 else ("E" if gf1 == gc1 else "D")
        punts_ht = {"V": 3, "E": 1, "D": 0}[signo_ht]
        filas.append(
            {
                "jornada": int(p["jornada"]),
                "rival": p["rival"],
                "cod_equipo_rival": int(p["cod_equipo_rival"]),
                "es_local": bool(p["es_local"]),
                "descans": "%d-%d" % (gf1, gc1),
                "final": "%d-%d" % (int(p["gf_total"]), int(p["gc_total"])),
                "signe_descans": signo_ht,
                "signe_final": p["signo"],
                "punts": int(p["puntos"]),
                "punts_virtuals_descans": punts_ht,
                "diferencia": int(p["puntos"]) - punts_ht,
            }
        )
    return pd.DataFrame(filas)


def remuntades(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, int]:
    """Matches turned around after going behind, and leads thrown away."""
    g = frames["goles"]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod]

    va_perdre = guanya_despres = empata_despres = 0
    va_guanyar = deixa_escapar = 0
    for _, p in mis.iterrows():
        en_acta = g[g["cod_acta"] == p["cod_acta"]].sort_values(["minuto", "id"])
        dif = 0
        min_dif = 0
        max_dif = 0
        for _, gol in en_acta.iterrows():
            dif += 1 if gol["cod_equipo_favor"] == cod else -1
            min_dif = min(min_dif, dif)
            max_dif = max(max_dif, dif)
        if min_dif < 0:
            va_perdre += 1
            if p["signo"] == "V":
                guanya_despres += 1
            elif p["signo"] == "E":
                empata_despres += 1
        if max_dif > 0:
            va_guanyar += 1
            if p["signo"] != "V":
                deixa_escapar += 1
    return {
        "va_anar_per_darrere": va_perdre,
        "remuntades": guanya_despres,
        "empats_rescatats": empata_despres,
        "va_anar_per_davant": va_guanyar,
        "avantatges_perduts": deixa_escapar,
    }


# --------------------------------------------------------------------------- #
# squad
# --------------------------------------------------------------------------- #
def gols_suplents(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, int]:
    """Goals scored by players who started versus players who came off the bench."""
    g = frames["goles"]
    subs = frames["sustituciones"]
    propios = g[(g["cod_equipo_favor"] == cod) & (~g["es_propia"])]

    entrades = subs[subs["cod_equipo"] == cod][
        ["cod_acta", "cod_persona_entra", "minuto"]
    ].rename(columns={"cod_persona_entra": "cod_persona", "minuto": "min_entra"})
    unidos = propios.merge(entrades, on=["cod_acta", "cod_persona"], how="left")
    suplent = (unidos["min_entra"].notna()) & (unidos["minuto"] >= unidos["min_entra"])
    return {
        "titulars": int((~suplent).sum()),
        "suplents": int(suplent.sum()),
        "total": len(unidos),
    }


def rotacio(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """How much the starting eleven changes from one matchday to the next."""
    a = frames["minutos"]
    mios = a[a["cod_equipo"] == cod]
    onces = (
        mios[mios["titular"]]
        .groupby("jornada")["cod_persona"]
        .apply(set)
        .sort_index()
    )
    canvis = []
    jornadas = list(onces.index)
    for anterior, actual in zip(jornadas, jornadas[1:]):
        canvis.append(len(onces[actual] - onces[anterior]))

    titulars = mios[mios["titular"]].groupby("cod_persona").size()
    jugats = mios["cod_acta"].nunique()
    return {
        "canvis_mitjans": float(np.mean(canvis)) if canvis else float("nan"),
        "canvis_maxim": int(max(canvis)) if canvis else 0,
        "canvis_minim": int(min(canvis)) if canvis else 0,
        "sempre_titulars": int((titulars == jugats).sum()),
        "jugadors_utilitzats": int(mios["cod_persona"].nunique()),
    }


def targetes_per_90(frames: Dict[str, pd.DataFrame], cod: int,
                    minims: int = 90) -> pd.DataFrame:
    """Cards per 90 minutes, which ranks sparingly used players fairly."""
    mn = frames["minutos"]
    tj = frames["tarjetas"]
    minuts = (
        mn[(mn["cod_equipo"] == cod) & (mn["jugo"])]
        .groupby(["cod_persona", "persona"])["minutos"]
        .sum()
        .reset_index()
    )
    targetes = (
        tj[(tj["cod_equipo"] == cod) & (tj["es_jugador"])]
        .groupby("cod_persona")
        .size()
        .rename("targetes")
        .reset_index()
    )
    out = minuts.merge(targetes, on="cod_persona", how="left")
    out["targetes"] = out["targetes"].fillna(0).astype(int)
    out = out[out["minutos"] >= minims]
    out["per_90"] = (90.0 * out["targetes"] / out["minutos"]).round(2)
    return out.sort_values(["per_90", "targetes"], ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# defence
# --------------------------------------------------------------------------- #
def ratxa_sense_encaixar(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, int]:
    """Longest run of minutes without conceding, measured across matchdays."""
    g = frames["goles"]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod].sort_values("jornada")

    millor = actual = 0
    for _, p in mis.iterrows():
        encaixats = sorted(
            int(m) for m in g[(g["cod_acta"] == p["cod_acta"])
                              & (g["cod_equipo_contra"] == cod)]["minuto"]
        )
        anterior = 0
        for minuto in encaixats:
            actual += min(minuto, DURACION) - anterior
            millor = max(millor, actual)
            actual = 0
            anterior = min(minuto, DURACION)
        actual += DURACION - anterior
        millor = max(millor, actual)
    return {"millor_ratxa": millor, "ratxa_actual": actual}


def minuts_primer_gol(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """Average minute of the team's first goal scored and first conceded."""
    g = frames["goles"]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod]

    marcats, encaixats = [], []
    for acta in mis["cod_acta"]:
        propios = g[(g["cod_acta"] == acta) & (g["cod_equipo_favor"] == cod)]
        contra = g[(g["cod_acta"] == acta) & (g["cod_equipo_contra"] == cod)]
        if len(propios):
            marcats.append(int(propios["minuto"].min()))
        if len(contra):
            encaixats.append(int(contra["minuto"].min()))
    return {
        "primer_marcat": float(np.mean(marcats)) if marcats else float("nan"),
        "primer_encaixat": float(np.mean(encaixats)) if encaixats else float("nan"),
    }


def perfil_partits(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """Match-shape stats: both teams scoring, goal volume, most repeated result."""
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod]
    if mis.empty:
        return {}
    totals = mis["gf_total"] + mis["gc_total"]
    resultats = (mis["gf_total"].astype(str) + "-" + mis["gc_total"].astype(str))
    return {
        "ambdos_marquen": int(((mis["gf_total"] > 0) & (mis["gc_total"] > 0)).sum()),
        "mes_de_2_5": int((totals > 2.5).sum()),
        "menys_de_2_5": int((totals <= 2.5).sum()),
        "gols_per_partit": float(totals.mean()),
        "resultat_mes_repetit": resultats.mode().iloc[0] if len(resultats) else "-",
        "partits": len(mis),
    }


def taula_lliga(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The advanced per-team numbers for every team, ready to rank."""
    filas = []
    for _, e in frames["resumen"].iterrows():
        cod = int(e["cod_equipo"])
        t = temps_en_marcador(frames, cod)
        p = primer_gol(frames, cod)
        r = remuntades(frames, cod)
        s = gols_suplents(frames, cod)
        rot = rotacio(frames, cod)
        ratxa = ratxa_sense_encaixar(frames, cod)
        perfil = perfil_partits(frames, cod)
        canvis = perfil_canvis(frames, cod)
        filas.append(
            {
                "cod_equipo": cod,
                "equipo": e["equipo"],
                "pj": int(e["pj"]),
                "pct_guanyant": round(t["pct_guanyant"], 1),
                "pct_perdent": round(t["pct_perdent"], 1),
                "minuts_guanyant": t["guanyant"],
                "marca_primer": p["marca_primer"],
                "punts_marcant_primer": p["punts_marcant_primer"],
                "remuntades": r["remuntades"] + r["empats_rescatats"],
                "avantatges_perduts": r["avantatges_perduts"],
                "gols_suplents": s["suplents"],
                "canvis_mitjans": round(rot["canvis_mitjans"], 1)
                if rot["canvis_mitjans"] == rot["canvis_mitjans"] else 0.0,
                "sempre_titulars": rot["sempre_titulars"],
                "millor_ratxa": ratxa["millor_ratxa"],
                "ambdos_marquen": perfil.get("ambdos_marquen", 0),
                "gols_per_partit": round(perfil.get("gols_per_partit", 0.0), 2),
                "primer_canvi": round(canvis.get("primer_canvi", 0.0), 1),
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# substitutions
# --------------------------------------------------------------------------- #
def perfil_canvis(frames: Dict[str, pd.DataFrame], cod: int) -> Dict[str, float]:
    """When the bench is used: first change, last change, how many per match."""
    subs = frames["sustituciones"]
    mis = subs[subs["cod_equipo"] == cod]
    if mis.empty:
        return {}
    per_partit = mis.groupby("cod_acta")["minuto"]
    return {
        "canvis": len(mis),
        "canvis_per_partit": float(len(mis) / mis["cod_acta"].nunique()),
        "primer_canvi": float(per_partit.min().mean()),
        "ultim_canvi": float(per_partit.max().mean()),
        "minut_mitja": float(mis["minuto"].mean()),
        "abans_del_60": int((mis["minuto"] < 60).sum()),
    }
