# UE Valls · Analítica Lliga Elit Grup 1

App en Streamlit sobre los datos oficiales de la FCF (Lliga Elit, Grup 1, temporada
2026-27) guardados en el proyecto Supabase **UEValls**.

Cuatro pestañas:

- **Clasificación** — tabla visual con escudo, diferencia de goles, racha de los últimos
  cinco partidos y puntos; debajo, cuándo y dónde se marca en la liga.
- **Rankings** — tops por tema (Goles, Defensa, Tarjetas, Banquillo) en barras, con el
  equipo seleccionado resaltado en rojo y la etiqueta de fiabilidad en cada tarjeta.
- **Equipo** — rejilla con los 16 escudos para elegir equipo y, debajo, su informe:
  KPIs, cuándo marca y encaja, con qué marcador marca, casa/fuera, goleadores, tarjetas,
  minutos, partidos y lista completa de goles.
- **Jugadores** — goleadores, tarjetas y minutos de toda la liga.

Un slider de jornadas en la cabecera recalcula **toda** la app sobre el rango elegido, y
el botón *Leyenda* explica las etiquetas de fiabilidad y los tres avisos sobre la fuente.

## Cómo se validan los insights

Con 5 jornadas disputadas hay 34 partidos, 90 goles y 186 tarjetas a jugadores. A ese
volumen algunas preguntas se pueden responder y otras no, así que **cada insight declara
el número de eventos que lo sostiene y se califica antes de llegar a la app**:

| Veredicto | Significado |
|---|---|
| `OK` | hay eventos suficientes para describir una tendencia |
| `ORIENTATIVO` | real pero frágil: un partido puede reordenar el ranking |
| `DESCARTADO` | demasiados pocos eventos para ordenar equipos; se muestra como dato suelto |

Los umbrales están en `uevalls/insights.py` (`UMBRAL_OK`, `UMBRAL_ORIENTATIVO`). La nota
se recalcula en cada carga, así que los insights descartados hoy se aprueban solos cuando
entren más jornadas.

Estado con los datos actuales:

- **OK (8):** jugadores distintos utilizados · minuto medio de cambio · tarjetas por
  partido · tarjetas en la segunda parte · goles por partido · goles encajados por
  partido · % de goles en la segunda parte · porterías a cero.
- **ORIENTATIVO (4):** goles como local · goles como visitante · goles desde el minuto 75
  · goles marcados yendo por detrás.
- **DESCARTADO (4):** goles en los primeros 20 minutos (14 en toda la liga) · goles de
  respuesta en ≤10 min (11) · goles encajados justo después de marcar (11) · goles de
  penal (4).

Dos decisiones que afectan a todos los rankings:

1. **Los equipos no han jugado lo mismo** (de 3 a 5 partidos), así que los rankings de
   volumen van normalizados por partido, con el total al lado.
2. **Las tarjetas del cuerpo técnico se separan** de las de jugadores (18 de 204) y no
   entran en ningún ranking.

Para ver el informe de validación en consola:

```bash
python validate_insights.py
```

Incluye un contraste contra la clasificación oficial de la FCF: PJ, puntos, G/E/P, GF y
GC coinciden en los 16 equipos.

## Límites conocidos

- **Descuento agrupado.** La FCF publica 45+X como minuto 44 y 90+X como minuto 89, así
  que los tramos 31-45 y 76-90 salen inflados y ningún gol aparece por encima del 90.
- **Minutos estimados.** Se calculan con titularidad, cambios y rojas, sin descuento, con
  techo de 90.
- **Doble amarilla.** El campo `segunda_amarilla` llega siempre vacío desde la FCF; la
  expulsión por doble amarilla se identifica por el artículo de la sanción.
- **Goles en propia.** Suman al equipo beneficiado y no se atribuyen a ningún goleador de
  ese equipo.

## Estructura

```
app.py                  interfaz Streamlit
uevalls/data.py         lectura de Supabase vía PostgREST (paginada)
uevalls/metrics.py      frames derivados: goles con contexto, equipo-partido, minutos, resumen
uevalls/insights.py     catálogo de insights, umbrales y generación de informes
validate_insights.py    informe de validación en consola
tools/build_assets.py   copia los escudos y construye assets/equipos.json
assets/                 escudos y mapa de equipos
pipeline/scrape.py      descarga las actas de la FCF a data/*.json
pipeline/load.py        carga esos JSON en Supabase (upsert, reejecutable)
pipeline/README_bbdd.md documentación del modelo de datos y de las vistas SQL
```

El marcador antes de cada gol se reconstruye ordenando los goles del acta, lo que permite
responder "¿marca yendo por detrás?" y "¿reacciona tras encajar?".

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Credenciales

La app lee con una clave **publishable** de Supabase y las tablas tienen RLS de solo
lectura, así que la clave no puede escribir. El orden de resolución es: secrets de
Streamlit → variables de entorno `SB_URL` / `SB_KEY` → valores por defecto en
`uevalls/data.py`.

Para Streamlit Cloud, copia `.streamlit/secrets.toml.example` en *App settings → Secrets*.

## Desplegar en Streamlit Community Cloud

1. Sube esta carpeta a un repositorio de GitHub.
2. En [share.streamlit.io](https://share.streamlit.io) elige *New app*, selecciona el
   repositorio y pon `app.py` como *Main file path*.
3. Pega el contenido de `.streamlit/secrets.toml.example` en *Secrets*.
4. Deploy.

## Actualizar tras cada jornada

Los datos vienen de la base **UEValls**. Cuando se carguen jornadas nuevas, la app las
coge sola (caché de 30 minutos, o botón *Recargar datos*).

Para cargar la jornada nueva:

```bash
python -I pipeline/scrape.py 58161861
```

```bash
$env:SB_URL="https://ghkbgfxkhdjjsyvlywrx.supabase.co"; $env:SB_KEY="<clave_de_escritura>"; python -I pipeline/load.py
```

`load.py` hace upsert por clave natural, así que se puede reejecutar sin duplicar nada.
La clave publishable es de solo lectura: para cargar hace falta una con permiso de
escritura (service role), y nunca debe acabar en el repositorio.
