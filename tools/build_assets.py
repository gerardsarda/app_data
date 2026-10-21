"""One-off: copy the Lliga Elit crests into the app and build the team map.

Source: `5. UE VALLS/escudos_equipos/` (slug.png + equipos.json, already curated
for the social-media templates). The map links each FCF `cod_equipo` to its slug,
short name and abbreviation, so the app never depends on the FCF CDN.

    python tools/build_assets.py

Re-run it if a team changes or a new season starts.
"""

from __future__ import annotations

import json
import shutil
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uevalls import data  # noqa: E402

ORIGEN = Path(r"C:\Users\gerar\OneDrive - URV\Documentos\5. UE VALLS\escudos_equipos")
DESTINO = Path(__file__).resolve().parents[1] / "assets"


def normaliza(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.upper().replace(".", " ").replace(",", " ").split())


def main() -> int:
    catalogo = json.loads((ORIGEN / "equipos.json").read_text(encoding="utf-8"))["equipos"]
    equipos = data.fetch_table("equipos", "cod_equipo")

    # FCF names in the crest catalog carry a trailing squad letter (" A", " B"...)
    # that the competition tables do not use.
    por_nombre = {}
    for slug, info in catalogo.items():
        clave = normaliza(info.get("fcf", info["nombre"]))
        partes = clave.rsplit(" ", 1)
        if len(partes) == 2 and len(partes[1]) == 1 and partes[1].isalpha():
            clave = partes[0]
        por_nombre[clave] = (slug, info)

    (DESTINO / "escudos").mkdir(parents=True, exist_ok=True)
    salida = {}
    sin_escudo = []
    for _, row in equipos.iterrows():
        clave = normaliza(row["nombre"])
        encontrado = por_nombre.get(clave)
        if not encontrado:
            sin_escudo.append(row["nombre"])
            salida[str(row["cod_equipo"])] = {
                "slug": None,
                "nombre_corto": row["nombre"].title(),
                "abrev": row["nombre"][:3].upper(),
            }
            continue
        slug, info = encontrado
        png = ORIGEN / (slug + ".png")
        if png.exists():
            shutil.copy2(png, DESTINO / "escudos" / png.name)
        salida[str(row["cod_equipo"])] = {
            "slug": slug,
            "nombre_corto": info["nombre"],
            "abrev": info["abrev"],
        }

    (DESTINO / "equipos.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("equipos mapeados: %d" % len(salida))
    print("escudos copiados: %d" % len(list((DESTINO / "escudos").glob("*.png"))))
    if sin_escudo:
        print("sin escudo:", ", ".join(sin_escudo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
