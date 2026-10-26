from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[3]
PROMPT_DIR = ROOT / "src" / "ai" / "prompts"
SCHEMA_DIR = ROOT / "src" / "ai" / "schemas"
DB_PATH = ROOT / "data" / "db.json"
_db_reader: Callable[[], dict] | None = None


def configure_db_reader(reader: Callable[[], dict] | None) -> None:
    """Inject the managed state reader without coupling prompts to HTTP code."""
    global _db_reader
    _db_reader = reader


# Canonical registry of every prompt the app exposes for editing.
# Key is the file-relative name (the same string services pass to `load_prompt`).
# Order here drives the default order in the UI.
PROMPT_REGISTRY: "dict[str, dict]" = {
    # --- Core posts ---
    "base_global_v1.txt":   {"label": "Prompt base global", "group": "core_posts", "scope": "posts"},
    "planner_v1.txt":       {"label": "Planner",            "group": "core_posts", "scope": "posts"},
    "validator_v1.txt":     {"label": "Validator",          "group": "core_posts", "scope": "posts"},

    # --- Post types (11) ---
    "post_types/marca_propuesta_valor_v1.txt":     {"label": "Marca / Propuesta de valor",      "group": "post_types", "scope": "posts"},
    "post_types/educativo_autoridad_v1.txt":        {"label": "Educativo / Autoridad",           "group": "post_types", "scope": "posts"},
    "post_types/sector_solucion_v1.txt":            {"label": "Sector / Solución",               "group": "post_types", "scope": "posts"},
    "post_types/fabricante_colaborador_v1.txt":     {"label": "Fabricante colaborador",          "group": "post_types", "scope": "posts"},
    "post_types/proyecto_prescripcion_v1.txt":      {"label": "Proyecto / Prescripción",         "group": "post_types", "scope": "posts"},
    "post_types/servicio_proceso_operativa_v1.txt": {"label": "Servicio / Proceso operativa",    "group": "post_types", "scope": "posts"},
    "post_types/actualidad_lectura_mercado_v1.txt": {"label": "Actualidad / Lectura de mercado", "group": "post_types", "scope": "posts"},
    "post_types/founder_pov_v1.txt":                {"label": "Founder / Punto de vista",        "group": "post_types", "scope": "posts"},
    "post_types/social_proof_caso_v1.txt":          {"label": "Prueba social / Caso",            "group": "post_types", "scope": "posts"},
    "post_types/encuesta_pulso_v1.txt":             {"label": "Encuesta / Pulso",                "group": "post_types", "scope": "posts"},
    "post_types/dato_opinion_v1.txt":               {"label": "Dato + Opinion",                  "group": "post_types", "scope": "posts"},

    # --- Transformers (3) ---
    "transformers/adaptacion_x_v1.txt":        {"label": "Adaptación X (Twitter)", "group": "transformers", "scope": "posts"},
    "transformers/adaptacion_facebook_v1.txt": {"label": "Adaptación Facebook",    "group": "transformers", "scope": "posts"},
    "transformers/adaptacion_instagram_v1.txt": {"label": "Adaptación Instagram", "group": "transformers", "scope": "posts"},

    # --- Blog ---
    "blog_planner_v1.txt": {"label": "Blog · Planner", "group": "blog", "scope": "blog"},
    "blog_writer_v1.txt":  {"label": "Blog · Writer",  "group": "blog", "scope": "blog"},
    "blog_seo_v1.txt":     {"label": "Blog · SEO",     "group": "blog", "scope": "blog"},
}


POST_TYPE_PROMPTS = {
    "marca_propuesta_valor": "post_types/marca_propuesta_valor_v1.txt",
    "educativo_autoridad": "post_types/educativo_autoridad_v1.txt",
    "sector_solucion": "post_types/sector_solucion_v1.txt",
    "fabricante_colaborador": "post_types/fabricante_colaborador_v1.txt",
    "proyecto_prescripcion": "post_types/proyecto_prescripcion_v1.txt",
    "servicio_proceso_operativa": "post_types/servicio_proceso_operativa_v1.txt",
    "actualidad_lectura_mercado": "post_types/actualidad_lectura_mercado_v1.txt",
    "founder_pov": "post_types/founder_pov_v1.txt",
    "social_proof_caso": "post_types/social_proof_caso_v1.txt",
    "encuesta_pulso": "post_types/encuesta_pulso_v1.txt",
    "dato_opinion": "post_types/dato_opinion_v1.txt",
}

