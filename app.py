"""UE Valls - Analítica Lliga Elit Grup 1 (Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import altair as alt
import pandas as pd
import streamlit as st

from uevalls import advanced, data, insights, metrics, ui

ASSETS = Path(__file__).parent / "assets"
VALLS = 33936

st.set_page_config(
    page_title="UE Valls · Lliga Elit",
    page_icon=str(ASSETS / "escudos" / "valls.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=1800, show_spinner=False)
def _raw() -> Dict[str, pd.DataFrame]:
    return data.load_all()


@st.cache_data(ttl=1800, show_spinner="Carregant dades de la FCF…")
def cargar(jornadas: tuple) -> Dict[str, pd.DataFrame]:
    return metrics.build(_raw(), jornadas)


@st.cache_data(ttl=1800, show_spinner=False)
def avancades(jornadas: tuple) -> pd.DataFrame:
    return advanced.taula_lliga(cargar(jornadas))


@st.cache_data
def catalogo() -> dict:
    ruta = ASSETS / "equipos.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def info_equipo(cod: int) -> dict:
    return catalogo().get(str(cod), {})


def slug(cod: int) -> str | None:
    return info_equipo(cod).get("slug")


def corto(cod: int, por_defecto: str = "") -> str:
    return info_equipo(cod).get("nombre_corto") or por_defecto


def abrev(cod: int, por_defecto: str = "") -> str:
    return info_equipo(cod).get("abrev") or por_defecto[:3].upper()


def num(valor, formato: str = "%.1f") -> str:
    """Format a number, or an em dash when it does not exist."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    return formato % valor


# --------------------------------------------------------------------------- #
# reusable blocks
# --------------------------------------------------------------------------- #
def barres_equips(df: pd.DataFrame, columna: str, formato: str, destacado: int | None,
                  apoyo: str | None = None) -> str:
    if df.empty:
        return "<div class='sub'>Sense dades en aquest rang de jornades.</div>"
    maximo = float(df[columna].max()) or 1.0
    filas = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        cod = int(r["cod_equipo"])
        resaltar = destacado is not None and cod == destacado
        filas.append(
            ui.fila_ranking(
                i, slug(cod), corto(cod, r.get("equipo", "")), formato % r[columna],
                100.0 * float(r[columna]) / maximo,
                ui.ROJO if resaltar else ui.SERIE_1,
                "" if not apoyo else str(int(r[apoyo])),
            )
        )
    return "".join(filas)


def barres_jugadors(df: pd.DataFrame, columna: str, nombre_col: str,
                    equipo_col: str | None = None,
                    destacado_equipo: int | None = None, formato: str = "%d") -> str:
    if df.empty:
        return "<div class='sub'>Sense dades.</div>"
    maximo = float(df[columna].max()) or 1.0
    filas = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        cod = int(r[equipo_col]) if equipo_col else None
        resaltar = destacado_equipo is not None and cod == destacado_equipo
        filas.append(
            ui.fila_ranking(
                i, slug(cod) if cod else None, str(r[nombre_col]).title(),
                formato % r[columna], 100.0 * float(r[columna]) / maximo,
                ui.ROJO if resaltar else ui.SERIE_1,
                ancho_nombre=150 if equipo_col else 180,
            )
        )
    return "".join(filas)


def barres_simples(items: list[tuple]) -> str:
    """items: (label, value, colour). A tiny bar chart for three or four categories."""
    maximo = max([v for _, v, _ in items] + [1])
    filas = []
    for etiqueta, valor, color in items:
        filas.append(
            "<div class='uev-fila'><div class='uev-nombre' style='width:120px'>%s</div>"
            "<div class='uev-pista'><div class='uev-barra' style='width:%.1f%%;"
            "background:%s'></div></div><div class='uev-valor'>%s</div></div>"
            % (etiqueta, max(100.0 * valor / maximo, 2), color,
               ("%.0f%%" % valor) if isinstance(valor, float) else str(valor))
        )
    return "".join(filas)


def grafic_trams(gf: pd.DataFrame, gc: pd.DataFrame | None, etiqueta: str,
                 color: str = ui.SERIE_1, nom_serie: str = "A favor") -> alt.Chart:
    a = metrics.distribucion_tramos(gf).assign(serie=nom_serie)
    partes = [a]
    if gc is not None:
        partes.append(metrics.distribucion_tramos(gc).assign(serie="En contra"))
    df = pd.concat(partes, ignore_index=True)
    base = alt.Chart(df).mark_bar(
        color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4
    )
    enc = {
        "x": alt.X("tramo:N", sort=metrics.TRAMO_LABELS, title=None,
                   axis=alt.Axis(labelAngle=0, labelFontWeight="bold",
                                 labelColor=ui.TINTA_2)),
        "y": alt.Y("n:Q", title=etiqueta,
                   axis=alt.Axis(grid=True, gridColor=ui.REJILLA,
                                 titleColor=ui.TINTA_MUDA)),
        "tooltip": [alt.Tooltip("tramo:N", title="Minuts"),
                    alt.Tooltip("serie:N", title="Sèrie"),
                    alt.Tooltip("n:Q", title=etiqueta)],
    }
    if gc is not None:
        enc["xOffset"] = alt.XOffset("serie:N")
        enc["color"] = alt.Color(
            "serie:N",
            scale=alt.Scale(domain=["A favor", "En contra"],
                            range=[ui.SERIE_1, ui.SERIE_2]),
            legend=alt.Legend(title=None, orient="top", labelColor=ui.TINTA_2,
                              labelFontWeight="bold"),
        )
    return base.encode(**enc).properties(height=230).configure_view(stroke=None)


