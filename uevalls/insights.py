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
        # columna_apoyo is sometimes the same column as the metric, so de-duplicate
        # before selecting: a repeated label makes sort_values ambiguous.
        cols = ["cod_equipo", "equipo", self.columna, "pj"]
        if self.columna_apoyo and self.columna_apoyo not in cols:
            cols.insert(3, self.columna_apoyo)
        t = resumen[cols].dropna(subset=[self.columna])
        t = t.sort_values(self.columna, ascending=self.ascendente).head(top)
        return t.reset_index(drop=True)


RANKINGS: List[Ranking] = [
    Ranking("gf_casa", "Més gols com a local", "gf_casa_por_partido", "gols/partit",
            "gols marcats per l'equip local", columna_apoyo="gf_casa",
            nota="Normalitzat per partits a casa: els equips no han jugat els mateixos."),
    Ranking("gf_fuera", "Més gols com a visitant", "gf_fuera_por_partido", "gols/partit",
            "gols marcats per l'equip visitant", columna_apoyo="gf_fuera"),
    Ranking("gf_total", "Més gols per partit", "gf_por_partido", "gols/partit",
            "gols totals", columna_apoyo="gf"),
    Ranking("gc_total", "Menys gols encaixats per partit", "gc_por_partido", "gols/partit",
            "gols totals", ascendente=True, columna_apoyo="gc"),
    Ranking("tarjetas_p2", "Més targetes a la segona part", "tarjetas_p2_por_partido",
            "targetes/partit", "targetes a jugadors a la segona part",
            columna_apoyo="tarjetas_p2",
            nota="Nomes targetes a jugadors. Les de la banqueta es compten a part."),
    Ranking("tarjetas_total", "Més targetes per partit", "tarjetas_por_partido",
            "targetes/partit", "targetes a jugadors", columna_apoyo="amarillas"),
    Ranking("gf_p2_pct", "Més percentatge de gols a la segona part", "pct_gf_p2",
            "% dels seus gols", "gols totals", columna_apoyo="gf_p2"),
    Ranking("gf_final", "Més gols als últims 15 minuts", "gf_m75", "gols",
            "gols des del minut 75", columna_apoyo="gf_m75"),
    Ranking("gf_perdiendo", "Més gols marcats anant per darrere", "gf_perdiendo",
            "gols", "gols marcats anant per darrere", columna_apoyo="gf_perdiendo"),
    Ranking("gf_inicio", "Més gols als primers 20 minuts", "gf_m20", "gols",
            "gols abans del minut 21", columna_apoyo="gf_m20"),
    Ranking("gf_respuesta", "Més gols de resposta (≤10 min després d'encaixar)", "gf_respuesta",
            "gols", "gols arribats ≤10 min després d'encaixar", columna_apoyo="gf_respuesta"),
    Ranking("gc_tras_marcar", "Més gols encaixats just després de marcar", "gc_tras_marcar",
            "gols", "gols encaixats ≤10 min després de marcar",
            columna_apoyo="gc_tras_marcar"),
    Ranking("cambios_pronto", "Canvis més primerencs", "min_cambio_medio", "minut mitjà",
            "substitucions", ascendente=True, columna_apoyo="cambios"),
    Ranking("plantilla", "Més jugadors diferents utilitzats", "jugadores_usados", "jugadors",
            "compareixences a l'acta", columna_apoyo="pj"),
    Ranking("porterias_cero", "Més porteries a zero", "porterias_cero", "partits",
            "partits-equip observats", columna_apoyo="pj",
            nota="Es mesura sobre partits, no sobre gols: la base son els partits-equip "
                 "disputats."),
    Ranking("penales", "Més gols de penal", "gf_penal", "gols", "gols de penal",
            columna_apoyo="gf_penal"),
]


def poblaciones(frames: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """League-wide event counts that back each ranking."""
    g = frames["goles"]
    t = frames["tarjetas"]
    tj = t[t["es_jugador"]]
    ep = frames["equipo_partido"]
    return {
        "gols totals": len(g),
        "gols marcats per l'equip local": int(g["favor_en_casa"].sum()),
        "gols marcats per l'equip visitant": int((~g["favor_en_casa"]).sum()),
        "gols des del minut 75": int((g["minuto"] >= 75).sum()),
        "gols abans del minut 21": int((g["minuto"] <= 20).sum()),
        "gols marcats anant per darrere": int((g["estado"] == "perdent").sum()),
        "gols arribats ≤10 min després d'encaixar": int(g["es_respuesta"].sum()),
        "gols encaixats ≤10 min després de marcar": int(g["es_respuesta"].sum()),
        "gols de penal": int(g["es_penal"].sum()),
        "targetes a jugadors": len(tj),
        "targetes a jugadors a la segona part": int((tj["parte"] == 2).sum()),
        "substitucions": len(frames["cambios"]),
        "compareixences a l'acta": len(frames["minutos"]),
        "partits-equip observats": len(ep),
        "partits amb porteria a zero": int(ep["porteria_cero"].sum()),
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
        return "sense dades"
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
            "Repartiment per parts",
            "Marca %s a la segona part i %s a la primera."
            % (_pct(int((gf["parte"] == 2).sum()), n), _pct(int((gf["parte"] == 1).sum()), n)),
            n,
            gr(n),
        )
    )

    # the claim is only as solid as its weakest base, so grade on the smaller side
    base_doble = min(n, len(gc))
    out.append(
        Hallazgo(
            "Arrencada",
            "Als primers 20 minuts marca %s i encaixa %s."
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
            "Tram final",
            "Des del minut 75 marca %s i encaixa %s."
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
            "Estat del marcador en marcar",
            "Marca %s anant per darrere, %s amb empat i %s per davant."
            % (
                _pct(int((gf["estado"] == "perdent").sum()), n),
                _pct(int((gf["estado"] == "empat").sum()), n),
                _pct(int((gf["estado"] == "guanyant").sum()), n),
            ),
            n,
            gr(n),
        )
    )

    resp = int(gf["es_respuesta"].sum())
    castigo = int(gc["es_respuesta"].sum())
    out.append(
        Hallazgo(
            "Reacció immediata",
            "Respon en els 10 minuts seguents a encaixar %d vegades; "
            "encaixa en els 10 minuts seguents a marcar %d vegades." % (resp, castigo),
            resp + castigo,
            gr(resp + castigo),
        )
    )

    out.append(
        Hallazgo(
            "Casa i fora",
            "A casa %.2f gols per partit i fora %.2f, sobre %d i %d partits."
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
            "%d targetes a jugadors, %s a la segona part. %.2f per partit."
            % (nt, _pct(int((mis_t["parte"] == 2).sum()), nt), nt / max(len(mi), 1)),
            nt,
            gr(nt),
        )
    )

    out.append(
        Hallazgo(
            "Banqueta",
            "%d substitucions, minut mitja %.1f." % (len(mis_c), mis_c["minuto"].mean())
            if len(mis_c)
            else "Sense substitucions registrades.",
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
    total = int(tabla["gols"].sum())
    if total == 0:
        return Hallazgo("Dependència golejadora", "L'equip encara no ha marcat.", 0,
                        "DESCARTADO", tabla)
    top = tabla.iloc[0]
    texto = "%s concentra %s dels gols de jugada i penal de l'equip." % (
        top["jugador"],
        _pct(int(top["gols"]), total),
    )
    return Hallazgo("Dependència golejadora", texto, total,
                    grado(total, UMBRAL_EQUIPO_OK, UMBRAL_EQUIPO_ORIENTATIVO), tabla)
