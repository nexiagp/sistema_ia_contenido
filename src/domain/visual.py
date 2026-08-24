"""Product-owned visual direction for Nexia's editorial generator.

The image model still creates the pixels, but the application owns the
creative decision: what a visual should communicate, how it should be framed
and which export format is appropriate for its editorial use.
"""
from __future__ import annotations


IMAGE_FORMATS = {
    "1088x1360": {
        "label": "LinkedIn recomendado (4:5)",
        "description": "Más presencia vertical en el feed sin llegar a formato story.",
        "width": 1088,
        "height": 1360,
        "use": "post_social",
    },
    "1536x1024": {
        "label": "Editorial horizontal (3:2)",
        "description": "Escena amplia para puertos, distribución, showroom o equipo.",
        "width": 1536,
        "height": 1024,
        "use": "post_social",
    },
    "1024x1024": {
        "label": "Cuadrado (1:1)",
        "description": "Formato versátil para adaptaciones y composiciones centradas.",
        "width": 1024,
        "height": 1024,
        "use": "post_social",
    },
    "1024x1536": {
        "label": "Vertical narrativo (2:3)",
        "description": "Adecuado cuando una persona, proceso o detalle necesita altura.",
        "width": 1024,
        "height": 1536,
        "use": "post_social",
    },
    "2048x1152": {
        "label": "Cabecera de blog (16:9)",
        "description": "Panorámica limpia para abrir un artículo sin simular una infografía.",
        "width": 2048,
        "height": 1152,
        "use": "blog",
    },
}


VISUAL_DIRECTIONS = {
    "operacion_real": {
        "label": "Operación real",
        "description": "Una acción concreta que demuestra cómo se mueve el negocio.",
        "instruction": (
            "Show a credible operation in progress: a real task, real equipment or materials, "
            "and one coherent moment of work. People, if present, are working naturally rather "
            "than posing for the camera."
        ),
    },
    "criterio_experto": {
        "label": "Criterio experto",
        "description": "Un profesional tomando una decisión o comprobando algo relevante.",
        "instruction": (
            "Show expertise through an authentic decision or inspection in context. Prefer a "
            "natural gesture, materials and environment over screens, staged meetings or readable documents."
        ),
    },
    "territorio_infraestructura": {
        "label": "Territorio e infraestructura",
        "description": "La escala de Canarias, el canal o la logística se entiende de un vistazo.",
        "instruction": (
            "Show real Canary Islands territory, port, warehouse, road, industrial or commercial "
            "infrastructure as a physical context. The scene must be geographically plausible and never use a map."
        ),
    },
    "producto_en_uso": {
        "label": "Producto en uso",
        "description": "Materiales, solución o equipo en un contexto B2B creíble, sin catálogo artificial.",
        "instruction": (
            "Show a product, material or tool in credible professional use. Avoid packshot treatment, "
            "invented labels and unnecessary branded packaging; focus on material, utility and environment."
        ),
    },
    "relacion_de_canal": {
        "label": "Relación de canal",
        "description": "Una interacción comercial verosímil, sobria y orientada al trabajo.",
        "instruction": (
            "Show a small, authentic B2B working interaction around a real object, sample or task. "
            "Avoid handshakes, smiles to camera, presentation poses and generic office collaboration."
        ),
    },
}


COMPOSITIONS = {
    "contexto_amplio": {
        "label": "Contexto amplio",
        "description": "Una escena completa, con entorno y escala suficientes para entenderla.",
        "instruction": "Wide editorial composition with a single clear subject and environmental context.",
    },
    "altura_humana": {
        "label": "A la altura del trabajo",
        "description": "Mirada documental cercana, sin teatralidad.",
        "instruction": "Eye-level observational composition with natural depth and an unforced point of view.",
    },
    "detalle_de_accion": {
        "label": "Detalle de acción",
        "description": "Manos, materiales o proceso cuando el gesto aporta más que la escena completa.",
        "instruction": (
            "Tight but spacious action detail. Show only anatomically natural hands when needed; "
            "do not include papers, maps, drawings or unreadable text as props."
        ),
    },
    "perspectiva_alta": {
        "label": "Perspectiva alta",
        "description": "Escala de instalación, territorio o flujo físico, sin convertirlo en un diagrama.",
        "instruction": "High-angle or aerial documentary composition, geographically and operationally plausible, never diagrammatic.",
    },
}


DEFAULT_DIRECTION = "operacion_real"
DEFAULT_COMPOSITION = "contexto_amplio"


def normalize_visual_choice(direction: object, composition: object) -> tuple[str, str]:
    normalized_direction = str(direction or "").strip()
    normalized_composition = str(composition or "").strip()
    if normalized_direction not in VISUAL_DIRECTIONS:
        normalized_direction = DEFAULT_DIRECTION
    if normalized_composition not in COMPOSITIONS:
        normalized_composition = DEFAULT_COMPOSITION
    return normalized_direction, normalized_composition


def visual_direction_prompt(direction: object, composition: object, *, with_frame: bool) -> str:
    """Return the non-negotiable visual brief passed to the image prompt."""
    direction_id, composition_id = normalize_visual_choice(direction, composition)
    frame_note = (
        "Keep the lower-right 18% visually calm and free of subjects, signs and high-contrast detail; "
        "the approved Nexia GP logo is composited there after generation."
        if with_frame
        else "Use the full frame naturally; no logo is generated into the image."
    )
    return "\n".join(
        [
            f"VISUAL ROLE — {VISUAL_DIRECTIONS[direction_id]['label']}: {VISUAL_DIRECTIONS[direction_id]['instruction']}",
            f"COMPOSITION — {COMPOSITIONS[composition_id]['label']}: {COMPOSITIONS[composition_id]['instruction']}",
            "Do not use maps, diagrams, charts, plans, documents, readable text, signage, multiple scenes or collage layouts.",
            frame_note,
        ]
    )


def public_visual_options() -> dict:
    """A deliberately small, editor-friendly set of visual choices for the UI."""
    return {
        "directions": {
            key: {"label": value["label"], "description": value["description"]}
            for key, value in VISUAL_DIRECTIONS.items()
        },
        "compositions": {
            key: {"label": value["label"], "description": value["description"]}
            for key, value in COMPOSITIONS.items()
        },
        "formats": {
            key: {
                "label": value["label"],
                "description": value["description"],
                "use": value["use"],
            }
            for key, value in IMAGE_FORMATS.items()
        },
    }