def grafic_quadrant(resumen: pd.DataFrame) -> alt.Chart:
    """Attack against defence, one crest per team, with the league averages drawn in."""
    df = resumen[["cod_equipo", "equipo", "gf_por_partido", "gc_por_partido",
                  "puntos", "pj"]].copy()
    df["escut"] = df["cod_equipo"].apply(lambda c: ui.escudo_uri(slug(int(c))))
    df["nom"] = df["cod_equipo"].apply(lambda c: corto(int(c), ""))
    mitjana_gf = float(df["gf_por_partido"].mean())
    mitjana_gc = float(df["gc_por_partido"].mean())

    eix = {"grid": True, "gridColor": ui.REJILLA, "titleColor": ui.TINTA_MUDA,
           "labelColor": ui.TINTA_2, "labelFontWeight": "bold"}
    base = alt.Chart(df).encode(
        x=alt.X("gc_por_partido:Q", title="Gols encaixats per partit",
                scale=alt.Scale(reverse=True, zero=False, nice=True),
                axis=alt.Axis(**eix)),
        y=alt.Y("gf_por_partido:Q", title="Gols marcats per partit",
                scale=alt.Scale(zero=False, nice=True), axis=alt.Axis(**eix)),
        tooltip=[alt.Tooltip("nom:N", title="Equip"),
                 alt.Tooltip("gf_por_partido:Q", title="Marca"),
                 alt.Tooltip("gc_por_partido:Q", title="Encaixa"),
                 alt.Tooltip("puntos:Q", title="Punts"),
                 alt.Tooltip("pj:Q", title="Partits")],
    )
    escuts = base.mark_image(width=34, height=34)
    noms = base.mark_text(dy=26, fontSize=10, fontWeight="bold",
                          color=ui.TINTA_MUDA).encode(text="nom:N")
    linia_v = alt.Chart(pd.DataFrame({"x": [mitjana_gc]})).mark_rule(
        color=ui.TINTA_MUDA, strokeDash=[4, 4]).encode(x="x:Q")
    linia_h = alt.Chart(pd.DataFrame({"y": [mitjana_gf]})).mark_rule(
        color=ui.TINTA_MUDA, strokeDash=[4, 4]).encode(y="y:Q")
    return (
        (linia_v + linia_h + escuts.encode(url="escut:N") + noms)
        .properties(height=440)
        .configure_view(stroke=None)
    )


# --------------------------------------------------------------------------- #
# tab: standings
# --------------------------------------------------------------------------- #
def tab_classificacio(frames: Dict[str, pd.DataFrame], foco: int) -> None:
    resumen = frames["resumen"].sort_values(
        ["puntos", "gf"], ascending=False
    ).reset_index(drop=True)
    ep = frames["equipo_partido"]

    cab = st.columns([3, 1])
    cab[0].markdown("## Classificació")
    cab[1].markdown(
        "<div style='text-align:right;color:%s;font-size:.78rem;font-weight:700;"
        "padding-top:18px'>PJ &nbsp;·&nbsp; GF-GC &nbsp;·&nbsp; ÚLTIMS &nbsp;·&nbsp; PTS</div>"
        % ui.TINTA_MUDA,
        unsafe_allow_html=True,
    )

    filas = []
    for i, r in resumen.iterrows():
        cod = int(r["cod_equipo"])
        forma = list(ep[ep["cod_equipo"] == cod].sort_values("jornada")["signo"].tail(5))
        filas.append(
            ui.fila_clasificacion(
                i + 1, slug(cod), corto(cod, r["equipo"]), int(r["pj"]), int(r["puntos"]),
                int(r["gf"]), int(r["gc"]), forma, cod == foco,
            )
        )
    st.markdown("".join(filas), unsafe_allow_html=True)

    st.markdown("")
    izq, cen, der = st.columns(3)
    goles = frames["goles"]
    tj = frames["tarjetas"][frames["tarjetas"]["es_jugador"]]
    with izq:
        st.markdown("### Quan es marca")
        st.altair_chart(grafic_trams(goles, None, "Gols"), width="stretch")
    with cen:
        st.markdown("### On es marca")
        casa = int(goles["favor_en_casa"].sum())
        fuera = len(goles) - casa
        total = max(len(goles), 1)
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Gols de l'equip local", "%d" % casa, "%.0f%%" % (100 * casa / total)),
                ("Gols del visitant", "%d" % fuera, "%.0f%%" % (100 * fuera / total)),
                ("Gols per partit", "%.2f" % (len(goles) / max(len(frames["partidos"]), 1))),
                ("Partits jugats", "%d" % len(frames["partidos"])),
                ("Gols de penal", "%d" % int(goles["es_penal"].sum())),
                ("Gols en pròpia", "%d" % int(goles["es_propia"].sum())),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
    with der:
        st.markdown("### Primera i segona part")
        p1 = int((goles["parte"] == 1).sum())
        p2 = len(goles) - p1
        t1 = int((tj["parte"] == 1).sum())
        t2 = len(tj) - t1
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Gols 1a part", "%d" % p1),
                ("Gols 2a part", "%d" % p2),
                ("Targetes 1a part", "%d" % t1),
                ("Targetes 2a part", "%d" % t2),
                ("Més targetes a la segona", "x%.1f" % (t2 / t1 if t1 else 0)),
                ("Targetes a la banqueta",
                 "%d" % int((~frames["tarjetas"]["es_jugador"]).sum())),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### Atac i defensa de cada equip")
    st.altair_chart(grafic_quadrant(resumen), width="stretch")
    st.caption(
        "Cada escut al seu lloc segons el que marca i el que encaixa per partit. "
        "A dalt a la dreta, els que marquen molt i encaixen poc. Les línies són la "
        "mitjana de la lliga."
    )


