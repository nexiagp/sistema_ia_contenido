"""Offline contract tests for the editor-facing visual direction controls."""
from __future__ import annotations

import unittest

from src.domain.visual import (
    COMPOSITIONS,
    DEFAULT_COMPOSITION,
    DEFAULT_DIRECTION,
    IMAGE_FORMATS,
    VISUAL_DIRECTIONS,
    normalize_visual_choice,
    public_visual_options,
    visual_direction_prompt,
)


class VisualDirectionTests(unittest.TestCase):
    def test_unknown_choices_fall_back_to_editorial_defaults(self) -> None:
        self.assertEqual(
            normalize_visual_choice("not-a-direction", "not-a-composition"),
            (DEFAULT_DIRECTION, DEFAULT_COMPOSITION),
        )

    def test_all_public_choices_are_backed_by_a_prompt_instruction(self) -> None:
        options = public_visual_options()
        self.assertEqual(set(options["directions"]), set(VISUAL_DIRECTIONS))
        self.assertEqual(set(options["compositions"]), set(COMPOSITIONS))
        self.assertEqual(set(options["formats"]), set(IMAGE_FORMATS))
        prompt = visual_direction_prompt("criterio_experto", "detalle_de_accion", with_frame=True)
        self.assertIn("Criterio experto", prompt)
        self.assertIn("Detalle de acción", prompt)
        self.assertIn("Do not use maps, diagrams, charts", prompt)
        self.assertIn("lower-right 18%", prompt)

    def test_unframed_images_do_not_reserve_logo_area(self) -> None:
        prompt = visual_direction_prompt("operacion_real", "contexto_amplio", with_frame=False)
        self.assertIn("no logo is generated", prompt)
        self.assertNotIn("lower-right 18% visually calm", prompt)


if __name__ == "__main__":
    unittest.main()
