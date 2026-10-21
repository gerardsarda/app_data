# UE Valls · Analítica Lliga Elit Grup 1

App en Streamlit sobre les dades oficials de la FCF (Lliga Elit, Grup 1, temporada
2026-27) desades al projecte Supabase **UEValls**.

## Les quatre pestanyes

- **Classificació** — taula visual amb escut, diferència de gols, ratxa dels últims
  cinc partits i punts; a sota, quan i on es marca a la lliga.
- **Rànquings** — tops per tema (Gols, Defensa, Targetes, Banqueta i **Avançat**) en
  barres, amb l'equip seleccionat ressaltat en vermell i l'etiqueta de fiabilitat a
  cada targeta.
- **Equip** — graella amb els 16 escuts per triar equip i, a sota, el seu informe
  repartit en cinc sub-pestanyes: Resum, Gols, Defensa i targetes, Plantilla, i
  Partits i context.
- **Jugadors** — golejadors, targetes i minuts de tota la lliga.

Un slider de jornades a la capçalera recalcula **tota** l'app sobre el rang triat, i
el botó *Llegenda* explica les etiquetes de fiabilitat i els avisos sobre la font.

## Quines estadístiques hi ha

**Ja es calculen** — tot surt de l'acta oficial, reconstruint els partits minut a minut:

| Bloc | Mètriques |
|---|---|
| Marcador | temps guanyant / empatant / perdent, qui marca primer i quants punts dona, minut mitjà del primer gol marcat i encaixat, amb quin marcador arriba cada gol |
| Partits | remuntades, avantatges deixats escapar, del descans al final amb els punts guanyats o perduts a la segona part, partits on marquen els dos, resultat més repetit |
| Atac | golejadors, gols per tram de 15 minuts, de jugada / de penal / en pròpia, gols de titulars i de suplents, golejadors diferents, gols de resposta |
| Defensa | porteries a zero, ratxa més llarga sense encaixar, en quin estat del marcador encaixa, gols encaixats per tram |
| Plantilla | minuts estimats, jugadors utilitzats, sempre titulars, canvis a l'onze entre jornades, minut del primer i de l'últim canvi, targetes per 90 minuts |
| Context | quilòmetres de desplaçament a cada camp, punts aconseguits fora |

**Caldran més jornades** — la dada existeix, però encara no té prou mostra per ordenar
equips: gols als primers 20 minuts, gols de resposta en menys de 10 minuts, gols
encaixats just després de marcar, penals, rendiment segons l'àrbitre, segons el dia i
l'hora, i segons els quilòmetres del desplaçament.

**Es podria afegir descarregant més** — temporades anteriors, la resta d'equips del
club, la Copa Catalunya, l'històric de sancions, el calendari amb camps i horaris.

**La FCF no ho publica** — tirs, xG, possessió, córners, faltes, passades, posicions i
sistema, mapes de calor, edat i dades físiques, lesions, i els minuts de descompte reals.

## Com es validen els insights

Amb 5 jornades hi ha 34 partits, 90 gols i 186 targetes a jugadors. A aquest volum
algunes preguntes es poden respondre i d'altres no, així que **cada insight declara el
nombre d'esdeveniments que el sostenen i es qualifica abans d'arribar a l'app**:

| Veredicte | Significat |
|---|---|
| `dada sòlida` | hi ha prou esdeveniments per descriure una tendència |
| `poques dades` | real però fràgil: un partit pot reordenar el rànquing |
| `molt poques dades` | massa pocs esdeveniments per ordenar equips; es mostra com a dada solta |

Els llindars són a `uevalls/insights.py` (`UMBRAL_OK`, `UMBRAL_ORIENTATIVO`). La nota es
recalcula a cada càrrega, així que els insights descartats avui s'aproven sols quan
entrin més jornades.

Dues decisions que afecten tots els rànquings:

1. **Els equips no han jugat el mateix** (de 3 a 5 partits), així que els rànquings de
   volum van normalitzats per partit, amb el total al costat.
