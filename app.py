"""UE Valls - Analitica Lliga Elit Grup 1.

Streamlit app over the FCF dataset stored in the Supabase project UEValls.
Run locally with:

    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import altair as alt
import pandas as pd
import streamlit as st

from uevalls import data, insights, metrics

ROJO = "#E03A24"
GRIS = "#7A8694"
AMBAR = "#E0A52E"
VERDE = "#3FA66B"

COLOR_VEREDICTO = {"OK": VERDE, "ORIENTATIVO": AMBAR, "DESCARTADO": GRIS}
ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="UE Valls | Analítica Lliga Elit",
    page_icon=str(ASSETS / "escudos" / "valls.png")
    if (ASSETS / "escudos" / "valls.png").exists()
    else "⚽",
    layout="wide",
)


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=1800, show_spinner="Cargando datos de la FCF…")
def cargar() -> Dict[str, pd.DataFrame]:
    return metrics.build(data.load_all())


@st.cache_data
def catalogo_equipos() -> dict:
    ruta = ASSETS / "equipos.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {}


def escudo(cod_equipo: int) -> Path | None:
    info = catalogo_equipos().get(str(cod_equipo))
    if not info or not info.get("slug"):
        return None
    ruta = ASSETS / "escudos" / (info["slug"] + ".png")
    return ruta if ruta.exists() else None


def nombre_corto(cod_equipo: int, por_defecto: str) -> str:
    info = catalogo_equipos().get(str(cod_equipo))
    return info["nombre_corto"] if info and info.get("nombre_corto") else por_defecto


def badge(veredicto: str) -> str:
    color = COLOR_VEREDICTO.get(veredicto, GRIS)
    return (
        "<span style='background:%s22;color:%s;border:1px solid %s66;"
        "border-radius:4px;padding:1px 7px;font-size:11px;font-weight:600;"
        "letter-spacing:.3px'>%s</span>" % (color, color, color, veredicto)
    )


def nota_muestra(veredicto: str, n: int) -> str:
    if veredicto == "OK":
        return "Base de %d eventos." % n
    if veredicto == "ORIENTATIVO":
        return "Solo %d eventos: tendencia frágil, un partido puede cambiarla." % n
    return "Solo %d eventos: dato suelto, no sirve para afirmar una tendencia." % n


# --------------------------------------------------------------------------- #
# charts
# --------------------------------------------------------------------------- #
def grafico_tramos(gf: pd.DataFrame, gc: pd.DataFrame) -> alt.Chart:
    a = metrics.distribucion_tramos(gf).assign(tipo="A favor")
    b = metrics.distribucion_tramos(gc).assign(tipo="En contra")
    df = pd.concat([a, b], ignore_index=True)
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("tramo:N", sort=metrics.TRAMO_LABELS, title="Tramo de minutos"),
            y=alt.Y("n:Q", title="Goles"),
            xOffset="tipo:N",
            color=alt.Color(
                "tipo:N",
                scale=alt.Scale(domain=["A favor", "En contra"], range=[ROJO, GRIS]),
                title=None,
            ),
            tooltip=["tramo", "tipo", "n"],
        )
        .properties(height=260)
    )


def grafico_tramos_simple(eventos: pd.DataFrame, color: str, titulo: str) -> alt.Chart:
    df = metrics.distribucion_tramos(eventos)
    return (
        alt.Chart(df)
        .mark_bar(color=color)
        .encode(
            x=alt.X("tramo:N", sort=metrics.TRAMO_LABELS, title="Tramo de minutos"),
            y=alt.Y("n:Q", title=titulo),
            tooltip=["tramo", "n"],
        )
        .properties(height=260)
    )


def grafico_estado(gf: pd.DataFrame) -> alt.Chart:
    orden = ["perdiendo", "empate", "ganando"]
    conteo = gf["estado"].value_counts().reindex(orden, fill_value=0).reset_index()
    conteo.columns = ["estado", "n"]
    return (
        alt.Chart(conteo)
        .mark_bar(color=ROJO)
        .encode(
            x=alt.X("estado:N", sort=orden, title="Marcador antes del gol"),
            y=alt.Y("n:Q", title="Goles"),
            tooltip=["estado", "n"],
        )
        .properties(height=260)
    )


def grafico_tarjetas(tj: pd.DataFrame) -> alt.Chart:
    df = metrics.distribucion_tramos(tj)
    return (
        alt.Chart(df)
        .mark_bar(color=AMBAR)
        .encode(
            x=alt.X("tramo:N", sort=metrics.TRAMO_LABELS, title="Tramo de minutos"),
            y=alt.Y("n:Q", title="Tarjetas"),
            tooltip=["tramo", "n"],
        )
        .properties(height=240)
    )


def grafico_evolucion(ev: pd.DataFrame) -> alt.Chart:
    base = alt.Chart(ev).encode(x=alt.X("jornada:O", title="Jornada"))
    linea = base.mark_line(color=ROJO, point=True).encode(
        y=alt.Y("puntos_acum:Q", title="Puntos acumulados"),
        tooltip=["jornada", "rival", "donde", "marcador", "puntos", "puntos_acum"],
    )
    return linea.properties(height=260)


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def pagina_liga(frames: Dict[str, pd.DataFrame]) -> None:
    resumen = frames["resumen"]
    st.subheader("Clasificación")

    tabla = resumen[
        ["equipo", "pj", "v", "e", "d", "puntos", "gf", "gc", "gf_p1", "gf_p2",
         "gc_p1", "gc_p2", "gf_casa", "gf_fuera", "gc_casa", "gc_fuera",
         "amarillas", "rojas"]
    ].copy()
    tabla["dif"] = tabla["gf"] - tabla["gc"]
    tabla = tabla[
        ["equipo", "pj", "v", "e", "d", "puntos", "gf", "gc", "dif", "gf_p1", "gf_p2",
         "gc_p1", "gc_p2", "gf_casa", "gf_fuera", "gc_casa", "gc_fuera",
         "amarillas", "rojas"]
    ]
    st.dataframe(
        tabla,
        hide_index=True,
        use_container_width=True,
        column_config={
            "equipo": "Equipo", "pj": "PJ", "v": "G", "e": "E", "d": "P",
            "puntos": "Pts", "gf": "GF", "gc": "GC", "dif": "Dif",
            "gf_p1": "GF 1ª", "gf_p2": "GF 2ª", "gc_p1": "GC 1ª", "gc_p2": "GC 2ª",
            "gf_casa": "GF casa", "gf_fuera": "GF fuera",
            "gc_casa": "GC casa", "gc_fuera": "GC fuera",
            "amarillas": "Amar.", "rojas": "Rojas",
        },
    )
    st.caption(
        "Contrastada con la clasificación oficial de la FCF: coinciden PJ, puntos, "
        "G/E/P, GF y GC en los 16 equipos. GF/GC por partes y por localía salen de los "
        "eventos del acta."
    )

    st.divider()
    st.subheader("Rankings")
    st.caption(
        "Los equipos no han jugado los mismos partidos (de %d a %d), así que los "
        "rankings de volumen van normalizados por partido. Cada uno lleva la etiqueta "
        "de fiabilidad que le da su número de eventos."
        % (resumen["pj"].min(), resumen["pj"].max())
    )

    publicables = insights.rankings_publicables(frames)
    val = insights.validar(frames).set_index("id")
    top_n = st.slider("Posiciones por ranking", 3, 8, 3)

    columnas = st.columns(2)
    for i, r in enumerate(publicables):
        fila = val.loc[r.id]
        with columnas[i % 2].container(border=True):
            st.markdown("**%s** &nbsp; %s" % (r.titulo, badge(fila["veredicto"])),
                        unsafe_allow_html=True)
            t = r.tabla(resumen, top_n)
            cfg = {"equipo": "Equipo", "pj": "PJ", r.columna: r.unidad}
            if r.columna_apoyo and r.columna_apoyo in t.columns:
                cfg[r.columna_apoyo] = "total"
            st.dataframe(t, hide_index=True, use_container_width=True, column_config=cfg)
            st.caption(nota_muestra(fila["veredicto"], int(fila["n"])) +
                       (" " + r.nota if r.nota else ""))

    descartados = insights.rankings_descartados(frames)
    if descartados:
        with st.expander("Preguntas que todavía no se pueden rankear (%d)" % len(descartados)):
            st.caption(
                "Con 5 jornadas estos eventos son demasiado escasos para ordenar equipos. "
                "Se muestran los totales de liga para que se vean, sin ranking."
            )
            for r in descartados:
                fila = val.loc[r.id]
                st.markdown(
                    "- **%s** — %d %s en toda la liga. %s"
                    % (r.titulo, int(fila["n"]), r.poblacion, nota_muestra("DESCARTADO",
                                                                           int(fila["n"])))
                )

    st.divider()
    izq, der = st.columns(2)
    with izq:
        st.subheader("Cuándo se marca en la liga")
        st.altair_chart(grafico_tramos_simple(frames["goles"], ROJO, "Goles"),
                        use_container_width=True)
    with der:
        st.subheader("Cuándo se saca tarjeta")
        tj = frames["tarjetas"]
        st.altair_chart(grafico_tarjetas(tj[tj["es_jugador"]]), use_container_width=True)
        p1 = int(((tj["es_jugador"]) & (tj["parte"] == 1)).sum())
        p2 = int(((tj["es_jugador"]) & (tj["parte"] == 2)).sum())
        st.caption(
            "%d tarjetas en la segunda parte frente a %d en la primera: %.1f veces más."
            % (p2, p1, p2 / p1 if p1 else 0)
        )


def pagina_equipo(frames: Dict[str, pd.DataFrame]) -> None:
    equipos = frames["equipos"].sort_values("equipo")
    opciones = {
        nombre_corto(int(r["cod_equipo"]), r["equipo"]): int(r["cod_equipo"])
        for _, r in equipos.iterrows()
    }
    por_defecto = list(opciones).index("U.E. Valls") if "U.E. Valls" in opciones else 0
    elegido = st.sidebar.selectbox("Equipo", list(opciones), index=por_defecto)
    cod = opciones[elegido]

    resumen = frames["resumen"]
    fila = resumen[resumen["cod_equipo"] == cod].iloc[0]
    g = frames["goles"]
    gf = g[g["cod_equipo_favor"] == cod]
    gc = g[g["cod_equipo_contra"] == cod]
    ep = frames["equipo_partido"]
    mis = ep[ep["cod_equipo"] == cod]

    cabecera = st.columns([1, 6])
    img = escudo(cod)
    if img:
        cabecera[0].image(str(img), width=90)
    cabecera[1].title(elegido)
    cabecera[1].caption(
        "%d partidos · %d puntos · %d-%d-%d · %d goles a favor · %d en contra"
        % (fila["pj"], fila["puntos"], fila["v"], fila["e"], fila["d"],
           fila["gf"], fila["gc"])
    )

    k = st.columns(6)
    k[0].metric("Goles/partido", "%.2f" % fila["gf_por_partido"])
    k[1].metric("Encajados/partido", "%.2f" % fila["gc_por_partido"])
    k[2].metric("% goles 2ª parte", "—" if pd.isna(fila["pct_gf_p2"]) else "%.0f%%" % fila["pct_gf_p2"])
    k[3].metric("Porterías a cero", int(fila["porterias_cero"]))
    k[4].metric("Tarjetas/partido", "%.2f" % fila["tarjetas_por_partido"])
    k[5].metric("Minuto medio de cambio", "%.1f" % fila["min_cambio_medio"])

    st.divider()
    st.subheader("Informe")
    hallazgos = insights.informe_equipo(frames, cod)
    hallazgos.append(insights.dependencia_goleadora(frames, frames["personas"], cod))
    cols = st.columns(2)
    for i, h in enumerate(hallazgos):
        with cols[i % 2].container(border=True):
            st.markdown("**%s** &nbsp; %s" % (h.titulo, badge(h.veredicto)),
                        unsafe_allow_html=True)
            st.write(h.texto)
            st.caption(nota_muestra(h.veredicto, h.n))

    st.divider()
    izq, der = st.columns(2)
    with izq:
        st.subheader("Cuándo marca y cuándo encaja")
        st.altair_chart(grafico_tramos(gf, gc), use_container_width=True)
        st.caption(
            "La FCF agrupa el descuento: 45+X se publica como minuto 44 y 90+X como "
            "minuto 89, así que los tramos 31-45 y 76-90 salen inflados."
        )
    with der:
        st.subheader("Con qué marcador llegan sus goles")
        st.altair_chart(grafico_estado(gf), use_container_width=True)
        st.caption(
            "Marcador inmediatamente antes de cada gol, reconstruido desde el orden "
            "de los goles del acta."
        )

    st.subheader("Evolución por jornada")
    st.altair_chart(grafico_evolucion(metrics.evolucion(ep, cod)), use_container_width=True)

    st.divider()
    st.subheader("Goleadores")
    gol = metrics.goleadores(frames["goles"], frames["personas"], cod)
    if len(gol):
        st.dataframe(
            gol[["jugador", "goles", "penales", "p1", "p2", "primer_minuto",
                 "ultimo_minuto"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "jugador": "Jugador", "goles": "Goles", "penales": "De penal",
                "p1": "1ª parte", "p2": "2ª parte",
                "primer_minuto": "Min. más temprano", "ultimo_minuto": "Min. más tardío",
            },
        )
        st.caption("Los goles en propia puerta no se atribuyen a ningún goleador del equipo.")
    else:
        st.info("El equipo no ha marcado todavía.")

    st.subheader("Lista de goles")
    detalle = gf.merge(frames["personas"].rename(columns={"nombre": "jugador"}),
                       on="cod_persona", how="left")
    detalle["dónde"] = detalle["favor_en_casa"].map({True: "Casa", False: "Fuera"})
    detalle["marcador antes"] = (
        detalle["marcador_local_antes"].astype(str) + "-"
        + detalle["marcador_visitante_antes"].astype(str)
    )
    st.dataframe(
        detalle.sort_values(["jornada", "minuto"])[
            ["jornada", "equipo_contra", "dónde", "jugador", "minuto", "parte", "tipo",
             "estado", "marcador antes"]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "jornada": "J", "equipo_contra": "Rival", "minuto": "Min", "parte": "Parte",
            "tipo": "Tipo", "estado": "Marcador al marcar",
        },
    )

    st.divider()
    izq, der = st.columns(2)
    with izq:
        st.subheader("Tarjetas")
        tj = frames["tarjetas"]
        mias = tj[(tj["cod_equipo"] == cod) & (tj["es_jugador"])]
        if len(mias):
            st.altair_chart(grafico_tarjetas(mias), use_container_width=True)
            top = (
                mias.groupby("persona")
                .agg(tarjetas=("id", "count"),
                     rojas=("color", lambda s: int((s == "roja").sum())))
                .reset_index()
                .sort_values("tarjetas", ascending=False)
                .head(10)
            )
            st.dataframe(top, hide_index=True, use_container_width=True,
                         column_config={"persona": "Jugador", "tarjetas": "Tarjetas",
                                        "rojas": "Rojas"})
        else:
            st.info("Sin tarjetas a jugadores.")
        banquillo = tj[(tj["cod_equipo"] == cod) & (~tj["es_jugador"])]
        st.caption("Tarjetas al banquillo (no entran en los rankings): %d" % len(banquillo))
    with der:
        st.subheader("Minutos jugados")
        mn = frames["minutos"]
        mios = mn[(mn["cod_equipo"] == cod) & (mn["jugo"])]
        tabla = (
            mios.groupby("persona")
            .agg(partidos=("cod_acta", "nunique"),
                 titular=("titular", "sum"),
                 minutos=("minutos", "sum"))
            .reset_index()
            .sort_values("minutos", ascending=False)
        )
        st.dataframe(tabla, hide_index=True, use_container_width=True, height=420,
                     column_config={"persona": "Jugador", "partidos": "PJ",
                                    "titular": "Titular", "minutos": "Minutos"})
        st.caption(
            "Minutos estimados: titular desde el 0, suplente desde su minuto de entrada, "
            "hasta la sustitución, la roja o el 90. El descuento no se cuenta."
        )

    st.divider()
    st.subheader("Partidos")
    st.dataframe(
        mis.sort_values("jornada")[
            ["jornada", "fecha", "rival", "es_local", "gf_total", "gc_total", "signo",
             "puntos"]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "jornada": "J", "fecha": "Fecha", "rival": "Rival",
            "es_local": st.column_config.CheckboxColumn("En casa"),
            "gf_total": "GF", "gc_total": "GC", "signo": "Resultado", "puntos": "Pts",
        },
    )


def pagina_jugadores(frames: Dict[str, pd.DataFrame]) -> None:
    st.subheader("Goleadores de la liga")
    gol = metrics.goleadores(frames["goles"], frames["personas"])
    st.dataframe(
        gol[["jugador", "equipo", "goles", "penales", "p1", "p2"]].head(40),
        hide_index=True, use_container_width=True,
        column_config={"jugador": "Jugador", "equipo": "Equipo", "goles": "Goles",
                       "penales": "De penal", "p1": "1ª parte", "p2": "2ª parte"},
    )
    st.caption("Sin goles en propia puerta: esos cuentan para el equipo rival, no para el autor.")

    izq, der = st.columns(2)
    with izq:
        st.subheader("Más tarjetas")
        tj = frames["tarjetas"]
        tj = tj[tj["es_jugador"]]
        t = (
            tj.groupby(["persona", "equipo"])
            .agg(tarjetas=("id", "count"),
                 amarillas=("color", lambda s: int((s == "amarilla").sum())),
                 rojas=("color", lambda s: int((s == "roja").sum())))
            .reset_index()
            .sort_values(["tarjetas", "rojas"], ascending=False)
            .head(25)
        )
        st.dataframe(t, hide_index=True, use_container_width=True,
                     column_config={"persona": "Jugador", "equipo": "Equipo",
                                    "tarjetas": "Total", "amarillas": "Amarillas",
                                    "rojas": "Rojas"})
    with der:
        st.subheader("Más minutos")
        mn = frames["minutos"]
        m = (
            mn[mn["jugo"]]
            .groupby(["persona", "equipo"])
            .agg(partidos=("cod_acta", "nunique"), minutos=("minutos", "sum"))
            .reset_index()
            .sort_values("minutos", ascending=False)
            .head(25)
        )
        st.dataframe(m, hide_index=True, use_container_width=True,
                     column_config={"persona": "Jugador", "equipo": "Equipo",
                                    "partidos": "PJ", "minutos": "Minutos"})


def pagina_metodologia(frames: Dict[str, pd.DataFrame]) -> None:
    st.subheader("Qué datos hay")
    p = frames["partidos"]
    tj = frames["tarjetas"]
    c = st.columns(5)
    c[0].metric("Partidos jugados", len(p))
    c[1].metric("Jornadas", int(p["jornada"].max()))
    c[2].metric("Goles", len(frames["goles"]))
    c[3].metric("Tarjetas a jugadores", int(tj["es_jugador"].sum()))
    c[4].metric("Sustituciones", len(frames["cambios"]))

    st.subheader("Validación de los insights")
    st.caption(
        "Cada ranking se califica por el número de eventos que lo sostienen, no por "
        "lo bien que suena. Umbrales: OK a partir de %d eventos, ORIENTATIVO a partir "
        "de %d, por debajo DESCARTADO. La calificación se recalcula con cada carga, "
        "así que los insights descartados hoy se aprobarán solos cuando haya jornadas."
        % (insights.UMBRAL_OK, insights.UMBRAL_ORIENTATIVO)
    )
    v = insights.validar(frames)
    st.dataframe(
        v[["insight", "poblacion", "n", "veredicto", "nota"]],
        hide_index=True, use_container_width=True,
        column_config={"insight": "Insight", "poblacion": "Eventos que lo sostienen",
                       "n": "n", "veredicto": "Veredicto", "nota": "Nota"},
    )

    st.subheader("Límites conocidos")
    st.markdown(
        """
