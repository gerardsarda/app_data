# FCF — Lliga Elit, Grup 1 (temporada 2026-27) → Supabase `UEValls`

Base de datos relacional construida a partir de los datos públicos de la Federació
Catalana de Futbol para el grupo de competición de la U.E. Valls.

- Proyecto Supabase: **UEValls** (`ghkbgfxkhdjjsyvlywrx`, región `eu-west-1`)
- Competición: `LLIGA ELIT` / `GRUP 1` / temporada `2026-27`
- `grupId` = `58161861`, `competicioId` = `58161860`, `disciplinaId` = `19308233`
- Fecha de captura: 2026-10-21 (jornadas 1–5 disputadas)

## Origen de los datos

La web de la FCF es una app Next.js que consume endpoints JSON públicos. Se usan
directamente en lugar de raspar el HTML:

| Endpoint | Contenido |
|---|---|
| `/api/competition/partidos?grupId=` | calendario completo (30 jornadas) y resultados |
| `/api/competition/acta?codacta=` | acta del partido: alineaciones, goles, tarjetas, cambios, árbitros, cuerpo técnico |
| `/api/competition/classificacio?grupId=` | clasificación oficial |
| `/api/competition/goleadores?grupId=` | ranking de goleadores |
| `/api/competition/sanciones?grupId=` | sanciones por jornada |

El acta en web equivalente está en `https://www.fcf.cat/es/competicio/acta/<codacta>`.

## Volumen cargado

| Tabla | Filas |
|---|---|
| `partidos` | 240 (34 jugados, 206 pendientes) |
| `alineaciones` | 1.348 |
| `sustituciones` | 391 |
| `tarjetas` | 204 (18 a banquillo) |
| `goles` | 90 |
| `cuerpo_tecnico` | 379 |
| `personas` | 484 |
| `equipos` / `clubes` / `campos` | 16 / 16 / 16 |
| `arbitros` | 78 |
| `sanciones` | 12 |
| `clasificacion_fcf` | 16 |

## Modelo

**Dimensiones:** `temporadas`, `disciplinas`, `competiciones`, `grupos`, `clubes`,
`equipos`, `campos`, `arbitros`, `personas` (jugadores y técnicos comparten el
espacio de identificadores de licencia; 0 colisiones detectadas).

**Catálogos:** `tipos_gol`, `tipos_tarjeta`, `tipos_tecnico`.

**Hechos:** `partidos` → `partido_arbitros`, `alineaciones`, `cuerpo_tecnico`,
`goles`, `tarjetas`, `sustituciones`, `sanciones`.

**Snapshot oficial:** `clasificacion_fcf` (la clasificación tal cual la publica la FCF,
para contrastar los cálculos propios).

### Codificación de la fuente

| Campo | Valor | Significado |
|---|---|---|
| `tipo_gol` | 100 | gol de jugada |
| | 101 | gol de penal |
| | 102 | gol en propia portería |
| `tipo_tarjeta` | 100 | amarilla |
| | 101 | roja |

Los goles en propia portería (`102`) llegan en la lista del equipo del ejecutor pero
suman para el rival. En `goles` eso se resuelve con tres columnas:
`cod_equipo_jugador` (quién lo marca), `cod_equipo_favor` (quién lo suma) y
`cod_equipo_contra`. Verificado: la suma de `cod_equipo_favor` cuadra con el
resultado en los 34 partidos.

`parte` se deriva del minuto: `minuto <= 45` → 1ª parte, resto → 2ª.

## Vistas analíticas

