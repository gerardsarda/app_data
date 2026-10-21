"""Insight catalog with explicit sample-size validation.

The dataset covers 5 jornadas (34 matches, 90 goals, 186 player cards). At that
volume some questions are answerable and others are not, so every insight
declares the event count it rests on and is graded before it reaches the app:

    OK           the metric has enough events to describe a tendency
    ORIENTATIVO  real but fragile; one match can reorder the ranking
    DESCARTADO   too few events to rank teams; shown as a raw fact only

The grade is computed from the data each time, not hardcoded, so the catalog
regrades itself automatically as new jornadas are loaded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

# league-wide event thresholds for a ranking to be meaningful
UMBRAL_OK = 60
UMBRAL_ORIENTATIVO = 25

# per-team event thresholds for a team-level statement
UMBRAL_EQUIPO_OK = 10
UMBRAL_EQUIPO_ORIENTATIVO = 4

# thresholds for statements whose unit is the match, not the event
UMBRAL_PARTIDOS_OK = 8
UMBRAL_PARTIDOS_ORIENTATIVO = 4


def grado(n: int, ok: int = UMBRAL_OK, orientativo: int = UMBRAL_ORIENTATIVO) -> str:
    if n >= ok:
        return "OK"
    if n >= orientativo:
        return "ORIENTATIVO"
    return "DESCARTADO"


@dataclass
class Ranking:
    """A league ranking built from one column of the per-team summary."""

    id: str
    titulo: str
    columna: str
    unidad: str
    poblacion: str  # which event count backs this ranking
    ascendente: bool = False
    columna_apoyo: Optional[str] = None  # raw total shown next to the rate
    nota: str = ""

    def tabla(self, resumen: pd.DataFrame, top: int = 3) -> pd.DataFrame:
        cols = ["equipo", self.columna, "pj"]
        if self.columna_apoyo:
            cols.insert(2, self.columna_apoyo)
        t = resumen[cols].dropna(subset=[self.columna])
        t = t.sort_values(self.columna, ascending=self.ascendente).head(top)
        return t.reset_index(drop=True)


RANKINGS: List[Ranking] = [
    Ranking("gf_casa", "Más goles como local", "gf_casa_por_partido", "goles/partido",
            "goles marcados por el equipo local", columna_apoyo="gf_casa",
            nota="Normalizado por partidos en casa: los equipos no han jugado los mismos."),
    Ranking("gf_fuera", "Más goles como visitante", "gf_fuera_por_partido", "goles/partido",
            "goles marcados por el equipo visitante", columna_apoyo="gf_fuera"),
    Ranking("gf_total", "Más goles por partido", "gf_por_partido", "goles/partido",
            "goles totales", columna_apoyo="gf"),
    Ranking("gc_total", "Menos goles encajados por partido", "gc_por_partido", "goles/partido",
            "goles totales", ascendente=True, columna_apoyo="gc"),
    Ranking("tarjetas_p2", "Más tarjetas en la segunda parte", "tarjetas_p2_por_partido",
            "tarjetas/partido", "tarjetas a jugadores en la segunda parte",
            columna_apoyo="tarjetas_p2",
            nota="Solo tarjetas a jugadores. Las del banquillo se cuentan aparte."),
    Ranking("tarjetas_total", "Más tarjetas por partido", "tarjetas_por_partido",
            "tarjetas/partido", "tarjetas a jugadores", columna_apoyo="amarillas"),
    Ranking("gf_p2_pct", "Mayor porcentaje de goles en la segunda parte", "pct_gf_p2",
            "% de sus goles", "goles totales", columna_apoyo="gf_p2"),
    Ranking("gf_final", "Más goles en los últimos 15 minutos", "gf_m75", "goles",
            "goles desde el minuto 75", columna_apoyo="gf_m75"),
    Ranking("gf_perdiendo", "Más goles marcados por detrás en el marcador", "gf_perdiendo",
            "goles", "goles marcados yendo por detrás", columna_apoyo="gf_perdiendo"),
    Ranking("gf_inicio", "Más goles en los primeros 20 minutos", "gf_m20", "goles",
            "goles antes del minuto 21", columna_apoyo="gf_m20"),
    Ranking("gf_respuesta", "Más goles de respuesta (≤10 min tras encajar)", "gf_respuesta",
            "goles", "goles llegados ≤10 min después de encajar", columna_apoyo="gf_respuesta"),
    Ranking("gc_tras_marcar", "Más goles encajados justo después de marcar", "gc_tras_marcar",
            "goles", "goles encajados ≤10 min después de marcar",
            columna_apoyo="gc_tras_marcar"),
    Ranking("cambios_pronto", "Cambios más tempranos", "min_cambio_medio", "minuto medio",
            "sustituciones", ascendente=True, columna_apoyo="cambios"),
    Ranking("plantilla", "Más jugadores distintos utilizados", "jugadores_usados", "jugadores",
            "comparecencias en acta", columna_apoyo="pj"),
    Ranking("porterias_cero", "Más porterías a cero", "porterias_cero", "partidos",
            "partidos-equipo observados", columna_apoyo="pj",
            nota="Se mide sobre partidos, no sobre goles: la base son los 68 "
                 "partidos-equipo disputados."),
    Ranking("penales", "Más goles de penal", "gf_penal", "goles", "goles de penal",
            columna_apoyo="gf_penal"),
]


def poblaciones(frames: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """League-wide event counts that back each ranking."""
    g = frames["goles"]
    t = frames["tarjetas"]
    tj = t[t["es_jugador"]]
    ep = frames["equipo_partido"]
    return {
        "goles totales": len(g),
        "goles marcados por el equipo local": int(g["favor_en_casa"].sum()),
        "goles marcados por el equipo visitante": int((~g["favor_en_casa"]).sum()),
        "goles desde el minuto 75": int((g["minuto"] >= 75).sum()),
        "goles antes del minuto 21": int((g["minuto"] <= 20).sum()),
        "goles marcados yendo por detrás": int((g["estado"] == "perdiendo").sum()),
        "goles llegados ≤10 min después de encajar": int(g["es_respuesta"].sum()),
        "goles encajados ≤10 min después de marcar": int(g["es_respuesta"].sum()),
        "goles de penal": int(g["es_penal"].sum()),
        "tarjetas a jugadores": len(tj),
        "tarjetas a jugadores en la segunda parte": int((tj["parte"] == 2).sum()),
        "sustituciones": len(frames["cambios"]),
        "comparecencias en acta": len(frames["minutos"]),
        "partidos-equipo observados": len(ep),
        "partidos con portería a cero": int(ep["porteria_cero"].sum()),
    }


def validar(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Grade every ranking in the catalog against the data actually loaded."""
    pob = poblaciones(frames)
    filas = []
    for r in RANKINGS:
        n = pob.get(r.poblacion, 0)
        filas.append(
            {
                "id": r.id,
                "insight": r.titulo,
                "metrica": r.columna,
                "poblacion": r.poblacion,
                "n": n,
                "veredicto": grado(n),
                "nota": r.nota,
            }
        )
    return pd.DataFrame(filas).sort_values(
        ["veredicto", "n"], ascending=[True, False]
    ).reset_index(drop=True)