- **Descuento agrupado.** La FCF publica 45+X como minuto 44 y 90+X como minuto 89.
  Los tramos 31-45 y 76-90 salen inflados y ningún gol aparece por encima del 90.
- **Partidos desiguales.** Van de 3 a 5 por equipo, así que los totales no son
  comparables entre equipos. Los rankings usan medias por partido.
- **Minutos estimados.** Se calculan con titularidad, cambios y rojas. Sin descuento
  y sin paradas, así que el techo es 90.
- **Tarjetas del banquillo.** 18 de las tarjetas son de cuerpo técnico. Se separan de
  las de jugadores y no entran en los rankings.
- **Doble amarilla.** El campo `segunda_amarilla` llega siempre vacío desde la FCF.
  La expulsión por doble amarilla se identifica por el artículo de la sanción.
- **Goles en propia.** Suman al equipo beneficiado y no se atribuyen a ningún
  goleador de ese equipo.
        """
    )

    st.subheader("Fuente")
    st.markdown(
        """
Datos de la Federació Catalana de Futbol, Lliga Elit Grup 1, temporada 2026-27
(`temporadaId=22`, `competicioId=58161860`, `grupId=58161861`), recogidos de las actas
oficiales. Almacenados en el proyecto Supabase **UEValls** con RLS de solo lectura.
La clasificación calculada aquí cuadra con la oficial de la FCF en los 16 equipos.
        """
    )


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    logo = ASSETS / "escudos" / "valls.png"
    if logo.exists():
        st.sidebar.image(str(logo), width=70)
    st.sidebar.markdown("### Analítica Lliga Elit")
    pagina = st.sidebar.radio(
        "Sección", ["Liga", "Equipo", "Jugadores", "Metodología"], label_visibility="collapsed"
    )

    try:
        frames = cargar()
    except Exception as exc:  # pragma: no cover - surfaced in the UI
        st.error("No se han podido cargar los datos: %s" % exc)
        st.stop()
        return

    if st.sidebar.button("Recargar datos", use_container_width=True):
        cargar.clear()
        st.rerun()
    st.sidebar.caption(
        "Última jornada cargada: %d" % int(frames["partidos"]["jornada"].max())
    )

    if pagina == "Liga":
        st.title("Lliga Elit · Grup 1")
        pagina_liga(frames)
    elif pagina == "Equipo":
        pagina_equipo(frames)
    elif pagina == "Jugadores":
        st.title("Jugadores")
        pagina_jugadores(frames)
    else:
        st.title("Metodología")
        pagina_metodologia(frames)


if __name__ == "__main__":
    main()
