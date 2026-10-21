"""Descarga los datos de un grupo de competicion de la FCF a ./data/*.json.

Uso:
    python -I scripts/scrape.py [grupId]

Endpoints JSON publicos usados (www.fcf.cat):
    /api/competition/partidos?grupId=...      calendario + resultados por jornada
    /api/competition/acta?codacta=...         acta: alineaciones, goles, tarjetas, cambios
    /api/competition/classificacio?grupId=... clasificacion oficial
    /api/competition/goleadores?grupId=...    ranking de goleadores
    /api/competition/sanciones?grupId=...     sanciones por jornada
    /api/competition/equipos?grupId=...       equipos del grupo
"""

import json
import os
import sys
import time
import urllib.request

BASE = "https://www.fcf.cat/api/competition"
GRUP = sys.argv[1] if len(sys.argv) > 1 else "58161861"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def save(name, data):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


partidos = get(BASE + "/partidos?grupId=" + GRUP)
save("partidos", partidos)
flat = [p for lst in partidos.values() for p in lst]
cerrados = [p for p in flat if str(p.get("CERRADA")) == "1"]
print("partidos: " + str(len(flat)) + " / cerrados: " + str(len(cerrados)))

actas = {}
for i, p in enumerate(cerrados, 1):
    cod = p["CODACTA"]
    try:
        actas[cod] = get(BASE + "/acta?codacta=" + cod)
    except Exception as e:
        print("  FALLO acta " + cod + ": " + str(e))
    if i % 10 == 0:
        print("  actas " + str(i) + "/" + str(len(cerrados)))
    time.sleep(0.35)
save("actas", actas)
print("actas: " + str(len(actas)))

for name, url in [("goleadores", BASE + "/goleadores?grupId=" + GRUP),
                  ("classificacio", BASE + "/classificacio?grupId=" + GRUP),
                  ("sanciones", BASE + "/sanciones?grupId=" + GRUP),
                  ("equipos", BASE + "/equipos?grupId=" + GRUP)]:
    try:
        save(name, get(url))
        print("ok " + name)
    except Exception as e:
        print("fallo " + name + ": " + str(e))
