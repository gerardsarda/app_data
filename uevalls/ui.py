"""Visual layer: palette, CSS and the HTML pieces the app is built from.

Colour decisions follow the data-viz method:

  * Rankings are nominal categories, so they use **emphasis**, not a value ramp:
    the team in focus takes the brand red, every other bar stays muted grey.
    One bar length already encodes the magnitude; hue carries identity instead.
  * Charts with two series (a favor / en contra) use validated categorical
    slots - blue and orange - which clear the CVD and contrast gates on this
    dark surface.
  * Reliability uses the reserved status palette and always ships with a label,
    never colour alone.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"

# brand
ROJO = "#E03A24"
ROJO_SUAVE = "#F2624E"

# surfaces and ink
FONDO = "#101317"
SUPERFICIE = "#191E25"
SUPERFICIE_2 = "#222932"
BORDE = "rgba(255,255,255,0.10)"
TINTA = "#F2F3F5"
TINTA_2 = "#AEB6C2"
TINTA_MUDA = "#7E8792"
REJILLA = "#2C3038"

# validated categorical slots for the dark surface
SERIE_1 = "#3987e5"   # a favor
SERIE_2 = "#d95926"   # en contra
SERIE_3 = "#199e70"
SERIE_4 = "#c98500"
SERIE_5 = "#9085e9"

# de-emphasis grey for the highlight pattern
MUDO = "#818A95"

# reserved status palette
ESTADO = {"OK": "#0ca30c", "ORIENTATIVO": "#fab219", "DESCARTADO": "#d03b3b"}
ESTADO_ETIQUETA = {
    "OK": "dato sólido",
    "ORIENTATIVO": "pocos datos",
    "DESCARTADO": "muy pocos datos",
}

SIGNO_COLOR = {"V": "#0ca30c", "E": "#7E8792", "D": "#d03b3b"}


@lru_cache(maxsize=64)
def escudo_uri(slug: str | None) -> str:
    """Return a crest as a data URI so it can live inside custom HTML."""
    if not slug:
        return ""
    ruta = ASSETS / "escudos" / (slug + ".png")
    if not ruta.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(ruta.read_bytes()).decode("ascii")


CSS = """
<style>
:root {
  --rojo: %(rojo)s;
  --superficie: %(superficie)s;
  --superficie2: %(superficie2)s;
  --borde: %(borde)s;
  --tinta: %(tinta)s;
  --tinta2: %(tinta2)s;
  --muda: %(muda)s;
}

html, body, [class*="st-"] { font-size: 16px; }

h1 { font-size: 2.4rem !important; font-weight: 800 !important; letter-spacing: -.02em; }
h2 { font-size: 1.6rem !important; font-weight: 800 !important; letter-spacing: -.01em; }
h3 { font-size: 1.15rem !important; font-weight: 700 !important; }

section.main .block-container { padding-top: 1.2rem; max-width: 1500px; }

/* tabs: bigger, bolder, with a red underline on the active one */
button[data-baseweb="tab"] { font-size: 1.05rem !important; font-weight: 700 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--rojo) !important; }
div[data-baseweb="tab-highlight"] { background-color: var(--rojo) !important; height: 3px; }

/* metrics: much larger figures */
[data-testid="stMetricValue"] { font-size: 2.1rem !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"] p {
  font-size: .82rem !important; font-weight: 700 !important;
  text-transform: uppercase; letter-spacing: .06em; color: var(--muda) !important;
}

/* generic card */
.uev-card {
  background: var(--superficie); border: 1px solid var(--borde);
  border-radius: 14px; padding: 16px 18px; margin-bottom: 14px;
}
.uev-card h4 {
  margin: 0 0 2px 0; font-size: 1.02rem; font-weight: 800; color: var(--tinta);
  letter-spacing: -.01em;
}
.uev-card .sub { font-size: .8rem; color: var(--muda); font-weight: 600; }

