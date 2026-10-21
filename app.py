"""UE Valls - Analítica Lliga Elit Grup 1 (Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import altair as alt
import pandas as pd
import streamlit as st

from uevalls import data, insights, metrics, ui

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


@st.cache_data(ttl=1800, show_spinner="Cargando datos de la FCF…")
def cargar(jornadas: tuple) -> Dict[str, pd.DataFrame]:
    return metrics.build(_raw(), jornadas)


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


# --------------------------------------------------------------------------- #
# reusable blocks
# --------------------------------------------------------------------------- #
def bloque_ranking(df: pd.DataFrame, columna: str, formato: str, destacado: int | None,
                   color: str = ui.ROJO, apoyo: str | None = None) -> str:
    if df.empty:
        return "<div class='sub'>Sin datos en este rango de jornadas.</div>"
    maximo = float(df[columna].max()) or 1.0
    filas = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        cod = int(r["cod_equipo"])
        resaltar = destacado is not None and cod == destacado
        filas.append(
            ui.fila_ranking(
                i,
                slug(cod),
                corto(cod, r.get("equipo", "")),
                formato % r[columna],
                100.0 * float(r[columna]) / maximo,
                color if resaltar else ui.SERIE_1,
                "" if not apoyo else str(int(r[apoyo])),
            )
        )
    return "".join(filas)


def bloque_ranking_jugadores(df: pd.DataFrame, columna: str, nombre_col: str,
                             equipo_col: str | None = None,
                             destacado_equipo: int | None = None) -> str:
    if df.empty:
        return "<div class='sub'>Sin datos.</div>"
    maximo = float(df[columna].max()) or 1.0
    filas = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        cod = int(r[equipo_col]) if equipo_col else None
        resaltar = destacado_equipo is not None and cod == destacado_equipo
        filas.append(
            ui.fila_ranking(
                i,
                slug(cod) if cod else None,
                str(r[nombre_col]).title(),
                "%d" % r[columna],
                100.0 * float(r[columna]) / maximo,
                ui.ROJO if resaltar else ui.SERIE_1,
                ancho_nombre=150 if equipo_col else 180,
            )
        )
    return "".join(filas)


def grafico_tramos(gf: pd.DataFrame, gc: pd.DataFrame | None, etiqueta: str) -> alt.Chart:
    a = metrics.distribucion_tramos(gf).assign(serie="A favor")
    partes = [a]
    if gc is not None:
        partes.append(metrics.distribucion_tramos(gc).assign(serie="En contra"))
    df = pd.concat(partes, ignore_index=True)
    base = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    enc = {
        "x": alt.X("tramo:N", sort=metrics.TRAMO_LABELS, title=None,
                   axis=alt.Axis(labelAngle=0, labelFontWeight="bold", labelColor=ui.TINTA_2)),
        "y": alt.Y("n:Q", title=etiqueta,
                   axis=alt.Axis(grid=True, gridColor=ui.REJILLA, titleColor=ui.TINTA_MUDA)),
        "tooltip": [alt.Tooltip("tramo:N", title="Minutos"),
                    alt.Tooltip("serie:N", title="Serie"),
                    alt.Tooltip("n:Q", title="Goles")],
    }
    if gc is not None:
        enc["xOffset"] = alt.XOffset("serie:N")
        enc["color"] = alt.Color(
            "serie:N",
            scale=alt.Scale(domain=["A favor", "En contra"], range=[ui.SERIE_1, ui.SERIE_2]),
            legend=alt.Legend(title=None, orient="top", labelColor=ui.TINTA_2,
                              labelFontWeight="bold"),
        )
    else:
        base = base.mark_bar(color=ui.SERIE_1, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    return base.encode(**enc).properties(height=230).configure_view(stroke=None)


# --------------------------------------------------------------------------- #
# tabs
# --------------------------------------------------------------------------- #
def tab_clasificacion(frames: Dict[str, pd.DataFrame], foco: int) -> None:
    resumen = frames["resumen"].sort_values(
        ["puntos", "gf"], ascending=False
    ).reset_index(drop=True)
    ep = frames["equipo_partido"]

    cab = st.columns([3, 1])
    cab[0].markdown("## Clasificación")
    cab[1].markdown(
        "<div style='text-align:right;color:%s;font-size:.8rem;font-weight:700;"
        "padding-top:18px'>PJ &nbsp;·&nbsp; GF-GC &nbsp;·&nbsp; ÚLTIMOS &nbsp;·&nbsp; PTS</div>"
        % ui.TINTA_MUDA,
        unsafe_allow_html=True,
    )

    filas = []
    for i, r in resumen.iterrows():
        cod = int(r["cod_equipo"])
        forma = list(
            ep[ep["cod_equipo"] == cod].sort_values("jornada")["signo"].tail(5)
        )
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
        st.markdown("### Cuándo se marca")
        st.altair_chart(grafico_tramos(goles, None, "Goles"), width="stretch")
    with cen:
        st.markdown("### Dónde se marca")
        casa = int(goles["favor_en_casa"].sum())
        fuera = len(goles) - casa
        st.markdown(
            "<div class='uev-card'>"
            + ui.dato("%d" % casa, "goles del equipo local (%.0f%%)" % (100 * casa / max(len(goles), 1)))
            + ui.dato("%d" % fuera, "goles del visitante (%.0f%%)" % (100 * fuera / max(len(goles), 1)))
            + ui.dato("%.2f" % (len(goles) / max(len(frames["partidos"]), 1)), "goles por partido")
            + "</div>",
            unsafe_allow_html=True,
        )
    with der:
        st.markdown("### Partes")
        p1 = int((goles["parte"] == 1).sum())
        p2 = len(goles) - p1
        t1 = int((tj["parte"] == 1).sum())
        t2 = len(tj) - t1
        st.markdown(
            "<div class='uev-card'>"
            + ui.dato("%d / %d" % (p1, p2), "goles 1ª / 2ª parte")
            + ui.dato("%d / %d" % (t1, t2), "tarjetas 1ª / 2ª parte")
            + ui.dato("x%.1f" % (t2 / t1 if t1 else 0), "más tarjetas en la segunda")
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Ver la tabla completa con todos los números"):
        tabla = resumen[
            ["equipo", "pj", "v", "e", "d", "puntos", "gf", "gc", "gf_p1", "gf_p2",
             "gc_p1", "gc_p2", "gf_casa", "gf_fuera", "gc_casa", "gc_fuera",
             "amarillas", "rojas", "porterias_cero"]
        ]
        st.dataframe(
            tabla, hide_index=True, width="stretch",
            column_config={
                "equipo": "Equipo", "pj": "PJ", "v": "G", "e": "E", "d": "P",
                "puntos": "Pts", "gf": "GF", "gc": "GC", "gf_p1": "GF 1ª",
                "gf_p2": "GF 2ª", "gc_p1": "GC 1ª", "gc_p2": "GC 2ª",
                "gf_casa": "GF casa", "gf_fuera": "GF fuera", "gc_casa": "GC casa",
                "gc_fuera": "GC fuera", "amarillas": "Amar.", "rojas": "Rojas",
                "porterias_cero": "P. a cero",
            },
        )


FAMILIAS = {
    "Goles": ["gf_total", "gf_casa", "gf_fuera", "gf_p2_pct", "gf_final", "gf_perdiendo"],
    "Defensa": ["gc_total", "porterias_cero"],
    "Tarjetas": ["tarjetas_p2", "tarjetas_total"],
    "Banquillo": ["plantilla", "cambios_pronto"],
}


def tab_rankings(frames: Dict[str, pd.DataFrame], foco: int) -> None:
    resumen = frames["resumen"]
    control = st.columns([3, 1])
    with control[0]:
        familia = st.pills("Tema", list(FAMILIAS), default="Goles", label_visibility="collapsed")
    with control[1]:
        top = st.slider("Equipos por ranking", 3, 10, 5)
    familia = familia or "Goles"

    publicables = {r.id: r for r in insights.rankings_publicables(frames)}
    val = insights.validar(frames).set_index("id")
    elegidos = [publicables[i] for i in FAMILIAS[familia] if i in publicables]

    if not elegidos:
        st.info("Ningún ranking de este tema tiene datos suficientes todavía.")
    cols = st.columns(2)
    for i, r in enumerate(elegidos):
        fila = val.loc[r.id]
        tabla = r.tabla(resumen, top)
        formato = "%.2f" if "por_partido" in r.columna or r.columna.startswith("min_") else "%.0f"
        if r.columna == "pct_gf_p2":
            formato = "%.0f%%"
        with cols[i % 2]:
            st.markdown(
                ui.tarjeta(
                    r.titulo,
                    bloque_ranking(tabla, r.columna, formato, foco,
                                   apoyo=r.columna_apoyo if r.columna_apoyo in tabla else None),
                    subtitulo="%s · base de %d eventos" % (r.unidad, int(fila["n"])),
                    extra=ui.chip(fila["veredicto"]),
                ),
                unsafe_allow_html=True,
            )

    descartados = insights.rankings_descartados(frames)
    if descartados:
        with st.expander("Lo que todavía no se puede ordenar (%d preguntas)" % len(descartados)):
            st.caption(
                "Hacen falta más jornadas. Se muestran los totales de la liga, sin ranking: "
                "con tan pocos eventos, el orden entre equipos sería azar."
            )
            for r in descartados:
                fila = val.loc[r.id]
                st.markdown(
                    "**%s** — %d en toda la liga" % (r.titulo, int(fila["n"]))
                )

    with st.expander("Cómo se decide qué se puede mostrar"):
        v = insights.validar(frames)
        st.dataframe(
            v[["insight", "poblacion", "n", "veredicto"]], hide_index=True,
            width="stretch",
            column_config={"insight": "Pregunta", "poblacion": "Qué la sostiene",
                           "n": "Eventos", "veredicto": "Fiabilidad"},
        )
        st.caption(
            "Cada pregunta se califica por el número de eventos que la sostienen: "
            "a partir de %d es dato sólido, a partir de %d son pocos datos, por debajo "
            "no se ordena. Se recalcula con cada jornada nueva."
            % (insights.UMBRAL_OK, insights.UMBRAL_ORIENTATIVO)
        )


def selector_equipo(frames: Dict[str, pd.DataFrame]) -> int:
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
            uri = ui.escudo_uri(slug(cod))
            with col:
                st.markdown(
                    "<div style='text-align:center;padding:6px 0 2px'>"
                    "<img src='%s' style='width:46px;height:46px;object-fit:contain;"
                    "opacity:%s'></div>" % (uri, "1" if activo else ".55"),
                    unsafe_allow_html=True,
                )
                if st.button(abrev(cod, r["equipo"]), key="eq_%d" % cod,
                             type="primary" if activo else "secondary"):
                    st.session_state["equipo"] = cod
                    st.rerun()
    return int(st.session_state["equipo"])


def tab_equipo(frames: Dict[str, pd.DataFrame]) -> None:
    cod = selector_equipo(frames)
    resumen = frames["resumen"].sort_values(["puntos", "gf"], ascending=False).reset_index(
        drop=True
    )
    if cod not in set(resumen["cod_equipo"]):
        st.info("Este equipo no tiene partidos en el rango de jornadas elegido.")
        return
    pos = int(resumen.index[resumen["cod_equipo"] == cod][0]) + 1
    r = resumen[resumen["cod_equipo"] == cod].iloc[0]

    g = frames["goles"]
    gf = g[g["cod_equipo_favor"] == cod]
    gc = g[g["cod_equipo_contra"] == cod]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod].sort_values("jornada")
    tj = frames["tarjetas"]
    mis_t = tj[(tj["cod_equipo"] == cod) & (tj["es_jugador"])]

    st.divider()
    cab = st.columns([1, 5])
    uri = ui.escudo_uri(slug(cod))
    cab[0].markdown(
        "<img src='%s' style='width:96px;height:96px;object-fit:contain'>" % uri,
        unsafe_allow_html=True,
    )
    cab[1].markdown(
        "<h1 style='margin-bottom:0'>%s</h1>"
        "<div style='color:%s;font-weight:700;font-size:1rem'>%dº · %d puntos · "
        "%d partidos · %d-%d-%d</div>"
        % (corto(cod, r["equipo"]), ui.TINTA_2, pos, int(r["puntos"]), int(r["pj"]),
           int(r["v"]), int(r["e"]), int(r["d"])),
        unsafe_allow_html=True,
    )

    k = st.columns(6)
    k[0].metric("Goles a favor · %.2f/partido" % r["gf_por_partido"], int(r["gf"]))
    k[1].metric("Goles en contra · %.2f/partido" % r["gc_por_partido"], int(r["gc"]))
    k[2].metric("GF 1ª / 2ª parte", "%d / %d" % (int(r["gf_p1"]), int(r["gf_p2"])))
    k[3].metric("GC 1ª / 2ª parte", "%d / %d" % (int(r["gc_p1"]), int(r["gc_p2"])))
    k[4].metric("Tarjetas · %.2f/partido" % r["tarjetas_por_partido"],
                int(r["amarillas"] + r["rojas"]))
    k[5].metric("Porterías a cero", int(r["porterias_cero"]))

    izq, der = st.columns([3, 2])
    with izq:
        st.markdown("### Cuándo marca y cuándo encaja")
        st.altair_chart(grafico_tramos(gf, gc, "Goles"), width="stretch")
        st.caption(
            "La FCF agrupa el descuento: 45+X aparece como minuto 44 y 90+X como 89."
        )
    with der:
        st.markdown("### Con qué marcador marca")
        total = max(len(gf), 1)
        barras = ""
        for estado, color in (("perdiendo", ui.SERIE_2), ("empate", ui.SERIE_4),
                              ("ganando", ui.SERIE_3)):
            n = int((gf["estado"] == estado).sum())
            barras += (
                "<div class='uev-fila'><div class='uev-nombre' style='width:92px'>%s</div>"
                "<div class='uev-pista'><div class='uev-barra' style='width:%.1f%%;"
                "background:%s'></div></div><div class='uev-valor'>%d</div></div>"
                % (estado.capitalize(), max(100.0 * n / total, 2), color, n)
            )
        st.markdown("<div class='uev-card'>" + barras + "</div>", unsafe_allow_html=True)

        casa = mis[mis["es_local"]]
        fuera = mis[~mis["es_local"]]
        st.markdown(
            "<div class='uev-card'>"
            + ui.dato("%d - %d" % (casa["gf_total"].sum(), casa["gc_total"].sum()),
                      "en casa (%d partidos)" % len(casa))
            + ui.dato("%d - %d" % (fuera["gf_total"].sum(), fuera["gc_total"].sum()),
                      "fuera (%d partidos)" % len(fuera))
            + "</div>",
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns(3)
    goleadores = metrics.goleadores(g, frames["personas"], cod).head(8)
    with col1:
        st.markdown("### Goleadores")
        if len(goleadores):
            st.markdown(
                "<div class='uev-card'>"
                + bloque_ranking_jugadores(goleadores, "goles", "jugador", None, None)
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Todavía sin goles.")
    with col2:
        st.markdown("### Más tarjetas")
        top_t = (
            mis_t.groupby("persona").size().rename("tarjetas").reset_index()
            .sort_values("tarjetas", ascending=False).head(8)
        )
        if len(top_t):
            st.markdown(
                "<div class='uev-card'>"
                + bloque_ranking_jugadores(top_t, "tarjetas", "persona", None, None)
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Sin tarjetas.")
    with col3:
        st.markdown("### Más minutos")
        mn = frames["minutos"]
        top_m = (
            mn[(mn["cod_equipo"] == cod) & (mn["jugo"])]
            .groupby("persona")["minutos"].sum().rename("minutos").reset_index()
            .sort_values("minutos", ascending=False).head(8)
        )
        st.markdown(
            "<div class='uev-card'>"
            + bloque_ranking_jugadores(top_m, "minutos", "persona", None, None)
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### Partidos y goles")
    izq, der = st.columns([2, 3])
    with izq:
        filas = ""
        for _, p in mis.iterrows():
            color = ui.SIGNO_COLOR[p["signo"]]
            rival_cod = int(p["cod_equipo_rival"])
            filas += (
                "<div class='uev-fila'>"
                "<div class='uev-pos'>J%d</div>"
                "<img class='uev-escudo' src='%s'>"
                "<div class='uev-nombre'>%s</div>"
                "<div class='uev-apoyo' style='width:50px'>%s</div>"
                "<div class='uev-valor'>%d-%d</div>"
                "<div style='width:26px;text-align:right;font-weight:800;color:%s'>%s</div>"
                "</div>"
                % (int(p["jornada"]), ui.escudo_uri(slug(rival_cod)),
                   corto(rival_cod, p["rival"]), "Casa" if p["es_local"] else "Fuera",
                   int(p["gf_total"]), int(p["gc_total"]), color, p["signo"])
            )
        st.markdown("<div class='uev-card'>" + filas + "</div>", unsafe_allow_html=True)
    with der:
        detalle = gf.merge(
            frames["personas"].rename(columns={"nombre": "jugador"}),
            on="cod_persona", how="left",
        )
        detalle["dónde"] = detalle["favor_en_casa"].map({True: "Casa", False: "Fuera"})
        st.dataframe(
            detalle.sort_values(["jornada", "minuto"])[
                ["jornada", "equipo_contra", "dónde", "jugador", "minuto", "tipo", "estado"]
            ],
            hide_index=True, width="stretch", height=330,
            column_config={"jornada": "J", "equipo_contra": "Rival", "minuto": "Min",
                           "tipo": "Tipo", "estado": "Marcador al marcar"},
        )

    with st.expander("Plantilla completa: minutos, titularidades y tarjetas"):
        mn = frames["minutos"]
        plant = (
            mn[(mn["cod_equipo"] == cod) & (mn["jugo"])]
            .groupby("persona")
            .agg(partidos=("cod_acta", "nunique"), titular=("titular", "sum"),
                 minutos=("minutos", "sum"))
            .reset_index()
        )
        tarj = mis_t.groupby("persona").size().rename("tarjetas").reset_index()
        gol_j = metrics.goleadores(g, frames["personas"], cod)[["jugador", "goles"]].rename(
            columns={"jugador": "persona"}
        )
        plant = plant.merge(tarj, on="persona", how="left").merge(
            gol_j, on="persona", how="left"
        )
        plant[["tarjetas", "goles"]] = plant[["tarjetas", "goles"]].fillna(0).astype(int)
        st.dataframe(
            plant.sort_values("minutos", ascending=False), hide_index=True,
            width="stretch",
            column_config={"persona": "Jugador", "partidos": "PJ", "titular": "Titular",
                           "minutos": "Minutos", "tarjetas": "Tarjetas", "goles": "Goles"},
        )


def tab_jugadores(frames: Dict[str, pd.DataFrame], foco: int) -> None:
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
        tj.groupby(["cod_persona", "persona", "cod_equipo"]).size().rename("tarjetas")
        .reset_index().sort_values("tarjetas", ascending=False).head(12)
    )
    mn = frames["minutos"]
    minu = (
        mn[mn["jugo"]].groupby(["cod_persona", "persona", "cod_equipo"])["minutos"]
        .sum().reset_index().sort_values("minutos", ascending=False).head(12)
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Máximos goleadores")
        st.markdown(
            "<div class='uev-card'>"
            + bloque_ranking_jugadores(gol, "goles", "jugador", "cod_equipo_favor", foco)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Sin goles en propia: esos cuentan para el rival, no para el autor.")
    with c2:
        st.markdown("### Más tarjetas")
        st.markdown(
            "<div class='uev-card'>"
            + bloque_ranking_jugadores(tar, "tarjetas", "persona", "cod_equipo", foco)
            + "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown("### Más minutos")
        st.markdown(
            "<div class='uev-card'>"
            + bloque_ranking_jugadores(minu, "minutos", "persona", "cod_equipo", foco)
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Tabla completa de goleadores"):
        completo = metrics.goleadores(g, personas)
        st.dataframe(
            completo[["jugador", "equipo", "goles", "penales", "p1", "p2"]],
            hide_index=True, width="stretch",
            column_config={"jugador": "Jugador", "equipo": "Equipo", "goles": "Goles",
                           "penales": "De penal", "p1": "1ª parte", "p2": "2ª parte"},
        )


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.markdown(ui.CSS, unsafe_allow_html=True)

    try:
        jornadas_max = int(_raw()["partidos"].query("jugado")["jornada"].max())
    except Exception as exc:
        st.error("No se han podido cargar los datos: %s" % exc)
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
            "datos oficiales FCF</div></div></div>"
            % (ui.escudo_uri("valls"), ui.TINTA_MUDA),
            unsafe_allow_html=True,
        )
    with cab[1]:
        rango = st.slider("Jornadas", 1, jornadas_max, (1, jornadas_max))
    with cab[2]:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        with st.popover("Leyenda"):
            st.markdown(
                "**Fiabilidad de cada dato**\n\n"
                "- %s con suficientes eventos detrás\n"
                "- %s el orden puede cambiar con un partido\n"
                "- %s no se ordena, solo se enseña el total\n\n"
                "**Tres avisos sobre la fuente**\n\n"
                "- El descuento va agrupado: 45+X sale como minuto 44 y 90+X como 89.\n"
                "- Los equipos han jugado entre 3 y 5 partidos, así que los rankings "
                "de volumen van por partido.\n"
                "- Las tarjetas del banquillo se cuentan aparte y no entran en rankings."
                % (ui.chip("OK"), ui.chip("ORIENTATIVO"), ui.chip("DESCARTADO")),
                unsafe_allow_html=True,
            )

    frames = cargar(tuple(rango))
    if frames["resumen"].empty:
        st.warning("No hay partidos jugados en ese rango de jornadas.")
        st.stop()
        return

    foco = int(st.session_state.get("equipo", VALLS))
    t1, t2, t3, t4 = st.tabs(["Clasificación", "Rankings", "Equipo", "Jugadores"])
    with t1:
        tab_clasificacion(frames, foco)
    with t2:
        tab_rankings(frames, foco)
    with t3:
        tab_equipo(frames)
    with t4:
        tab_jugadores(frames, foco)


if __name__ == "__main__":
    main()