# --------------------------------------------------------------------------- #
# tab: rankings
# --------------------------------------------------------------------------- #
FAMILIAS = {
    "Gols": ["gf_total", "gf_casa", "gf_fuera", "gf_p2_pct", "gf_final", "gf_perdiendo"],
    "Defensa": ["gc_total", "gc_total_mes", "porterias_cero"],
    "Targetes": ["tarjetas_p2", "tarjetas_total"],
    "Banqueta": ["plantilla", "cambios_pronto"],
}

ROADMAP = """
**Ja es calcula ara** (tot surt de l'acta oficial, minut a minut)

Temps guanyant, empatant i perdent · qui marca primer i quants punts dona ·
remuntades i avantatges deixats escapar · del descans al final · ratxa més llarga
sense encaixar · gols de titulars i de suplents · minut mitjà del primer gol marcat
i encaixat · rotació de l'onze entre jornades · jugadors sempre titulars · minut del
primer i de l'últim canvi · targetes per 90 minuts ·
partits on marquen els dos equips · resultat més repetit · gols per tram de 15 minuts
· gols de penal, de jugada i en pròpia.

**Caldran més jornades** (la dada existeix, però encara no té prou mostra)

Gols als primers 20 minuts · gols de resposta en menys de 10 minuts · gols encaixats
just després de marcar · penals · rendiment segons l'àrbitro · rendiment segons el dia
i l'hora del partit · ratxes llargues
de victòries o de porteries a zero · comparació casa/fora fiable.

**Es podria afegir amb més feina de descàrrega**

Temporades anteriors del mateix grup · la resta d'equips del club · la Copa Catalunya ·
l'històric de sancions i de dies de baixa · el calendari complet amb camps i horaris.

**La FCF no ho publica** (no es pot treure de l'acta, per molt que es vulgui)

Tirs i tirs a porta · xG · possessió · córners · faltes · passades · posicions i
sistema de joc · mapes de calor · edat i dades físiques dels jugadors · lesions ·
minuts de descompte reals.
"""

AVANCATS = [
    ("pct_guanyant", "Més temps guanyant", "%.0f%%", "OK",
     "minuts jugats", "minuts_guanyant"),
    ("pct_perdent", "Més temps perdent", "%.0f%%", "OK", "minuts jugats", None),
    ("millor_ratxa", "Ratxa més llarga sense encaixar", "%.0f min", "OK",
     "minuts jugats", None),
    ("gols_per_partit", "Partits amb més gols (els dos equips)", "%.2f", "OK",
     "partits jugats", None),
    ("remuntades", "Més punts rescatats anant per darrere", "%.0f", "DESCARTADO",
     "remuntades i empats rescatats", None),
    ("avantatges_perduts", "Més avantatges deixats escapar", "%.0f", "DESCARTADO",
     "avantatges perduts", None),
    ("gols_suplents", "Més gols des de la banqueta", "%.0f", "DESCARTADO",
     "gols de suplents", None),
    ("sempre_titulars", "Més jugadors sempre titulars", "%.0f", "OK",
     "compareixences a l'acta", None),
    ("canvis_mitjans", "Més canvis a l'onze entre jornades", "%.1f", "ORIENTATIVO",
     "jornades encadenades", None),
    ("primer_canvi", "Primer canvi més tardà", "%.0f'", "OK", "substitucions", None),
]