/* ranking rows */
.uev-fila { display: flex; align-items: center; gap: 10px; margin: 9px 0; }
.uev-pos {
  width: 20px; text-align: right; font-size: .85rem; font-weight: 800; color: var(--muda);
  font-variant-numeric: tabular-nums;
}
.uev-escudo { width: 26px; height: 26px; object-fit: contain; flex: 0 0 26px; }
.uev-nombre {
  width: 128px; font-size: .88rem; font-weight: 700; color: var(--tinta);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.uev-pista { flex: 1; background: rgba(255,255,255,.05); border-radius: 5px; height: 16px; }
.uev-barra { height: 16px; border-radius: 5px; }
.uev-valor {
  width: 58px; text-align: right; font-size: .95rem; font-weight: 800; color: var(--tinta);
  font-variant-numeric: tabular-nums;
}
.uev-apoyo { width: 40px; text-align: right; font-size: .78rem; color: var(--muda); font-weight: 600; }

/* reliability chip */
.uev-chip {
  display: inline-block; border-radius: 999px; padding: 2px 9px;
  font-size: .68rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase;
}

/* standings row */
.uev-clas {
  display: flex; align-items: center; gap: 12px; padding: 9px 12px; border-radius: 10px;
  background: var(--superficie); border: 1px solid var(--borde); margin-bottom: 6px;
}
.uev-clas.destacado { border-color: var(--rojo); background: rgba(224,58,36,.09); }
.uev-pts { font-size: 1.35rem; font-weight: 800; width: 46px; text-align: right;
           font-variant-numeric: tabular-nums; }
.uev-mini { font-size: .8rem; color: var(--tinta2); font-weight: 600;
            font-variant-numeric: tabular-nums; }
.uev-punto { width: 10px; height: 10px; border-radius: 50%%; display: inline-block; margin-right: 3px; }

/* headline numbers inside cards */
.uev-dato { display: flex; align-items: baseline; gap: 8px; margin: 6px 0; }
.uev-dato .n { font-size: 1.9rem; font-weight: 800; color: var(--tinta); line-height: 1; }
.uev-dato .t { font-size: .85rem; color: var(--tinta2); font-weight: 600; }

/* team picker buttons */
div[data-testid="column"] .stButton > button {
  width: 100%%; font-size: .78rem; font-weight: 700; padding: 3px 4px;
  border-radius: 8px; border: 1px solid var(--borde);
}
div[data-testid="column"] .stButton > button:hover { border-color: var(--rojo); color: var(--rojo); }
</style>
""" % {
    "rojo": ROJO,
    "superficie": SUPERFICIE,
    "superficie2": SUPERFICIE_2,
    "borde": BORDE,
    "tinta": TINTA,
    "tinta2": TINTA_2,
    "muda": TINTA_MUDA,
}


def chip(veredicto: str) -> str:
    color = ESTADO.get(veredicto, TINTA_MUDA)
    return (
        "<span class='uev-chip' style='background:%s22;color:%s;border:1px solid %s55'>%s</span>"
        % (color, color, color, ESTADO_ETIQUETA.get(veredicto, veredicto))
    )


def fila_ranking(pos: int, slug: str | None, nombre: str, valor: str, ancho: float,
                 color: str, apoyo: str = "", ancho_nombre: int = 128) -> str:
    uri = escudo_uri(slug)
    img = ("<img class='uev-escudo' src='%s'>" % uri) if uri else ""
    return (
        "<div class='uev-fila'>"
        "<div class='uev-pos'>%d</div>%s"
        "<div class='uev-nombre' style='width:%dpx' title='%s'>%s</div>"
        "<div class='uev-pista'><div class='uev-barra' style='width:%.1f%%;background:%s'></div></div>"
        "<div class='uev-valor'>%s</div>"
        "<div class='uev-apoyo'>%s</div>"
        "</div>" % (pos, img, ancho_nombre, nombre, nombre, max(ancho, 2.0), color, valor, apoyo)
    )


def tarjeta(titulo: str, cuerpo: str, subtitulo: str = "", extra: str = "") -> str:
    sub = "<div class='sub'>%s</div>" % subtitulo if subtitulo else ""
    return "<div class='uev-card'><h4>%s %s</h4>%s%s</div>" % (titulo, extra, sub, cuerpo)


def dato(numero: str, texto: str) -> str:
    return "<div class='uev-dato'><span class='n'>%s</span><span class='t'>%s</span></div>" % (
        numero,
        texto,
    )


def puntos_forma(signos: list[str]) -> str:
    return "".join(
        "<span class='uev-punto' style='background:%s' title='%s'></span>"
        % (SIGNO_COLOR.get(s, TINTA_MUDA), s)
        for s in signos
    )


def fila_clasificacion(pos: int, slug: str | None, nombre: str, pj: int, puntos: int,
                       gf: int, gc: int, forma: list[str], destacado: bool) -> str:
    uri = escudo_uri(slug)
    img = ("<img class='uev-escudo' src='%s'>" % uri) if uri else "<span class='uev-escudo'></span>"
    dif = gf - gc
    signo = "+" if dif > 0 else ""
    return (
        "<div class='uev-clas%s'>"
        "<div class='uev-pos'>%d</div>%s"
        "<div style='flex:1;font-weight:800;font-size:.95rem'>%s</div>"
        "<div class='uev-mini' style='width:34px;text-align:center'>%d</div>"
        "<div class='uev-mini' style='width:86px;text-align:center'>%d&nbsp;-&nbsp;%d "
        "<span style='color:%s'>(%s%d)</span></div>"
        "<div style='width:84px;text-align:right'>%s</div>"
        "<div class='uev-pts'>%d</div>"
        "</div>"
        % (
            " destacado" if destacado else "",
            pos,
            img,
            nombre,
            pj,
            gf,
            gc,
            SIGNO_COLOR["V"] if dif > 0 else (SIGNO_COLOR["D"] if dif < 0 else TINTA_MUDA),
            signo,
            dif,
            puntos_forma(forma),
            puntos,
        )
    )
