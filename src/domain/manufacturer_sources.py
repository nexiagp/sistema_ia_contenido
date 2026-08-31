"""Verified manufacturer sources shown by Nexia GP's public catalogue.

The catalogue is deliberately separate from fetched material.  A manufacturer
only becomes editorial context after an editor refreshes its website and then
explicitly synchronises the resulting document to the Vector Store.
"""
from __future__ import annotations

from copy import deepcopy


# Source: https://nexiagp.com/distribuidores/ (catalogue reviewed 2026-08-31).
# Website URLs are official manufacturer/brand homes, not social profiles.
MANUFACTURER_CATALOG: tuple[dict[str, str], ...] = (
    {"id": "airum", "name": "Airum", "sector": "Aire comprimido", "website": "https://www.airum.com/"},
    {"id": "ar-blue-clean", "name": "AR Blue Clean", "sector": "Limpieza profesional", "website": "https://arblueclean.it/en/"},
    {"id": "stanley", "name": "STANLEY Tools", "sector": "Herramientas", "website": "https://www.stanleyworks.es/"},
    {
        "id": "altuna", "name": "Altuna Group", "sector": "Herramientas y garden",
        "website": "https://www.altuna.es/", "fallbackUrls": "https://www.altuna.es/accesorios/",
    },
    {"id": "odem", "name": "ODEM", "sector": "Construcción", "website": "https://odem.es/"},
    {"id": "vithal-garden", "name": "Vithal Garden", "sector": "Cuidado del jardín", "website": "https://vithalgarden.com/es/"},
    {"id": "biv", "name": "BIV", "sector": "Construcción e innovación", "website": "https://www.bivinnova.com/"},
    {"id": "piher", "name": "PIHER", "sector": "Herramientas de sujeción", "website": "https://www.piher.com/en/"},
    {"id": "diadora-utility", "name": "Diadora Utility", "sector": "Calzado y ropa de trabajo", "website": "https://www.diadorautility.com/"},
    {"id": "marefix", "name": "Marefix", "sector": "Fijación y construcción", "website": "https://www.marefix.com/"},
    {"id": "catmader", "name": "Catmader", "sector": "Madera y ferretería", "website": "https://catmader.es/"},
    {"id": "dck", "name": "DCK Power Tools", "sector": "Herramientas eléctricas", "website": "https://www.dcktool.com/es/"},
    {"id": "fireside", "name": "Fireside", "sector": "Chimeneas y bioetanol", "website": "https://distribucionesfireside.com/productos-fireside/"},
    {"id": "tagu", "name": "TAGU", "sector": "Chimeneas eléctricas", "website": "https://tagu.eu/"},
    {"id": "sahara", "name": "Sahara BBQs", "sector": "Barbacoas y exterior", "website": "https://www.saharabbqs.com/sahara-bbq/"},
    {"id": "paul-voormann", "name": "Paul Voormann", "sector": "Protección y cuidado profesional", "website": "https://paul-voormann.com/de/"},
    {"id": "sesa", "name": "Sesa Tools", "sector": "Herramientas", "website": "https://www.sesatools.com/"},
    {"id": "saviola", "name": "Saviola", "sector": "Tableros y superficies", "website": "https://www.saviola.com/eng/"},
    {"id": "fabricados-lmg", "name": "Fabricados LMG", "sector": "Soluciones para el jardín", "website": "https://www.fabricadoslmg.es/"},
    {"id": "catral-group", "name": "Catral Group", "sector": "Garden y exterior", "website": "https://www.catralgroup.com/"},
    {"id": "sibol-spaciani", "name": "Sibol Spaciani", "sector": "Protección laboral", "website": "https://tiendasibol.com/"},
)


def default_manufacturer_sources() -> list[dict]:
    """Return a fresh, client-safe initial state for every verified brand."""
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "sector": item["sector"],
            "website": {
                "url": item["website"],
                "fallbackUrls": [url for url in item.get("fallbackUrls", "").split("|") if url],
                "enabled": True,
                "lastStatus": "pending",
                "lastSyncAt": None,
                "lastError": None,
                "pages": 0,
                "documentId": None,
            },
            "social": {
                "x": {
                    "enabled": False,
                    "handle": "",
                    "status": "pending_discovery",
                    "lastSyncAt": None,
                    "lastError": None,
                    "seenPostIds": [],
                }
            },
            "discoveredSocials": [],
        }
        for item in MANUFACTURER_CATALOG
    ]


def ensure_manufacturer_sources(db: dict) -> list[dict]:
    """Soft-migrate state without overwriting operator choices or sync history."""
    existing = db.setdefault("manufacturerSources", [])
    by_id = {item.get("id"): item for item in existing if isinstance(item, dict) and item.get("id")}
    for default in default_manufacturer_sources():
        current = by_id.get(default["id"])
        if current is None:
            existing.append(default)
            continue
        for key in ("name", "sector"):
            current.setdefault(key, default[key])
        website = current.setdefault("website", {})
        for key, value in default["website"].items():
            website.setdefault(key, value)
        social = current.setdefault("social", {})
        x_source = social.setdefault("x", {})
        for key, value in default["social"]["x"].items():
            x_source.setdefault(key, deepcopy(value))
        current.setdefault("discoveredSocials", [])
    return existing