TRANSFORMER_PROMPTS = {
    "adaptacion_x": "transformers/adaptacion_x_v1.txt",
    "adaptacion_facebook": "transformers/adaptacion_facebook_v1.txt",
    "adaptacion_instagram": "transformers/adaptacion_instagram_v1.txt",
}


# ----- core readers -----

def _read_db_safe() -> dict:
    """Read db.json best-effort; return {} on any failure (transient write window, missing file)."""
    try:
        if _db_reader is not None:
            return _db_reader()
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_file_prompt(name: str) -> str:
    """Read a prompt straight from disk, no override. Used to seed baseline versions."""
    return (PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def load_prompt(name: str) -> str:
    """Return the prompt text the pipelines should use.

    Checks `data/db.json -> prompt_overrides[name].text` first; falls back to the
    `.txt` file in `src/ai/prompts/`.
    """
    db = _read_db_safe()
    overrides = db.get("prompt_overrides") or {}
    entry = overrides.get(name)
    if isinstance(entry, dict):
        text = entry.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return read_file_prompt(name)


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


# ----- helpers used by existing services -----

def base_prompt() -> str:
    return load_prompt("base_global_v1.txt")


def planner_prompt() -> str:
    return load_prompt("planner_v1.txt")


def validator_prompt() -> str:
    return load_prompt("validator_v1.txt")


def post_type_prompt(post_type: str) -> str:
    path = POST_TYPE_PROMPTS.get(post_type)
    if not path:
        raise ValueError(f"Tipo de post no soportado: {post_type}")
    return load_prompt(path)


def transformer_prompt(name: str) -> str:
    path = TRANSFORMER_PROMPTS.get(name)
    if not path:
        raise ValueError(f"Transformador no soportado: {name}")
    return load_prompt(path)


def schema(name: str) -> dict:
    return load_schema(name)


# ----- editor API (read-side; writes happen in server.py with DB_LOCK) -----

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def is_registered(prompt_id: str) -> bool:
    return prompt_id in PROMPT_REGISTRY


def registry_entry(prompt_id: str) -> dict:
    return PROMPT_REGISTRY[prompt_id]


def list_prompts_meta() -> list:
    """Summary row per registered prompt. Used by GET /api/prompts."""
    db = _read_db_safe()
    overrides = db.get("prompt_overrides") or {}
    versions = db.get("prompt_versions") or {}
    rows = []
    for name, info in PROMPT_REGISTRY.items():
        try:
            file_text = read_file_prompt(name)
        except FileNotFoundError:
            file_text = ""
        entry = overrides.get(name) if isinstance(overrides.get(name), dict) else None
        active_text = (
            entry["text"].strip()
            if entry and isinstance(entry.get("text"), str) and entry["text"].strip()
            else file_text
        )
        history = versions.get(name) or []
        rows.append({
            "id": name,
            "label": info["label"],
            "group": info["group"],
            "scope": info["scope"],
            "source": "user" if entry else "file",
            "hash": hash_text(active_text),
            "chars": len(active_text),
            "fileExists": bool(file_text),
            "updatedAt": (entry or {}).get("updatedAt"),
            "versionCount": len(history),
        })
    return rows


def get_prompt_detail(prompt_id: str) -> dict:
    """Full detail for one prompt: current text + full history. Raises KeyError if unknown."""
    if prompt_id not in PROMPT_REGISTRY:
        raise KeyError(prompt_id)
    db = _read_db_safe()
    overrides = db.get("prompt_overrides") or {}
    versions = db.get("prompt_versions") or {}
    try:
        file_text = read_file_prompt(prompt_id)
    except FileNotFoundError:
        file_text = ""
    entry = overrides.get(prompt_id) if isinstance(overrides.get(prompt_id), dict) else None
    active_text = (
        entry["text"].strip()
        if entry and isinstance(entry.get("text"), str) and entry["text"].strip()
        else file_text
    )
    history = versions.get(prompt_id) or []
    info = PROMPT_REGISTRY[prompt_id]
    return {
        "id": prompt_id,
        "label": info["label"],
        "group": info["group"],
        "scope": info["scope"],
        "source": "user" if entry else "file",
        "text": active_text,
        "fileText": file_text,
        "hash": hash_text(active_text),
        "updatedAt": (entry or {}).get("updatedAt"),
        "history": history,
    }
