"""Phase 1: validate every insight before it goes into the app.

Prints how many events back each league ranking, the grade it earns, a
cross-check of the computed table against the official FCF standings, and the
per-team sample sizes. Run it again after each jornada is loaded.

    python validate_insights.py
"""

from __future__ import annotations

import sys

import pandas as pd

from uevalls import data, insights, metrics

try:  # Windows consoles default to cp1252 and choke on accents
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 60)


def main() -> int:
    raw = data.load_all()
    frames = metrics.build(raw)
    resumen = frames["resumen"]

    print("=" * 100)
    print("COBERTURA DE DATOS")
    print("=" * 100)
    print(
        "partidos jugados: %d | jornadas: %d | goles: %d | tarjetas jugador: %d | "
        "tarjetas banquillo: %d | sustituciones: %d | equipos: %d"
        % (
            len(frames["partidos"]),
            int(frames["partidos"]["jornada"].max()),
            len(frames["goles"]),
            int(frames["tarjetas"]["es_jugador"].sum()),
            int((~frames["tarjetas"]["es_jugador"]).sum()),
            len(frames["cambios"]),
            len(frames["equipos"]),
        )
    )
    print(
        "partidos por equipo: min %d, max %d -> cualquier ranking por totales favorece "
        "al que mas ha jugado" % (resumen["pj"].min(), resumen["pj"].max())
    )

    print()
    print("=" * 100)
    print("VALIDACION DE INSIGHTS DE LIGA")
    print("=" * 100)
    v = insights.validar(frames)
    print(v[["insight", "poblacion", "n", "veredicto"]].to_string(index=False))

    print()
    print("Umbrales: OK >= %d eventos | ORIENTATIVO >= %d | por debajo DESCARTADO"
          % (insights.UMBRAL_OK, insights.UMBRAL_ORIENTATIVO))
    for veredicto in ("OK", "ORIENTATIVO", "DESCARTADO"):
        ids = list(v[v["veredicto"] == veredicto]["id"])
        print("%-12s %d: %s" % (veredicto, len(ids), ", ".join(ids) or "-"))

    print()
    print("=" * 100)
    print("CONTRASTE CON LA CLASIFICACION OFICIAL FCF")
    print("=" * 100)
    oficial = frames["clasificacion_fcf"][
        ["cod_equipo", "jugados", "puntos", "ganados", "empatados", "perdidos",
         "goles_favor", "goles_contra"]
    ].rename(columns=lambda c: c if c == "cod_equipo" else "of_" + c)
    chk = resumen.merge(oficial, on="cod_equipo", how="inner")

    cols = {
        "pj": "of_jugados",
        "puntos": "of_puntos",
        "v": "of_ganados",
        "e": "of_empatados",
        "d": "of_perdidos",
        "gf": "of_goles_favor",
        "gc": "of_goles_contra",
    }
    ok = True
    for calc, ofi in cols.items():
        difs = chk[chk[calc].astype(float) != chk[ofi].astype(float)]
        print("%-7s vs %-16s diferencias: %d" % (calc, ofi, len(difs)))
        if len(difs):
            ok = False
            print(difs[["equipo", calc, ofi]].to_string(index=False))
    print("equipos contrastados: %d de %d" % (len(chk), len(resumen)))
    print("RESULTADO:", "cuadra con la fuente oficial" if ok else "REVISAR")

    print()
    print("=" * 100)
    print("TAMANO DE MUESTRA POR EQUIPO")
    print("=" * 100)
    muestra = resumen[["equipo", "pj", "gf", "gc", "amarillas", "rojas", "cambios",
                       "jugadores_usados"]].copy()
    muestra["gf_grado"] = muestra["gf"].apply(
        lambda n: insights.grado(n, insights.UMBRAL_EQUIPO_OK, insights.UMBRAL_EQUIPO_ORIENTATIVO)
    )
    muestra["tarjetas_grado"] = muestra["amarillas"].apply(
        lambda n: insights.grado(n, insights.UMBRAL_EQUIPO_OK, insights.UMBRAL_EQUIPO_ORIENTATIVO)
    )
    print(muestra.sort_values("gf", ascending=False).to_string(index=False))

    print()
    print("=" * 100)
    print("EJEMPLO DE INFORME DE EQUIPO (el mas goleador)")
    print("=" * 100)
    cod = int(resumen.sort_values("gf", ascending=False).iloc[0]["cod_equipo"])
    nombre = frames["equipos"].set_index("cod_equipo").loc[cod, "equipo"]
    print(nombre)
    for h in insights.informe_equipo(frames, cod):
        print("  [%-11s n=%3d] %-32s %s" % (h.veredicto, h.n, h.titulo, h.texto))
    dep = insights.dependencia_goleadora(frames, raw["personas"], cod)
    print("  [%-11s n=%3d] %-32s %s" % (dep.veredicto, dep.n, dep.titulo, dep.texto))

    print()
    print("=" * 100)
    print("DISTRIBUCION DE GOLES POR TRAMO (liga)")
    print("=" * 100)
    print(metrics.distribucion_tramos(frames["goles"]).to_string(index=False))
    print(
        "Aviso: la FCF agrupa el descuento. 45+X se publica como minuto 44 y 90+X como "
        "minuto 89, asi que los tramos 31-45 y 76-90 estan inflados."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
