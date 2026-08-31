from __future__ import annotations

from .openai_client import OpenAIClient
from src.domain.visual import (
    COMPOSITIONS,
    VISUAL_DIRECTIONS,
    normalize_visual_choice,
    visual_direction_prompt,
)


_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "image_prompt": {"type": "string"},
        "scene_rationale": {"type": "string"},
    },
    "required": ["image_prompt", "scene_rationale"],
}

_SYSTEM = """\
You are a professional art director and editorial photographer specializing in B2B content for LinkedIn.

Your task: read a LinkedIn post and generate a detailed English image prompt for gpt-image-2 that produces a TRULY PROFESSIONAL, PHOTOREALISTIC image that perfectly illustrates the post concept.

MANDATORY CRITERIA:
- Style: high-end editorial or documentary photography — never stock photo aesthetics
- The image must ILLUSTRATE the post's core IDEA or FEELING, not describe it literally
- Authentic scenes, real industry environments, genuine human moments
- Natural or professional studio lighting, real depth of field
- Specific, concrete scenes — not generic representations
- When the post context is Canary Islands: include relevant visual cues (volcanic landscape, Atlantic coastline, Mediterranean light, island architecture)
- No text, no logos, no brand elements anywhere in the image. Do not try to reproduce Nexia GP's logo: it is applied after generation by a deterministic brand compositor.
- Follow the supplied logo-safe-area instruction exactly: it only applies when the editor has activated a local Nexia brand treatment.
- Never solve a business concept with a map, diagram, chart, technical drawing, readable paperwork, collage or split screen. A photograph must work as a real scene before it works as an illustration.
- The selected visual role and composition are binding. They are creative decisions made by the editor, not optional inspiration.

STRICTLY AVOID (stock photo clichés):
- Forced handshakes between suited people
- Executives staring at laptops or pointing at screens
- Groups smiling around a conference table
- Generic blurred office backgrounds
- Fake "team collaboration" poses

PREFER INSTEAD:
- Real warehouse workers doing their actual job
- Industrial machinery in authentic operation
- Distribution trucks at a real loading dock at golden hour
- An actual B2B working exchange around a material sample, equipment or physical task
- Aerial drone shots of logistics infrastructure
- Close-up of hands operating equipment
- Real port or harbor activity in Canary Islands

PROMPT STRUCTURE:
[Specific concrete scene with action verb] · [Real industry setting/environment details] · [Photography style] · [Lighting description] · [Camera/lens aesthetic] · [Selected composition] · No text, no logos, no brand elements

Output ONLY the image_prompt (in English) and a brief scene_rationale (in Spanish, for the editor to understand your choice).
"""


class ImagePromptService:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def generate_prompt(
        self,
        post: dict,
        direction: object,
        composition: object,
        user_notes: str,
        *,
        with_branding: bool,
    ) -> tuple[dict, str | None]:
        generation = post.get("generation") or {}
        copy_obj = generation.get("copy") or {}
        support = generation.get("editorial_support") or {}
        brief = post.get("brief") or {}
        request = post.get("request") or {}

        final_post = copy_obj.get("final_post") or post.get("copy") or ""
        angle = brief.get("core_angle") or post.get("angle") or ""
        thesis = brief.get("core_thesis") or post.get("idea") or ""
        visual_brief = support.get("visual_brief") or ""
        sector = request.get("sector") or ""
        channel = request.get("canal") or post.get("platform") or "linkedin"

        direction_id, composition_id = normalize_visual_choice(direction, composition)
        parts = [
            f"POST ANGLE: {angle}" if angle else "",
            f"CORE THESIS: {thesis}" if thesis else "",
            f"SECTOR: {sector}" if sector else "",
            f"CHANNEL: {channel}",
            f"EDITORIAL VISUAL BRIEF: {visual_brief}" if visual_brief else "",
            "",
            "POST BODY (first 1200 chars):",
            final_post[:1200],
            "",
            f"SELECTED VISUAL ROLE: {VISUAL_DIRECTIONS[direction_id]['label']}",
            f"SELECTED COMPOSITION: {COMPOSITIONS[composition_id]['label']}",
            visual_direction_prompt(direction_id, composition_id, with_frame=with_branding),
            f"ADDITIONAL USER NOTES: {user_notes}" if user_notes and user_notes.strip() else "",
        ]
        user_input = "\n".join(p for p in parts if p is not None)

        result, response_id = self.client.responses_json(
            system=_SYSTEM,
            user=user_input,
            schema=_SCHEMA,
            schema_name="image_prompt_result",
        )
        return result, response_id
