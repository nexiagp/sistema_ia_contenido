from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


CHOCOLATE = (58, 31, 14)  # #3a1f0e
ROOT = Path(__file__).resolve().parents[3]
BRAND_LOGO_PATH = ROOT / "Imágenes" / "Logo NGP.png"


def compose_branded_frame(
    src_path: Path,
    dest_path: Path,
    padding_ratio: float = 0.04,
    blur_radius: int = 38,
    line_width: int = 2,
    line_color: tuple[int, int, int] = CHOCOLATE,
    logo_path: Path | None = None,
    logo_width_ratio: float = 0.16,
    logo_margin_ratio: float = 0.035,
) -> Path:
    """
    Compose a frame around the image:
    - Background: a slightly zoomed, heavily blurred version of the same image
    - Foreground: the original sharp image, centered, with a thin chocolate outline
    - The blurred strip is `padding_ratio` of the longer side, on each side.
    - The approved logo is composited locally, after generation, so its shape
      and legibility never depend on an image model or a CDN transformation.
    """
    with Image.open(src_path) as source:
        img = source.convert("RGB")
    w, h = img.size
    pad = int(round(max(w, h) * padding_ratio))
    new_w, new_h = w + 2 * pad, h + 2 * pad

    # Background: same image scaled to cover the new canvas, then blurred
    bg = img.copy()
    # Scale to cover (slight zoom so blurred edges don't show gaps)
    scale = max(new_w / w, new_h / h) * 1.04
    bg_w, bg_h = int(w * scale), int(h * scale)
    bg = bg.resize((bg_w, bg_h), Image.LANCZOS)
    # Crop to canvas centered
    left = (bg_w - new_w) // 2
    top = (bg_h - new_h) // 2
    bg = bg.crop((left, top, left + new_w, top + new_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Paste sharp original onto centered position
    bg.paste(img, (pad, pad))

    # Draw chocolate line as the frame separator
    draw = ImageDraw.Draw(bg)
    draw.rectangle(
        [pad - 1, pad - 1, pad + w, pad + h],
        outline=line_color,
        width=line_width,
    )

    # Put the logo on the final local asset, not in the image-generation prompt
    # and not in a Cloudinary transformation. This is deterministic: if the
    # branded asset cannot be applied, no unbranded "with frame" image exists.
    resolved_logo_path = logo_path or BRAND_LOGO_PATH
    if not resolved_logo_path.is_file():
        raise FileNotFoundError(f"No se encontró el logotipo de marca: {resolved_logo_path}")
    with Image.open(resolved_logo_path) as logo_source:
        logo = logo_source.convert("RGBA")
    logo_target_width = max(96, int(new_w * logo_width_ratio))
    logo_target_height = max(1, int(logo.height * (logo_target_width / logo.width)))
    logo.thumbnail((logo_target_width, logo_target_height), Image.LANCZOS)
    margin = max(18, int(new_w * logo_margin_ratio))
    position = (new_w - logo.width - margin, new_h - logo.height - margin)
    composed = bg.convert("RGBA")
    composed.alpha_composite(logo, dest=position)

    # Write the branded result atomically. A partially written composite must
    # never become the image that the editor or Cloudinary can serve.
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest_path.with_name(f"{dest_path.name}.tmp")
    try:
        composed.convert("RGB").save(temporary, format="PNG", optimize=True)
        with Image.open(temporary) as output:
            output.verify()
        temporary.replace(dest_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return dest_path