def tab_rankings(frames: Dict[str, pd.DataFrame], foco: int, rango: tuple) -> None:
    resumen = frames["resumen"]
    control = st.columns([3, 1])
    with control[0]:
        familia = st.pills("Tema", list(FAMILIAS) + ["Avançat"], default="Gols",
                           label_visibility="collapsed")
    with control[1]:
        top = st.slider("Equips per rànquing", 3, 10, 5)
    familia = familia or "Gols"

    if familia == "Avançat":
        taula = avancades(rango)
        st.caption(
            "Aquestes dades es reconstrueixen minut a minut des de l'acta: "
            "quant de temps va per davant cada equip, com remunta i quan fa els canvis."
        )
        cols = st.columns(2)
        for i, (columna, titulo, formato, veredicto, base, apoyo) in enumerate(AVANCATS):
            t = taula.sort_values(columna, ascending=False).head(top)
            with cols[i % 2]:
                st.markdown(
                    ui.tarjeta(
                        titulo,
                        barres_equips(t, columna, formato, foco, apoyo),
                        subtitulo="base: %s" % base,
                        extra=ui.chip(veredicto),
                    ),
                    unsafe_allow_html=True,
                )
        with st.expander("Què més es podrà mesurar"):
            st.markdown(ROADMAP)
        return

    publicables = {r.id: r for r in insights.rankings_publicables(frames)}
    val = insights.validar(frames).set_index("id")
    elegidos = [publicables[i] for i in FAMILIAS[familia] if i in publicables]

    if not elegidos:
        st.info("Cap rànquing d'aquest tema té prou dades encara.")
    cols = st.columns(2)
    for i, r in enumerate(elegidos):
        fila = val.loc[r.id]
        tabla = r.tabla(resumen, top)
        formato = "%.2f" if ("por_partido" in r.columna or r.columna.startswith("min_")) \
            else "%.0f"
        if r.columna == "pct_gf_p2":
            formato = "%.0f%%"
        with cols[i % 2]:
            st.markdown(
                ui.tarjeta(
                    r.titulo,
                    barres_equips(tabla, r.columna, formato, foco,
                                  r.columna_apoyo if r.columna_apoyo in tabla else None),
                    subtitulo="%s · base de %d esdeveniments" % (r.unidad, int(fila["n"])),
                    extra=ui.chip(fila["veredicto"]),
                ),
                unsafe_allow_html=True,
            )

    descartados = insights.rankings_descartados(frames)
    if descartados:
        with st.expander("El que encara no es pot ordenar (%d preguntes)" % len(descartados)):
            st.caption(
                "Calen més jornades. Es mostren els totals de la lliga, sense rànquing: "
                "amb tan pocs esdeveniments, l'ordre entre equips seria atzar."
            )
            for r in descartados:
                st.markdown("**%s** — %d a tota la lliga"
                            % (r.titulo, int(val.loc[r.id, "n"])))

    with st.expander("Com es decideix què es pot mostrar"):
        v = insights.validar(frames).sort_values("n", ascending=False)
        maximo = float(v["n"].max()) or 1.0
        filas = []
        for _, fila in v.iterrows():
            color = ui.ESTADO[fila["veredicto"]]
            filas.append(
                "<div class='uev-fila'>"
                "<div class='uev-nombre' style='width:300px' title='%s'>%s</div>"
                "<div class='uev-pista'><div class='uev-barra' style='width:%.1f%%;"
                "background:%s'></div></div>"
                "<div class='uev-valor'>%d</div>"
                "<div style='width:150px;text-align:right'>%s</div></div>"
                % (fila["poblacion"], fila["insight"],
                   max(100.0 * int(fila["n"]) / maximo, 2), color, int(fila["n"]),
                   ui.chip(fila["veredicto"]))
            )
        st.markdown("<div class='uev-card'>" + "".join(filas) + "</div>",
                    unsafe_allow_html=True)
        st.caption(
            "Cada pregunta es qualifica pel nombre d'esdeveniments que la sostenen: "
            "a partir de %d és dada sòlida, a partir de %d són poques dades, per sota "
            "no s'ordena. Es recalcula amb cada jornada nova."
            % (insights.UMBRAL_OK, insights.UMBRAL_ORIENTATIVO)
        )


# --------------------------------------------------------------------------- #
# tab: team
# --------------------------------------------------------------------------- #
def selector_equip(frames: Dict[str, pd.DataFrame]) -> int:
    equipos = frames["equipos"].sort_values("equipo").reset_index(drop=True)
    if "equipo" not in st.session_state:
        st.session_state["equipo"] = VALLS

    por_fila = 8
    for inicio in range(0, len(equipos), por_fila):
        trozo = equipos.iloc[inicio:inicio + por_fila]
        cols = st.columns(por_fila)
        for col, (_, r) in zip(cols, trozo.iterrows()):
            cod = int(r["cod_equipo"])
            activo = st.session_state["equipo"] == cod
            with col:
                st.markdown(
                    "<div style='text-align:center;padding:6px 0 2px'>"
                    "<img src='%s' style='width:46px;height:46px;object-fit:contain;"
                    "opacity:%s'></div>"
                    % (ui.escudo_uri(slug(cod)), "1" if activo else ".55"),
                    unsafe_allow_html=True,
                )
                if st.button(abrev(cod, r["equipo"]), key="eq_%d" % cod,
                             type="primary" if activo else "secondary"):
                    st.session_state["equipo"] = cod
                    st.rerun()
    return int(st.session_state["equipo"])


