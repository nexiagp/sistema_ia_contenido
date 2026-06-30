from __future__ import annotations

from src.ai.services.openai_client import OpenAIClient
from src.ai.services.prompt_service import base_prompt, schema, validator_prompt
from src.domain.editorial import RISK_FLAGS


class ValidatorService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def validate(self, request: dict, brief: dict, retrieval: dict, generation: dict, db: dict) -> tuple[dict, str | None]:
        if self.client.enabled:
            try:
                user = (
                    "Valida y corrige esta pieza para Nexia GP.\n"
                    f"Solicitud: {request}\nBrief: {brief}\nContexto: {retrieval}\nPieza: {generation}"
                )
                return self.client.responses_json(
                    system=f"{base_prompt()}\n\n{validator_prompt()}",
                    user=user,
                    schema=schema("validation.schema.json"),
                    schema_name="nexiagp_validation",
                    model=db.get("settings", {}).get("model") or None,
                )
            except Exception:
                return self._fallback_validate(brief, retrieval, generation), None
        return self._fallback_validate(brief, retrieval, generation), None

    @staticmethod
    def _fallback_validate(brief: dict, retrieval: dict, generation: dict) -> dict:
        copy = generation.get("copy", {})
        final_post = copy.get("final_post", "")
        flags = []
        notes = []
        if retrieval.get("confidence") == "low":
            flags.append("unsupported_claim_risk")
            notes.append("Contexto documental limitado; mantener afirmaciones generales.")
        if len(final_post.split()) > 280:
            notes.append("El texto puede acortarse para LinkedIn.")
        if any(word in final_post.lower() for word in ["lider absoluto", "garantiza", "infalible", "revolucion"]):
            flags.append("brand_overpromotion_risk")
            notes.append("Se detectaron posibles claims fuertes.")
        if brief.get("factual_sensitivity") == "high" and "unsupported_claim_risk" not in flags:
            notes.append("Sensibilidad factual alta: revisar nombres, marcas o actualidad antes de publicar.")
        return {
            "final_post": final_post,
            "cta": copy.get("cta", ""),
            "hashtags": copy.get("hashtags", []),
            "adjustments_made": ["Validacion editorial local aplicada."],
            "review_flags": [flag for flag in flags if flag in RISK_FLAGS],
            "risk_level": "high" if flags else "medium" if brief.get("human_review_level") == "high" else "low",
            "human_review_required": bool(flags) or brief.get("human_review_level") == "high",
            "validation_notes": notes,
        }
