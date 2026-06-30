"""Helpers puros (sin OpenAI, sin I/O) para calidad editorial.

Se usan en el pipeline de posts para:
- pasar a planner/writer las aperturas recientes y evitar hooks clonicos,
- normalizar los hashtags de marca,
- recortar texto a un limite duro (p. ej. 280 de X) sin cortar a mitad de palabra.

Todo es determinista y testeable de forma aislada.
"""
from __future__ import annotations

# Variantes del hashtag de marca que deben colapsar a la forma canonica.
BRAND_HASHTAG = "#NexiaGP"
_BRAND_PREFIXES = ("#nexia",)  # cubre #NexiaGP, #NexiaGrowthPartner, #Nexia, #NexiaGrowth...


def first_line(text: str) -> str:
    """Primera linea no vacia de un texto (el hook del post)."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def recent_openings(db: dict, limit: int = 12) -> list[str]:
    """Hooks (primera linea) de los posts mas recientes, para no repetir aperturas."""
    out: list[str] = []
    for post in (db.get("posts") or [])[:limit]:
        hook = first_line(post.get("copy") or "")
        if hook:
            out.append(hook)
    return out


def recent_angles(db: dict, limit: int = 12) -> list[str]:
    """Tesis/angulos recientes, para no repetir la idea central."""
    out: list[str] = []
    for post in (db.get("posts") or [])[:limit]:
        angle = post.get("angle") or post.get("idea") or post.get("title")
        if angle:
            out.append(str(angle))
    return out


def normalize_hashtags(tags, max_n: int = 6) -> list[str]:
    """Normaliza hashtags: marca unica #NexiaGP al frente, dedup, cap a max_n.

    - Colapsa cualquier variante de marca (#NexiaGrowthPartner, #Nexia...) a #NexiaGP.
    - Garantiza el '#', elimina duplicados (case-insensitive) conservando el primero.
    - Asegura que #NexiaGP este presente exactamente una vez, en primera posicion.
    """
    seen: set[str] = set()
    out: list[str] = []
    brand_added = False
    for raw in tags or []:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if not tag:
            continue
        tag = "#" + tag.lstrip("#").strip()
        if tag == "#":
            continue
        low = tag.lower()
        if low.startswith(_BRAND_PREFIXES):
            if not brand_added:
                out.insert(0, BRAND_HASHTAG)
                seen.add(BRAND_HASHTAG.lower())
                brand_added = True
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(tag)
    if not brand_added:
        out.insert(0, BRAND_HASHTAG)
    return out[:max_n]


def clip_text(text: str, limit: int = 280) -> str:
    """Recorta a <= limit caracteres cortando en frontera de frase o palabra (nunca a mitad)."""
    if not isinstance(text, str) or len(text) <= limit:
        return text or ""
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "\n"):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).strip()
