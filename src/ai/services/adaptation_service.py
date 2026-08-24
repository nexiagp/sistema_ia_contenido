from __future__ import annotations

from src.ai.services.context_helpers import clip_text
from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, schema, transformer_prompt

X_LIMIT = 280

# Schema reducido para corregir SOLO el bloque X cuando supera el limite.
_X_ONLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "short_version": {"type": "string"},
        "alternative": {"type": "string"},
        "thread": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["short_version", "alternative", "thread"],
}

# Schema reducido para reescribir SOLO Facebook cuando es demasiado calcado de LinkedIn.
_FB_ONLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "final_post": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["final_post", "cta"],
}


class AdaptationService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def adapt(self, generation: dict, validation: dict, db: dict) -> tuple[dict, str | None]:
        canonical = validation.get("final_post") or ""
        if self.client.enabled:
            user = (
                "Adapta el post canonico validado de Nexia GP a X y Facebook.\n"
                f"Post canonico: {canonical}\n"
                f"CTA: {validation.get('cta')}\n"
                f"Hashtags: {validation.get('hashtags')}\n"
                f"Angulo: {(generation.get('strategy') or {}).get('core_angle', '')}\n"
                "No recuperes ni repitas borradores, notas ni trazas internas."
            )
            system = "\n\n".join(
                [
                    base_prompt(),
                    transformer_prompt("adaptacion_x"),
                    transformer_prompt("adaptacion_facebook"),
                ]
            )
            adaptations, response_id = self.client.responses_json(
                system=system,
                user=user,
                schema=schema("adaptation.schema.json"),
                schema_name="nexiagp_adaptations",
                model=db.get("settings", {}).get("model") or None,
            )
            adaptations = self._enforce_x_limits(adaptations, db)
            adaptations = self._enforce_facebook_distinct(adaptations, canonical, validation, db)
            return adaptations, response_id
        return self._fallback_adapt(validation), None

    def _enforce_x_limits(self, adaptations: dict, db: dict) -> dict:
        """Garantiza que cada pieza de X quepa en 280: re-prompt acotado y, si no, clip determinista."""
        x = dict((adaptations or {}).get("x") or {})

        def over(value) -> bool:
            return isinstance(value, str) and len(value) > X_LIMIT

        thread = x.get("thread") or []
        if not (over(x.get("short_version")) or over(x.get("alternative")) or any(over(t) for t in thread)):
            return adaptations

        if self.client.enabled:
            try:
                fixed, _ = self.client.responses_json(
                    system="\n\n".join([base_prompt(), transformer_prompt("adaptacion_x")]),
                    user=(
                        "Reescribe SOLO el bloque X para que CADA campo quepa en 280 caracteres, "
                        "manteniendo la idea central y con tono directo y afilado. Cuenta los caracteres.\n"
                        f"Bloque X actual (demasiado largo): {x}"
                    ),
                    schema=_X_ONLY_SCHEMA,
                    schema_name="nexiagp_x_fix",
                    model=db.get("settings", {}).get("model") or None,
                )
                if isinstance(fixed, dict):
                    x.update({k: v for k, v in fixed.items() if v})
            except Exception:
                pass

        # Red de seguridad determinista: nunca devolver una pieza > 280.
        x["short_version"] = clip_text(x.get("short_version", ""), X_LIMIT)
        x["alternative"] = clip_text(x.get("alternative", ""), X_LIMIT)
        x["thread"] = [clip_text(t, X_LIMIT) for t in (x.get("thread") or [])]
        adaptations["x"] = x
        return adaptations

    def _enforce_facebook_distinct(self, adaptations: dict, canonical: str, validation: dict, db: dict) -> dict:
        """Si Facebook es casi calco de LinkedIn, lo reescribe una vez para diferenciarlo de verdad."""
        fb = dict((adaptations or {}).get("facebook") or {})
        fb_text = fb.get("final_post") or ""
        if not fb_text or self._similarity(fb_text, canonical) < 0.72:
            return adaptations
        if self.client.enabled:
            try:
                fixed, _ = self.client.responses_json(
                    system="\n\n".join([base_prompt(), transformer_prompt("adaptacion_facebook")]),
                    user=(
                        "La version de Facebook esta demasiado calcada del post de LinkedIn. "
                        "Reescribela de verdad: abre con un gancho DISTINTO (no reutilices la primera frase de LinkedIn), "
                        "funde los parrafos en 2-3 bloques mas divulgativos y cierra con una CTA visible. "
                        "No debe compartir frases literales con el original.\n"
                        f"Post LinkedIn (NO copiar literal): {canonical}\n"
                        f"CTA disponible: {validation.get('cta')}"
                    ),
                    schema=_FB_ONLY_SCHEMA,
                    schema_name="nexiagp_fb_fix",
                    model=db.get("settings", {}).get("model") or None,
                )
                if isinstance(fixed, dict) and fixed.get("final_post"):
                    if self._similarity(fixed["final_post"], canonical) < self._similarity(fb_text, canonical):
                        fb.update({k: v for k, v in fixed.items() if v})
                        adaptations["facebook"] = fb
            except Exception:
                pass
        return adaptations

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Jaccard sobre palabras significativas (>3 letras). 0 = nada en comun, 1 = identicos."""
        def tokens(text: str) -> set:
            cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in (text or ""))
            return {word for word in cleaned.split() if len(word) > 3}

        ta, tb = tokens(a), tokens(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    @staticmethod
    def _fallback_adapt(validation: dict) -> dict:
        post = validation.get("final_post", "")
        paragraphs = [part.strip() for part in post.split("\n\n") if part.strip()]
        hook = paragraphs[0] if paragraphs else post[:180]
        thesis = paragraphs[1] if len(paragraphs) > 1 else "El desarrollo comercial necesita criterio de canal, no solo producto."
        x_short = f"{hook}\n\n{thesis[:190]}"
        thread = [hook, thesis[:240], "En Canarias, el encaje comercial se construye con red local, soporte y continuidad."]
        facebook = "\n\n".join(
            [
                hook,
                "La idea es sencilla: crecer en un mercado como Canarias requiere entender el canal, acompanar la implantacion y trabajar con criterio B2B.",
                validation.get("cta") or "Si tiene sentido para tu empresa, podemos abrir conversacion.",
            ]
        )
        return {
            "x": {
                "short_version": clip_text(x_short, X_LIMIT),
                "alternative": clip_text(
                    "Entrar en un mercado no es solo llegar. Es entender el canal, sostener la operativa y construir confianza.",
                    X_LIMIT,
                ),
                "thread": [clip_text(piece, X_LIMIT) for piece in thread[:3]],
            },
            "facebook": {
                "final_post": facebook,
                "cta": validation.get("cta", ""),
            },
        }