def _sub_resum(frames, cod, r, mis, gf, gc) -> None:
    temps = advanced.temps_en_marcador(frames, cod)
    primer = advanced.primer_gol(frames, cod)
    rem = advanced.remuntades(frames, cod)
    perfil = advanced.perfil_partits(frames, cod)
    minuts = advanced.minuts_primer_gol(frames, cod)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Temps al marcador")
        st.markdown(
            "<div class='uev-card'>"
            + barres_simples([
                ("Guanyant", temps["pct_guanyant"], ui.SERIE_3),
                ("Empatant", temps["pct_empatant"], ui.SERIE_4),
                ("Perdent", temps["pct_perdent"], ui.SERIE_2),
            ])
            + ui.linies([
                ("Minuts per davant", "%d min" % temps["guanyant"]),
                ("Minuts per darrere", "%d min" % temps["perdent"]),
                ("Minuts jugats", "%d min" % temps["total"]),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Reconstruït minut a minut des de l'ordre dels gols de l'acta.")
    with c2:
        st.markdown("### Qui marca primer")
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Partits marcant primer", "%d" % primer["marca_primer"]),
                ("Punts per partit quan marca primer",
                 num(primer["mitjana_marcant_primer"], "%.2f")),
                ("Partits encaixant primer", "%d" % primer["encaixa_primer"]),
                ("Punts per partit quan encaixa primer",
                 num(primer["mitjana_encaixant_primer"], "%.2f")),
                ("Minut mitjà del seu 1r gol", num(minuts["primer_marcat"], "%.0f'")),
                ("Minut mitjà del 1r gol encaixat",
                 num(minuts["primer_encaixat"], "%.0f'")),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown("### Com es mouen els partits")
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Partits anant per darrere", "%d" % rem["va_anar_per_darrere"]),
                ("Remuntats (victòria)", "%d" % rem["remuntades"]),
                ("Empats rescatats", "%d" % rem["empats_rescatats"]),
                ("Avantatges deixats escapar", "%d" % rem["avantatges_perduts"]),
                ("Partits on marquen els dos", "%d de %d"
                 % (perfil.get("ambdos_marquen", 0), perfil.get("partits", 0))),
                ("Resultat més repetit", perfil.get("resultat_mes_repetit", "—")),
                ("Gols per partit (els dos equips)",
                 num(perfil.get("gols_per_partit"), "%.2f")),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )

    izq, der = st.columns([3, 2])
    with izq:
        st.markdown("### Quan marca i quan encaixa")
        st.altair_chart(grafic_trams(gf, gc, "Gols"), width="stretch")
        st.caption(
            "La FCF agrupa el descompte: 45+X surt com a minut 44 i 90+X com a 89."
        )
    with der:
        st.markdown("### Casa i fora")
        casa = mis[mis["es_local"]]
        fuera = mis[~mis["es_local"]]
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("A casa", "%d-%d" % (casa["gf_total"].sum(), casa["gc_total"].sum()),
                 "%d partits" % len(casa)),
                ("Punts a casa", "%d" % casa["puntos"].sum(),
                 num(casa["puntos"].mean() if len(casa) else None, "%.2f/partit")),
                ("Fora", "%d-%d" % (fuera["gf_total"].sum(), fuera["gc_total"].sum()),
                 "%d partits" % len(fuera)),
                ("Punts fora", "%d" % fuera["puntos"].sum(),
                 num(fuera["puntos"].mean() if len(fuera) else None, "%.2f/partit")),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )


def _sub_gols(frames, cod, gf) -> None:
    g = frames["goles"]
    suplents = advanced.gols_suplents(frames, cod)
    total = max(len(gf), 1)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Golejadors")
        gol = metrics.goleadores(g, frames["personas"], cod).head(10)
        st.markdown(
            "<div class='uev-card'>" + barres_jugadors(gol, "goles", "jugador") + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Els gols en pròpia no s'atribueixen a cap golejador de l'equip.")
        st.markdown("### Gols marcats per franja")
        st.altair_chart(grafic_trams(gf, None, "Gols marcats", ui.SERIE_1, "A favor"),
                        width="stretch")
    with c2:
        st.markdown("### Amb quin marcador marca")
        st.markdown(
            "<div class='uev-card'>"
            + barres_simples([
                ("Perdent", int((gf["estado"] == "perdent").sum()), ui.SERIE_2),
                ("Empat", int((gf["estado"] == "empat").sum()), ui.SERIE_4),
                ("Guanyant", int((gf["estado"] == "guanyant").sum()), ui.SERIE_3),
            ])
            + ui.linies([
                ("Gols de resposta (≤10 min)", "%d" % int(gf["es_respuesta"].sum())),
                ("Gols als primers 20 min", "%d" % int((gf["minuto"] <= 20).sum())),
                ("Gols des del minut 75", "%d" % int((gf["minuto"] >= 75).sum())),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown("### Tipus de gol")
        st.markdown(
            "<div class='uev-card'>"
            + barres_simples([
                ("De jugada", int((gf["tipo"] == "de jugada").sum()), ui.SERIE_1),
                ("De penal", int((gf["tipo"] == "de penal").sum()), ui.SERIE_5),
                ("En pròpia", int((gf["tipo"] == "en pròpia").sum()), ui.SERIE_4),
            ])
            + "<div style='height:14px'></div>"
            + barres_simples([
                ("Titulars", suplents["titulars"], ui.SERIE_1),
                ("Suplents", suplents["suplents"], ui.SERIE_3),
            ])
            + "<div style='height:14px'></div>"
            + barres_simples([
                ("1a part", int((gf["parte"] == 1).sum()), ui.SERIE_1),
                ("2a part", int((gf["parte"] == 2).sum()), ui.SERIE_2),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "%d gols a favor, de %d golejadors diferents."
            % (total, int(gf[~gf["es_propia"]]["cod_persona"].nunique()))
        )

    st.markdown("### Els gols, partit a partit")
    st.caption(
        "Cada barra és un partit de 0 a 90 minuts. Els punts blaus són gols a favor "
        "i els taronges en contra; el número de dins és el minut."
    )
    _timelines(frames, cod)


def _timelines(frames, cod) -> None:
    """Every match of the team drawn as a 0-90 minute track with its goals."""
    g = frames["goles"].merge(
        frames["personas"].rename(columns={"nombre": "jugador"}),
        on="cod_persona", how="left",
    )
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod].sort_values("jornada")

    cols = st.columns(2)
    for i, (_, p) in enumerate(mis.iterrows()):
        en_acta = g[g["cod_acta"] == p["cod_acta"]]
        gols = []
        for _, gol in en_acta.iterrows():
            a_favor = gol["cod_equipo_favor"] == cod
            nom = str(gol["jugador"] or "").title()
            extra = "" if gol["tipo"] == "de jugada" else " (%s)" % gol["tipo"]
            gols.append({"minut": int(gol["minuto"]), "a_favor": bool(a_favor),
                         "text": nom + extra})
        rival_cod = int(p["cod_equipo_rival"])
        with cols[i % 2]:
            st.markdown(
                "<div class='uev-card'>" + ui.timeline_partit(
                    int(p["jornada"]), slug(rival_cod), corto(rival_cod, p["rival"]),
                    int(p["gf_total"]), int(p["gc_total"]),
                    "Casa" if p["es_local"] else "Fora", p["signo"], gols,
                ) + "</div>",
                unsafe_allow_html=True,
            )


def _sub_defensa(frames, cod, gc, r) -> None:
    ratxa = advanced.ratxa_sense_encaixar(frames, cod)
    tj = frames["tarjetas"]
    mis_t = tj[(tj["cod_equipo"] == cod) & (tj["es_jugador"])]
    banqueta = tj[(tj["cod_equipo"] == cod) & (~tj["es_jugador"])]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Gols encaixats")
        st.altair_chart(grafic_trams(gc, None, "Gols encaixats", ui.SERIE_2, "En contra"),
                        width="stretch")
        # the state stored on a goal belongs to the team that scored it, so for the
        # conceding side it reads the other way round
        inverso = {"perdent": "guanyant", "guanyant": "perdent", "empat": "empat"}
        estats = gc["estado"].map(inverso)
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Porteries a zero", "%d de %d" % (int(r["porterias_cero"]), int(r["pj"]))),
                ("Ratxa més llarga sense encaixar", "%d min" % ratxa["millor_ratxa"]),
                ("Ratxa actual", "%d min" % ratxa["ratxa_actual"]),
                ("Encaixa anant guanyant", "%d" % int((estats == "guanyant").sum())),
                ("Encaixa amb empat", "%d" % int((estats == "empat").sum())),
                ("Encaixa anant perdent", "%d" % int((estats == "perdent").sum())),
                ("Encaixa ≤10 min després de marcar",
                 "%d" % int(gc["es_respuesta"].sum())),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("### Targetes")
        if len(mis_t):
            st.altair_chart(grafic_trams(mis_t, None, "Targetes", ui.SERIE_4, "Targetes"),
                            width="stretch")
        per90 = advanced.targetes_per_90(frames, cod)
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Grogues", "%d" % int(r["amarillas"])),
                ("Vermelles", "%d" % int(r["rojas"])),
                ("Per partit", "%.2f" % r["tarjetas_por_partido"]),
                ("A la segona part", "%d de %d"
                 % (int((mis_t["parte"] == 2).sum()), len(mis_t))),
                ("A la banqueta (no compten als rànquings)", "%d" % len(banqueta)),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )
        if len(per90):
            st.markdown("**Targetes per 90 minuts** (mínim 90 min jugats)")
            st.markdown(
                "<div class='uev-card'>"
                + barres_jugadors(per90.head(8), "per_90", "persona", formato="%.2f")
                + "</div>",
                unsafe_allow_html=True,
            )


def _sub_plantilla(frames, cod) -> None:
    rot = advanced.rotacio(frames, cod)
    canvis = advanced.perfil_canvis(frames, cod)
    mn = frames["minutos"]
    mios = mn[(mn["cod_equipo"] == cod) & (mn["jugo"])]

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("### Minuts jugats")
        top_m = (
            mios.groupby("persona")["minutos"].sum().rename("minutos").reset_index()
            .sort_values("minutos", ascending=False).head(14)
        )
        st.markdown(
            "<div class='uev-card'>" + barres_jugadors(top_m, "minutos", "persona")
            + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("### Rotació i banqueta")
        st.markdown(
            "<div class='uev-card'>"
            + ui.linies([
                ("Jugadors utilitzats", "%d" % rot["jugadors_utilitzats"]),
                ("Sempre titulars", "%d" % rot["sempre_titulars"]),
                ("Canvis a l'onze per jornada", num(rot["canvis_mitjans"], "%.1f"),
                 "de %d a %d" % (rot["canvis_minim"], rot["canvis_maxim"])),
                ("Substitucions", "%d" % canvis.get("canvis", 0)),
                ("Per partit", num(canvis.get("canvis_per_partit"), "%.1f")),
                ("Minut del primer canvi", num(canvis.get("primer_canvi"), "%.0f'")),
                ("Minut de l'últim canvi", num(canvis.get("ultim_canvi"), "%.0f'")),
                ("Canvis abans del minut 60", "%d" % canvis.get("abans_del_60", 0)),
            ])
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### Plantilla completa")
    plant = (
        mios.groupby("persona")
        .agg(partits=("cod_acta", "nunique"), titular=("titular", "sum"),
             minuts=("minutos", "sum"))
        .reset_index()
    )
    tj = frames["tarjetas"]
    tarj = (
        tj[(tj["cod_equipo"] == cod) & (tj["es_jugador"])]
        .groupby("persona").size().rename("targetes").reset_index()
    )
    gol_j = metrics.goleadores(frames["goles"], frames["personas"], cod)[
        ["jugador", "goles"]
    ].rename(columns={"jugador": "persona", "goles": "gols"})
    plant = plant.merge(tarj, on="persona", how="left").merge(gol_j, on="persona",
                                                              how="left")
    plant[["targetes", "gols"]] = plant[["targetes", "gols"]].fillna(0).astype(int)
    plant = plant.sort_values("minuts", ascending=False).reset_index(drop=True)

    maximo = float(plant["minuts"].max()) or 1.0
    mitad = (len(plant) + 1) // 2
    cols = st.columns(2)
    for columna, trozo in zip(cols, (plant.iloc[:mitad], plant.iloc[mitad:])):
        filas = []
        for i, (_, j) in enumerate(trozo.iterrows(), start=1):
            chips = ui.pill("%d XI" % int(j["titular"]), ui.TINTA_MUDA)
            if j["gols"]:
                chips += ui.pill("%d gol%s" % (int(j["gols"]),
                                               "" if j["gols"] == 1 else "s"), ui.SERIE_3)
            if j["targetes"]:
                chips += ui.pill("%d targ." % int(j["targetes"]), ui.SERIE_4)
            filas.append(
                ui.fila_jugador(
                    i + (0 if columna is cols[0] else mitad),
                    str(j["persona"]).title(), "%d'" % int(j["minuts"]),
                    100.0 * float(j["minuts"]) / maximo, ui.SERIE_1, chips,
                )
            )
        columna.markdown("<div class='uev-card'>" + "".join(filas) + "</div>",
                         unsafe_allow_html=True)
    st.caption(
        "Minuts estimats: titular des del 0, suplent des del seu minut d'entrada, "
        "fins a la substitució, la vermella o el 90. El descompte no es compta. "
        "XI = partits de titular."
    )


def _sub_partits(frames, cod, mis) -> None:
    c1, c2 = st.columns([2, 3])
    with c1:
        st.markdown("### Partits")
        filas = ""
        for _, p in mis.iterrows():
            rival_cod = int(p["cod_equipo_rival"])
            filas += (
                "<div class='uev-fila'>"
                "<div class='uev-pos'>J%d</div>"
                "<img class='uev-escudo' src='%s'>"
                "<div class='uev-nombre'>%s</div>"
                "<div class='uev-apoyo' style='width:46px'>%s</div>"
                "<div class='uev-valor'>%d-%d</div>"
                "<div style='width:26px;text-align:right;font-weight:800;color:%s'>%s</div>"
                "</div>"
                % (int(p["jornada"]), ui.escudo_uri(slug(rival_cod)),
                   corto(rival_cod, p["rival"]), "Casa" if p["es_local"] else "Fora",
                   int(p["gf_total"]), int(p["gc_total"]),
                   ui.SIGNO_COLOR[p["signo"]], p["signo"])
            )
        st.markdown("<div class='uev-card'>" + filas + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("### Del descans al final")
        df = advanced.descans_final(frames, cod)
        if not len(df):
            return
        guanyats = int(df[df["diferencia"] > 0]["diferencia"].sum())
        perduts = int(-df[df["diferencia"] < 0]["diferencia"].sum())
        st.markdown(
            "<div class='uev-card'>"
            + barres_simples([
                ("Punts guanyats", guanyats, ui.SERIE_3),
                ("Punts perduts", perduts, ui.SERIE_2),
            ])
            + "<div class='sub' style='margin-top:10px'>Comparant el que valia el "
              "marcador al descans amb el del final.</div>"
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "".join(
                ui.fila_descans(slug(int(f["cod_equipo_rival"])),
                                corto(int(f["cod_equipo_rival"]), f["rival"]),
                                f["descans"], f["final"], int(f["diferencia"]),
                                f["signe_final"])
                for _, f in df.iterrows()
            ),
            unsafe_allow_html=True,
        )


def tab_equip(frames: Dict[str, pd.DataFrame]) -> None:
    cod = selector_equip(frames)
    resumen = frames["resumen"].sort_values(
        ["puntos", "gf"], ascending=False
    ).reset_index(drop=True)
    if cod not in set(resumen["cod_equipo"]):
        st.info("Aquest equip no té partits en el rang de jornades triat.")
        return
    pos = int(resumen.index[resumen["cod_equipo"] == cod][0]) + 1
    r = resumen[resumen["cod_equipo"] == cod].iloc[0]

    g = frames["goles"]
    gf = g[g["cod_equipo_favor"] == cod]
    gc = g[g["cod_equipo_contra"] == cod]
    mis = frames["equipo_partido"]
    mis = mis[mis["cod_equipo"] == cod].sort_values("jornada")

    st.divider()
    cab = st.columns([1, 5])
    cab[0].markdown(
        "<img src='%s' style='width:96px;height:96px;object-fit:contain'>"
        % ui.escudo_uri(slug(cod)),
        unsafe_allow_html=True,
    )
    cab[1].markdown(
        "<h1 style='margin-bottom:0'>%s</h1>"
        "<div style='color:%s;font-weight:700;font-size:1rem'>%dè · %d punts · "
        "%d partits · %d-%d-%d</div>"
        % (corto(cod, r["equipo"]), ui.TINTA_2, pos, int(r["puntos"]), int(r["pj"]),
           int(r["v"]), int(r["e"]), int(r["d"])),
        unsafe_allow_html=True,
    )

    k = st.columns(6)
    k[0].metric("Gols a favor · %.2f/partit" % r["gf_por_partido"], int(r["gf"]))
    k[1].metric("Gols en contra · %.2f/partit" % r["gc_por_partido"], int(r["gc"]))
    k[2].metric("GF 1a / 2a part", "%d / %d" % (int(r["gf_p1"]), int(r["gf_p2"])))
    k[3].metric("GC 1a / 2a part", "%d / %d" % (int(r["gc_p1"]), int(r["gc_p2"])))
    k[4].metric("Targetes · %.2f/partit" % r["tarjetas_por_partido"],
                int(r["amarillas"] + r["rojas"]))
    k[5].metric("Porteries a zero", int(r["porterias_cero"]))

    s1, s2, s3, s4, s5 = st.tabs(
        ["Resum", "Gols", "Defensa i targetes", "Plantilla", "Partits i context"]
    )
    with s1:
        _sub_resum(frames, cod, r, mis, gf, gc)
    with s2:
        _sub_gols(frames, cod, gf)
    with s3:
        _sub_defensa(frames, cod, gc, r)
    with s4:
        _sub_plantilla(frames, cod)
    with s5:
        _sub_partits(frames, cod, mis)


# --------------------------------------------------------------------------- #
# tab: players
# --------------------------------------------------------------------------- #
def tab_jugadors(frames: Dict[str, pd.DataFrame], foco: int) -> None:
    g = frames["goles"]
    personas = frames["personas"]
    gol = metrics.goleadores(g, personas).head(12)
    gol = gol.merge(
        g.groupby("cod_persona")["cod_equipo_favor"].first().reset_index(),
        on="cod_persona", how="left",
    )

    tj = frames["tarjetas"]
    tj = tj[tj["es_jugador"]]
    tar = (
        tj.groupby(["cod_persona", "persona", "cod_equipo"]).size().rename("targetes")
        .reset_index().sort_values("targetes", ascending=False).head(12)
    )
    mn = frames["minutos"]
    minu = (
        mn[mn["jugo"]].groupby(["cod_persona", "persona", "cod_equipo"])["minutos"]
        .sum().reset_index().sort_values("minutos", ascending=False).head(12)
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Màxims golejadors")
        st.markdown(
            "<div class='uev-card'>"
            + barres_jugadors(gol, "goles", "jugador", "cod_equipo_favor", foco)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Sense gols en pròpia: compten per al rival, no per a l'autor.")
    with c2:
        st.markdown("### Més targetes")
        st.markdown(
            "<div class='uev-card'>"
            + barres_jugadors(tar, "targetes", "persona", "cod_equipo", foco)
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown("### Més minuts")
        st.markdown(
            "<div class='uev-card'>"
            + barres_jugadors(minu, "minutos", "persona", "cod_equipo", foco)
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Tots els golejadors de la lliga"):
        completo = metrics.goleadores(g, personas).merge(
            g.groupby("cod_persona")["cod_equipo_favor"].first().reset_index(),
            on="cod_persona", how="left",
        )
        maximo = float(completo["goles"].max()) or 1.0
        mitad = (len(completo) + 1) // 2
        cols = st.columns(2)
        for desplazamiento, (columna, trozo) in enumerate(
            zip(cols, (completo.iloc[:mitad], completo.iloc[mitad:]))
        ):
            filas = []
            for i, (_, j) in enumerate(trozo.iterrows(), start=1):
                equip = int(j["cod_equipo_favor"])
                chips = ui.pill(abrev(equip, ""), ui.TINTA_MUDA)
                if j["penales"]:
                    chips += ui.pill("%d penal%s" % (int(j["penales"]),
                                                     "" if j["penales"] == 1 else "s"),
                                     ui.SERIE_5)
                filas.append(
                    ui.fila_jugador(
                        i + desplazamiento * mitad, str(j["jugador"]).title(),
                        "%d" % int(j["goles"]), 100.0 * float(j["goles"]) / maximo,
                        ui.ROJO if equip == foco else ui.SERIE_1, chips,
                    )
                )
            columna.markdown("<div class='uev-card'>" + "".join(filas) + "</div>",
                             unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.markdown(ui.CSS, unsafe_allow_html=True)

    try:
        jornadas_max = int(_raw()["partidos"].query("jugado")["jornada"].max())
    except Exception as exc:
        st.error("No s'han pogut carregar les dades: %s" % exc)
        st.stop()
        return

    cab = st.columns([5, 3, 1])
    with cab[0]:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:14px'>"
            "<img src='%s' style='width:52px;height:52px;object-fit:contain'>"
            "<div><div style='font-size:1.6rem;font-weight:800;line-height:1.1'>"
            "Lliga Elit · Grup 1</div>"
            "<div style='color:%s;font-weight:700;font-size:.85rem'>Temporada 2026-27 · "
            "dades oficials FCF</div></div></div>"
            % (ui.escudo_uri("valls"), ui.TINTA_MUDA),
            unsafe_allow_html=True,
        )
    with cab[1]:
        rango = st.slider("Jornades", 1, jornadas_max, (1, jornadas_max))
    with cab[2]:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        with st.popover("Llegenda"):
            st.markdown(
                "**Fiabilitat de cada dada**\n\n"
                "- %s amb prou esdeveniments al darrere\n"
                "- %s l'ordre pot canviar amb un partit\n"
                "- %s no s'ordena, només s'ensenya el total\n\n"
                "**Tres avisos sobre la font**\n\n"
                "- El descompte va agrupat: 45+X surt com a minut 44 i 90+X com a 89.\n"
                "- Els equips han jugat entre 3 i 5 partits, així que els rànquings "
                "de volum van per partit.\n"
                "- Les targetes de la banqueta es compten a part i no entren als "
                "rànquings."
                % (ui.chip("OK"), ui.chip("ORIENTATIVO"), ui.chip("DESCARTADO")),
                unsafe_allow_html=True,
            )

    frames = cargar(tuple(rango))
    if frames["resumen"].empty:
        st.warning("No hi ha partits jugats en aquest rang de jornades.")
        st.stop()
        return

    foco = int(st.session_state.get("equipo", VALLS))
    t1, t2, t3, t4 = st.tabs(["Classificació", "Rànquings", "Equip", "Jugadors"])
    with t1:
        tab_classificacio(frames, foco)
    with t2:
        tab_rankings(frames, foco, tuple(rango))
    with t3:
        tab_equip(frames)
    with t4:
        tab_jugadors(frames, foco)


if __name__ == "__main__":
    main()
