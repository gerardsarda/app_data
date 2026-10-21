import json, os, sys, io, urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

URL = os.environ["SB_URL"].rstrip("/")
KEY = os.environ["SB_KEY"]
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

TEMPORADA = 22
COD_DISCIPLINA = 19308233
COD_COMPETICION = 58161860
COD_GRUPO = 58161861


def L(n):
    return json.load(open(os.path.join(D, n + ".json"), encoding="utf-8"))


PART = L("partidos")
ACTAS = L("actas")
GOL = L("goleadores")
CLAS = L("classificacio")
SANC = L("sanciones")


def post(table, rows, on_conflict=None):
    if not rows:
        print("  " + table + ": 0")
        return
    done = 0
    for i in range(0, len(rows), 400):
        chunk = rows[i:i + 400]
        u = URL + "/rest/v1/" + table
        if on_conflict:
            u += "?on_conflict=" + on_conflict
        req = urllib.request.Request(
            u, data=json.dumps(chunk).encode("utf-8"), method="POST",
            headers={"apikey": KEY, "Authorization": "Bearer " + KEY,
                     "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
                done += len(chunk)
        except urllib.error.HTTPError as e:
            print("  !! " + table + ": " + str(e.code) + " " + e.read().decode()[:600])
            return
    print("  " + table + ": " + str(done))


def I(v):
    return None if v in (None, "") else int(v)


def F(v):
    return None if v in (None, "") else float(v)


def parte(m):
    return 1 if int(m) <= 45 else 2


flat = [p for v in PART.values() for p in v]

post("temporadas", [{"cod_temporada": TEMPORADA, "nombre": "2026-27"}], "cod_temporada")
post("disciplinas", [{"cod_disciplina": COD_DISCIPLINA, "nombre": "Futbol 11"}], "cod_disciplina")
post("competiciones", [{"cod_competicion": COD_COMPETICION, "nombre": "LLIGA ELIT",
                        "cod_disciplina": COD_DISCIPLINA}], "cod_competicion")
post("grupos", [{"cod_grupo": COD_GRUPO, "cod_competicion": COD_COMPETICION,
                 "cod_temporada": TEMPORADA, "nombre": "GRUP 1"}], "cod_grupo")

post("tipos_gol", [
    {"tipo_gol": 100, "codigo": "jugada", "etiqueta": "Gol"},
    {"tipo_gol": 101, "codigo": "penal", "etiqueta": "Gol de penal"},
    {"tipo_gol": 102, "codigo": "propia", "etiqueta": "Gol en propia porteria"},
], "tipo_gol")
post("tipos_tarjeta", [
    {"tipo_tarjeta": 100, "codigo": "amarilla", "etiqueta": "Tarjeta amarilla"},
    {"tipo_tarjeta": 101, "codigo": "roja", "etiqueta": "Tarjeta roja"},
], "tipo_tarjeta")

TT = {"ET": "Entrenador titular", "EA": "Entrenador auxiliar", "EP": "Entrenador de porteros",
      "EM": "Entrenador / monitor", "PF": "Preparador fisico", "FTP": "Fisioterapeuta",
      "D": "Delegado de equipo", "DCS": "Delegado de campo", "AU": "Auxiliar"}
tipos_tec = sorted({t.get("tipo_nombre") for a in ACTAS.values() for s in ("local", "visitante")
                    for t in a["tecnicos_equipo_" + s] if t.get("tipo_nombre")})
post("tipos_tecnico", [{"codigo": c, "etiqueta": TT.get(c, c)} for c in tipos_tec], "codigo")

clubes, equipos = {}, {}
for p in flat:
    for lado in ("CASA", "FUERA"):
        eq = int(p["CODEQUIPO_" + lado])
        cl = I(p["CODCLUB_" + lado])
        equipos[eq] = {"cod_equipo": eq, "cod_club": cl,
                       "nombre": p["NOMBRE_" + lado], "escudo": p["ESCUDO_" + lado]}
        if cl:
            clubes[cl] = {"cod_club": cl, "nombre": p["NOMBRE_" + lado]}
for a in ACTAS.values():
    for k in ("equipo_local", "equipo_visitante"):
        e = a[k]
        ce = int(e["CODEQUIPO"])
        row = equipos.setdefault(ce, {"cod_equipo": ce})
        row.update({"cod_club": I(e.get("CODCLUB")), "nombre": e["NOMBRE_EQUIPO"],
                    "escudo": e.get("escudo")})
if isinstance(SANC, dict):
    for lst in SANC.values():
        for r in lst:
            if r.get("codclub"):
                clubes.setdefault(int(r["codclub"]),
                                  {"cod_club": int(r["codclub"]), "nombre": r["nombre_equipo"]})
post("clubes", list(clubes.values()), "cod_club")
post("equipos", list(equipos.values()), "cod_equipo")

campos = {}
for p in flat:
    c = I(p.get("CODIGO_CAMPO"))
    if c:
        campos[c] = {"cod_campo": c, "nombre": p["CAMPO"],
                     "latitud": F(p.get("LATITUD")), "longitud": F(p.get("LONGITUD"))}
for a in ACTAS.values():
    c = I(a.get("CODIGO_CAMPO"))
    if c:
        campos.setdefault(c, {"cod_campo": c, "nombre": a.get("CAMPO")})
post("campos", list(campos.values()), "cod_campo")

arb = {}
for a in ACTAS.values():
    for r in a.get("arbitros", []):
        arb[int(r["CODARBITRO"])] = {"cod_arbitro": int(r["CODARBITRO"]),
                                     "nombre": r["nombre_arbitro"],
                                     "codigo_delegacion": r.get("codigo_delegacion"),
                                     "delegacion": r.get("delegacion")}
post("arbitros", list(arb.values()), "cod_arbitro")

per = {}
for a in ACTAS.values():
    for s in ("local", "visitante"):
        for j in a["jugadores_equipo_" + s]:
            per[int(j["id"])] = j["nombre"]
        for t in a["tecnicos_equipo_" + s]:
            per.setdefault(int(t["id"]), t["nombre"])
for g in GOL:
    per.setdefault(int(g["codjugador"]), g["nombre_jugador"])
post("personas", [{"cod_persona": k, "nombre": v} for k, v in per.items()], "cod_persona")

rows = []
for p in flat:
    gl, gv = I(p["GOLES_CASA"]), I(p["GOLES_FUERA"])
    cerrada = p["CERRADA"] == "1"
    res = None
    if cerrada and gl is not None and gv is not None:
        res = "L" if gl > gv else ("V" if gv > gl else "E")
    com = p.get("COMIENZO1")
    rows.append({"cod_acta": int(p["CODACTA"]), "cod_grupo": int(p["CODGRUPO"]),
                 "jornada": int(p["JORNADA"]), "comienzo": com,
                 "fecha": com[:10] if com else None, "hora": com[11:19] if com else None,
                 "cod_equipo_local": int(p["CODEQUIPO_CASA"]),
                 "cod_equipo_visitante": int(p["CODEQUIPO_FUERA"]),
                 "cod_campo": I(p.get("CODIGO_CAMPO")),
                 "goles_local": gl if cerrada else None,
                 "goles_visitante": gv if cerrada else None,
                 "penaltis_local": I(p.get("PENALTIS_CASA")),
                 "penaltis_visitante": I(p.get("PENALTIS_FUERA")),
                 "cerrada": cerrada, "estado": p.get("ESTADO"), "jugado": cerrada,
                 "resultado": res})
post("partidos", rows, "cod_acta")

pa, alin, tec, goles, tarj, sust = [], [], [], [], [], []
for cod, a in ACTAS.items():
    ca = int(cod)
    loc = int(a["CODEQUIPO_CASA"])
    vis = int(a["CODEQUIPO_FUERA"])
    seen = set()
    for r in a.get("arbitros", []):
        k = (int(r["CODARBITRO"]), r.get("rol"))
        if k in seen:
            continue
        seen.add(k)
        pa.append({"cod_acta": ca, "cod_arbitro": int(r["CODARBITRO"]), "rol": r.get("rol"),
                   "tipo_arbitro": I(r.get("CODTIPO_ARBITRO")), "orden": I(r.get("ORDEN"))})
    for s, eq in (("local", loc), ("visitante", vis)):
        es_loc = s == "local"
        otro = vis if es_loc else loc
        jug = a["jugadores_equipo_" + s]
        ids_j = {j["id"] for j in jug}
        dorsales = {j["id"]: I(j.get("dorsal")) for j in jug}
        for j in jug:
            alin.append({"cod_acta": ca, "cod_equipo": eq, "cod_persona": int(j["id"]),
                         "dorsal": I(j.get("dorsal")), "titular": j.get("titular") == "1",
                         "capitan": j.get("capitan") == "1",
                         "portero": str(j.get("portero")) == "1", "es_local": es_loc})
        for t in a["tecnicos_equipo_" + s]:
            if not t.get("tipo_nombre"):
                continue
            tec.append({"cod_acta": ca, "cod_equipo": eq, "cod_persona": int(t["id"]),
                        "tipo_nombre": t["tipo_nombre"], "tipo_licencia": t.get("tipo_licencia"),
                        "es_local": es_loc})
        for g in a["goles_equipo_" + s]:
            tg = int(g["tipo_gol"])
            propia = tg == 102
            favor = otro if propia else eq
            goles.append({"cod_acta": ca, "cod_persona": I(g.get("id_jugador")),
                          "cod_equipo_jugador": eq, "cod_equipo_favor": favor,
                          "cod_equipo_contra": eq if propia else otro,
                          "dorsal": I(g.get("dorsal")), "minuto": int(g["minuto"]),
                          "parte": parte(g["minuto"]), "tipo_gol": tg,
                          "es_penal": tg == 101, "es_propia": propia,
                          "favor_local": favor == loc})
        for t in a["tarjetas_equipo_" + s]:
            pid = t.get("id_jugador")
            tarj.append({"cod_acta": ca, "cod_equipo": eq, "cod_persona": I(pid),
                         "es_jugador": pid in ids_j, "dorsal": dorsales.get(pid),
                         "minuto": int(t["minuto"]), "parte": parte(t["minuto"]),
                         "tipo_tarjeta": int(t["tipo_tarjeta"]),
                         "segunda_amarilla": bool(t.get("segunda_amarilla")), "es_local": es_loc})
        for x in a["sustituciones_equipo_" + s]:
            sust.append({"cod_acta": ca, "cod_equipo": eq,
                         "cod_persona_entra": I(x.get("id_jugador_entra")),
                         "cod_persona_sale": I(x.get("id_jugador_sale")),
                         "dorsal_entra": I(x.get("entradorsal")),
                         "dorsal_sale": I(x.get("saledorsal")),
                         "minuto": int(x["minuto"]), "parte": parte(x["minuto"]),
                         "es_local": es_loc})

post("partido_arbitros", pa, "cod_acta,cod_arbitro,rol")
post("alineaciones", alin, "cod_acta,cod_persona")
post("cuerpo_tecnico", tec, "cod_acta,cod_persona,tipo_nombre")
post("goles", goles, "cod_acta,cod_persona,minuto,tipo_gol")
post("tarjetas", tarj)
post("sustituciones", sust)

srows = []
if isinstance(SANC, dict):
    for lst in SANC.values():
        for r in lst:
            srows.append({"cod_acta": I(r.get("codacta")), "jornada": I(r.get("jornada")),
                          "tipo": r.get("tipo"), "cod_equipo": I(r.get("codequipo")),
                          "cod_persona": I(r.get("codparticipante")),
                          "persona_nombre": r.get("participante_nombre"),
                          "licencia": r.get("licencia"),
                          "motivo": (r.get("motivo_sancion") or "").strip(),
                          "articulo": r.get("articulo_salida"),
                          "partidos_sancion": I(r.get("partidos_sancion")),
                          "cod_tiposancion": I(r.get("cod_tiposancion"))})
post("sanciones", srows)

crows = []
for r in CLAS["data"]:
    crows.append({"cod_grupo": COD_GRUPO, "posicion": int(r["position"]),
                  "cod_equipo": int(r["team"]["teamId"]), "puntos": F(r.get("points")),
                  "jugados": I(r.get("played")), "ganados": I(r.get("won")),
                  "empatados": I(r.get("drawn")), "perdidos": I(r.get("lost")),
                  "goles_favor": I(r.get("goalsFor")), "goles_contra": I(r.get("goalsAgainst")),
                  "coeficiente": F(r.get("coefficient")), "color": r.get("promotionColor")})
post("clasificacion_fcf", crows, "cod_grupo,posicion")
print("OK")