def rankings_publicables(frames: Dict[str, pd.DataFrame]) -> List[Ranking]:
    v = validar(frames)
    validos = set(v[v["veredicto"] != "DESCARTADO"]["id"])
    return [r for r in RANKINGS if r.id in validos]


def rankings_descartados(frames: Dict[str, pd.DataFrame]) -> List[Ranking]:
    v = validar(frames)
    fuera = set(v[v["veredicto"] == "DESCARTADO"]["id"])
    return [r for r in RANKINGS if r.id in fuera]


# --------------------------------------------------------------------------- #
# team report
# --------------------------------------------------------------------------- #
@dataclass
class Hallazgo:
    titulo: str
    texto: str
    n: int
    veredicto: str
    detalle: Optional[pd.DataFrame] = field(default=None)


def _pct(parte: int, total: int) -> str:
    if not total:
        return "sin datos"
    return "%d de %d (%.0f%%)" % (parte, total, 100 * parte / total)


def informe_equipo(frames: Dict[str, pd.DataFrame], cod_equipo: int) -> List[Hallazgo]:
    """Narrative findings for one team, each graded by its own event count."""
    g = frames["goles"]
    gf = g[g["cod_equipo_favor"] == cod_equipo]
    gc = g[g["cod_equipo_contra"] == cod_equipo]
    ep = frames["equipo_partido"]
    mi = ep[ep["cod_equipo"] == cod_equipo]
    tj = frames["tarjetas"]
    mis_t = tj[(tj["cod_equipo"] == cod_equipo) & (tj["es_jugador"])]
    cambios = frames["cambios"]
    mis_c = cambios[cambios["cod_equipo"] == cod_equipo]

    def gr(n: int) -> str:
        return grado(n, UMBRAL_EQUIPO_OK, UMBRAL_EQUIPO_ORIENTATIVO)

    out: List[Hallazgo] = []

    n = len(gf)
    out.append(
        Hallazgo(
            "Reparto por partes",
            "Marca %s en la segunda parte y %s en la primera."
            % (_pct(int((gf["parte"] == 2).sum()), n), _pct(int((gf["parte"] == 1).sum()), n)),
            n,
            gr(n),
        )
    )

    # the claim is only as solid as its weakest base, so grade on the smaller side
    base_doble = min(n, len(gc))
    out.append(
        Hallazgo(
            "Arranque",
            "En los primeros 20 minutos marca %s y encaja %s."
            % (
                _pct(int((gf["minuto"] <= 20).sum()), n),
                _pct(int((gc["minuto"] <= 20).sum()), len(gc)),
            ),
            base_doble,
            gr(base_doble),
        )
    )

    out.append(
        Hallazgo(
            "Tramo final",
            "Desde el minuto 75 marca %s y encaja %s."
            % (
                _pct(int((gf["minuto"] >= 75).sum()), n),
                _pct(int((gc["minuto"] >= 75).sum()), len(gc)),
            ),
            base_doble,
            gr(base_doble),
        )
    )

    out.append(
        Hallazgo(
            "Estado del marcador al marcar",
            "Marca %s yendo por detrás, %s con empate y %s por delante."
            % (
                _pct(int((gf["estado"] == "perdiendo").sum()), n),
                _pct(int((gf["estado"] == "empate").sum()), n),
                _pct(int((gf["estado"] == "ganando").sum()), n),
            ),
            n,
            gr(n),
        )
    )

    resp = int(gf["es_respuesta"].sum())
    castigo = int(gc["es_respuesta"].sum())
    out.append(
        Hallazgo(
            "Reacción inmediata",
            "Responde en los 10 minutos siguientes a encajar %d veces; "
            "encaja en los 10 minutos siguientes a marcar %d veces." % (resp, castigo),
            resp + castigo,
            gr(resp + castigo),
        )
    )

    out.append(
        Hallazgo(
            "Casa y fuera",
            "En casa %.2f goles por partido y fuera %.2f, sobre %d y %d partidos."
            % (
                mi[mi["es_local"]]["gf_total"].mean() if (mi["es_local"]).any() else 0,
                mi[~mi["es_local"]]["gf_total"].mean() if (~mi["es_local"]).any() else 0,
                int(mi["es_local"].sum()),
                int((~mi["es_local"]).sum()),
            ),
            len(mi),
            grado(len(mi), UMBRAL_PARTIDOS_OK, UMBRAL_PARTIDOS_ORIENTATIVO),
        )
    )

    nt = len(mis_t)
    out.append(
        Hallazgo(
            "Disciplina",
            "%d tarjetas a jugadores, %s en la segunda parte. %.2f por partido."
            % (nt, _pct(int((mis_t["parte"] == 2).sum()), nt), nt / max(len(mi), 1)),
            nt,
            gr(nt),
        )
    )

    out.append(
        Hallazgo(
            "Banquillo",
            "%d sustituciones, minuto medio %.1f." % (len(mis_c), mis_c["minuto"].mean())
            if len(mis_c)
            else "Sin sustituciones registradas.",
            len(mis_c),
            gr(len(mis_c)),
        )
    )

    return out


def dependencia_goleadora(frames: Dict[str, pd.DataFrame], personas: pd.DataFrame,
                          cod_equipo: int) -> Hallazgo:
    """How concentrated a team's goals are in its top scorer."""
    from . import metrics  # local import keeps the module import-light

    tabla = metrics.goleadores(frames["goles"], personas, cod_equipo)
    total = int(tabla["goles"].sum())
    if total == 0:
        return Hallazgo("Dependencia goleadora", "El equipo no ha marcado todavía.", 0,
                        "DESCARTADO", tabla)
    top = tabla.iloc[0]
    texto = "%s concentra %s de los goles de jugada y penal del equipo." % (
        top["jugador"],
        _pct(int(top["goles"]), total),
    )
    return Hallazgo("Dependencia goleadora", texto, total,
                    grado(total, UMBRAL_EQUIPO_OK, UMBRAL_EQUIPO_ORIENTATIVO), tabla)