2. **Les targetes del cos tècnic se separen** de les de jugadors (18 de 204) i no entren
   a cap rànquing.

Per veure l'informe de validació per consola:

```bash
python validate_insights.py
```

Inclou un contrast contra la classificació oficial de la FCF: PJ, punts, G/E/P, GF i GC
coincideixen als 16 equips.

## Límits coneguts

- **Descompte agrupat.** La FCF publica 45+X com a minut 44 i 90+X com a minut 89, així
  que els trams 31-45 i 76-90 surten inflats i cap gol apareix per sobre del 90.
- **Minuts estimats.** Es calculen amb titularitat, canvis i vermelles, sense descompte,
  amb sostre de 90.
- **Doble groga.** El camp `segunda_amarilla` arriba sempre buit des de la FCF;
  l'expulsió per doble groga s'identifica per l'article de la sanció.
- **Gols en pròpia.** Sumen a l'equip beneficiat i no s'atribueixen a cap golejador
  d'aquell equip.
- **Distàncies en línia recta.** Els quilòmetres són haversine entre camps, no ruta per
  carretera.

## Estructura

```
app.py                  interfície Streamlit
uevalls/data.py         lectura de Supabase via PostgREST (paginada)
uevalls/metrics.py      frames derivats: gols amb context, equip-partit, minuts, resum
uevalls/advanced.py     estadístiques avançades reconstruïdes minut a minut
uevalls/insights.py     catàleg d'insights, llindars i informes
uevalls/ui.py           paleta, CSS i les peces HTML de les barres i targetes
validate_insights.py    informe de validació per consola
tools/build_assets.py   copia els escuts i construeix assets/equipos.json
assets/                 escuts i mapa d'equips
pipeline/scrape.py      descarrega les actes de la FCF a data/*.json
pipeline/load.py        carrega aquests JSON a Supabase (upsert, reexecutable)
pipeline/README_bbdd.md documentació del model de dades i de les vistes SQL
```

El marcador abans de cada gol es reconstrueix ordenant els gols de l'acta, que és el que
permet respondre "marca anant per darrere?" i "reacciona després d'encaixar?".

## Colors

La paleta està validada amb el script de daltonisme i contrast: blau `#3987e5` i taronja
`#d95926` per a les sèries, vermell `#E03A24` només per a l'equip en focus, i la paleta
d'estat reservada per a les etiquetes de fiabilitat. Els rànquings fan servir **èmfasi**
(un color per a tothom, l'equip triat ressaltat) i no una rampa de valor, perquè la
llargada de la barra ja codifica la magnitud.

## Executar en local

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

## Credencials

L'app llegeix amb una clau **publishable** de Supabase i les taules tenen RLS de només
lectura, així que la clau no pot escriure. L'ordre de resolució és: secrets de Streamlit
→ variables d'entorn `SB_URL` / `SB_KEY` → valors per defecte a `uevalls/data.py`.

Per a Streamlit Cloud, copia `.streamlit/secrets.toml.example` a *App settings → Secrets*.

## Desplegar a Streamlit Community Cloud

1. Puja aquesta carpeta a un repositori de GitHub.
2. A [share.streamlit.io](https://share.streamlit.io) tria *New app*, selecciona el
   repositori i posa `app.py` com a *Main file path*.
3. Enganxa el contingut de `.streamlit/secrets.toml.example` a *Secrets*.
4. Deploy.

## Actualitzar després de cada jornada

Les dades vénen de la base **UEValls**. Quan es carreguin jornades noves, l'app les
agafa sola (memòria cau de 30 minuts).

```bash
python -I pipeline/scrape.py 58161861
```

```bash
$env:SB_URL="https://ghkbgfxkhdjjsyvlywrx.supabase.co"; $env:SB_KEY="<clau_escriptura>"; python -I pipeline/load.py
```

`load.py` fa upsert per clau natural, així que es pot reexecutar sense duplicar res. La
clau publishable és de només lectura: per carregar cal una amb permís d'escriptura
(service role), i no ha d'acabar mai al repositori.
