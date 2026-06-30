from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


CHOCOLATE = (58, 31, 14)  # #3a1f0e


def compose_branded_frame(
    src_path: Path,
    dest_path: Path,
    padding_ratio: float = 0.04,
    blur_radius: int = 38,
    line_width: int = 2,
    line_color: tuple[int, int, int] = CHOCOLATE,
) -> Path:
    """
    Compose a frame around the image:
    - Background: a slightly zoomed, heavily blurred version of the same image
    - Foreground: the original sharp image, centered, with a thin chocolate outline
    - The blurred strip is `padding_ratio` of the longer side, on each side.
    """
    img = Image.open(src_path).convert("RGB")
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

    bg.save(dest_path, format="PNG", optimize=True)
    return dest_path