| Vista | Para qué |
|---|---|
| `v_partidos_equipo` | formato largo: una fila por equipo y partido, con GF/GC por parte, tramos de 15', tarjetas, portería a cero |
| `v_equipo_resumen` | **tabla global**: PJ/V/E/D y puntos totales, en casa y fuera; GF, GC, GF 1ª/2ª parte, GC 1ª/2ª parte, GF/GC casa y fuera, penales, propias, tramos de 15', porterías a cero, partidos sin marcar, tarjetas, medias |
| `v_clasificacion` | clasificación calculada a partir de los partidos |
| `v_evolucion_equipo` | puntos y goles acumulados jornada a jornada |
| `v_goles_detalle` | cada gol con goleador, minuto, parte, tipo y rival |
| `v_tarjetas_detalle` | cada tarjeta con persona, minuto, tipo, si es jugador o banquillo |
| `v_sustituciones_detalle` | cada cambio con quién entra, quién sale y minuto |
| `v_alineacion_detalle` | alineación de un partido con dorsal, titular/suplente, capitán, portero y minutos |
| `v_minutos_jugador` | minutos jugados por jugador y partido (titular/entrada, salida por cambio o roja) |
| `v_jugador_resumen` | por jugador: convocatorias, PJ, titularidades, minutos, goles (totales, de penal, propias, por parte), tarjetas, minutos por gol |
| `v_goles_partido_equipo`, `v_tarjetas_partido_equipo` | agregados intermedios |

## Validación

`v_equipo_resumen` se contrastó contra `clasificacion_fcf`: **16/16 equipos coinciden**
en PJ, puntos, G, E, P, GF y GC. Además: 0 partidos descuadrados entre resultado y
eventos de gol, 0 actas sin 11 titulares, 0 goleadores fuera de la alineación.

## Limitaciones conocidas

- Los minutos de descuento aparecen agrupados en la fuente: hay un pico de goles en
  el minuto 44 (45+) y en el 89 (90+). El minuto se guarda tal cual lo publica la FCF.
- `v_minutos_jugador` estima minutos con partidos de 90' sin descuento, y toma la
  primera entrada y la primera salida de cada jugador.
- `segunda_amarilla` llega siempre nulo en la fuente; una expulsión por doble amarilla
  se identifica por `tipo_tarjeta = 101` más dos amarillas del mismo jugador, o por la
  tabla `sanciones` (artículo 336).
- Las etiquetas de `tipos_tecnico` (ET, EA, PF, FTP, DCS…) son una interpretación de la
  leyenda del acta web; los códigos originales se conservan.
- `penaltis_local` / `penaltis_visitante` existen para eliminatorias; en liga son nulos.

## Seguridad

RLS activado en las 21 tablas, con política `lectura_publica` de solo `SELECT` para
`anon` y `authenticated`; `INSERT`/`UPDATE`/`DELETE` revocados para esos roles. Las
vistas usan `security_invoker = on`. El *security advisor* de Supabase no reporta avisos.
La carga se hace con `service_role` o por SQL.

## Refrescar los datos

```bash
python -I scripts/scrape.py 58161861
SB_URL=https://ghkbgfxkhdjjsyvlywrx.supabase.co SB_KEY=<service_role_key> python -I scripts/load.py
```

Todas las inserciones son *upsert* por clave natural, así que se puede reejecutar tras
cada jornada. `tarjetas` y `sustituciones` no tienen clave natural: vacíalas antes de
recargar un acta ya cargada.

Para otro grupo o temporada, pasa su `grupId` a `scrape.py` y ajusta las constantes
`TEMPORADA`, `COD_DISCIPLINA`, `COD_COMPETICION`, `COD_GRUPO` en `load.py`.

## Ejemplos

Goles del Manlleu con goleador y minuto:

```sql
select jornada, equipo_contra as rival, jugador, minuto, parte, tipo
from v_goles_detalle
where cod_equipo_favor = 34413
order by jornada, minuto;
```

Tabla global ordenada por puntos:

```sql
select equipo, pj, puntos, victorias, empates, derrotas,
       gf, gc, gf_p1, gf_p2, gc_p1, gc_p2,
       gf_casa, gc_casa, gf_fuera, gc_fuera,
       victorias_casa, victorias_fuera, porterias_cero
from v_clasificacion
order by posicion;
```

Rendimiento de la U.E. Valls jornada a jornada:

```sql
select jornada, rival, es_local, gf, gc, signo, puntos_acumulados
from v_evolucion_equipo
where cod_equipo = 33936
order by jornada;
```

Minutos y goles de la plantilla del Valls:

```sql
select jugador, pj, titularidades, minutos, goles, amarillas, rojas
from v_jugador_resumen
where cod_equipo = 33936
order by minutos desc;
```
