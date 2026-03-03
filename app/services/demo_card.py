from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def _fit_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Центр-кроп под нужное соотношение сторон + ресайз."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    if src_ratio > tgt_ratio:
        # слишком широкий — обрезаем по ширине
        new_w = int(src_h * tgt_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        # слишком высокий — обрезаем по высоте
        new_h = int(src_w / tgt_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = (" ".join(cur + [w])).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines

def make_demo_card(
    photo_bytes: bytes,
    user_phrase: str,
    fixed_line: str,
    fmt: str,  # "3:4" или "4:3"
) -> bytes:
    img = Image.open(BytesIO(photo_bytes)).convert("RGB")

    # Размеры под формат (Telegram нормально принимает такие)
    if fmt == "3:4":
        W, H = 900, 1200
    else:
        W, H = 1200, 900

    img = _fit_crop(img, W, H)

    # Полупрозрачный блок под текст
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    pad = int(min(W, H) * 0.05)
    block_h = int(H * 0.28)
    y0 = H - block_h - pad
    y1 = H - pad

    odraw.rounded_rectangle(
        (pad, y0, W - pad, y1),
        radius=30,
        fill=(0, 0, 0, 140),
    )

    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    draw = ImageDraw.Draw(img_rgba)

    # Шрифт: пробуем системный, иначе дефолтный
    try:
        font_big = ImageFont.truetype("DejaVuSans.ttf", size=int(H * 0.05))
        font_small = ImageFont.truetype("DejaVuSans.ttf", size=int(H * 0.04))
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    max_w = W - 2 * pad - 40
    phrase_lines = _wrap_text(draw, user_phrase, font_big, max_w=max_w)
    fixed_lines = _wrap_text(draw, fixed_line, font_small, max_w=max_w)

    # Рисуем по центру блока
    cur_y = y0 + 30
    for line in phrase_lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_big)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, cur_y), line, font=font_big, fill=(255, 255, 255, 255))
        cur_y += int(H * 0.06)

    cur_y += 10
    for line in fixed_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, cur_y), line, font=font_small, fill=(255, 255, 255, 230))
        cur_y += int(H * 0.05)

    out = BytesIO()
    img_rgba.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
