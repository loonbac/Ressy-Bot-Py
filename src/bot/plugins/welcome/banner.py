"""Composite welcome banner — avatar + name overlaid on background image."""
from __future__ import annotations

import io
import os
from typing import Iterable

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BANNER_W = 1100
BANNER_H = 360
AVATAR_SIZE = 240
AVATAR_RING = 8
PADDING = 50

_TITLE_FONT_CANDIDATES = (
    "/usr/share/fonts/noto/NotoSans-Black.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)

_BODY_FONT_CANDIDATES = (
    "/usr/share/fonts/noto/NotoSans-SemiBold.ttf",
    "/usr/share/fonts/noto/NotoSans-Medium.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _load_font(candidates: Iterable[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


async def _fetch_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "RessyBot/1.0"})
            resp.raise_for_status()
            return resp.content
    except Exception:
        return None


def _crop_to_fill(img: Image.Image, width: int, height: int) -> Image.Image:
    target_ratio = width / height
    src_ratio = img.width / img.height
    if src_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        offset = (img.width - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        offset = (img.height - new_h) // 2
        img = img.crop((0, offset, img.width, offset + new_h))
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _circular_avatar(avatar_img: Image.Image, size: int) -> Image.Image:
    avatar = avatar_img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar, (0, 0), mask)
    return out


def _hex_to_rgb(color: int) -> tuple[int, int, int]:
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


async def generate_welcome_banner(
    *,
    avatar_url: str,
    username: str,
    title_text: str = "BIENVENIDO/A",
    background_url: str = "",
    accent_color: int = 0x23856B,
) -> bytes:
    """Compose welcome banner and return PNG bytes."""
    # 1. Background
    bg_bytes = await _fetch_bytes(background_url)
    if bg_bytes:
        try:
            bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
            bg = _crop_to_fill(bg, BANNER_W, BANNER_H)
        except Exception:
            bg = None
    else:
        bg = None
    if bg is None:
        bg = Image.new("RGBA", (BANNER_W, BANNER_H), (26, 28, 26, 255))

    # 2. Dark gradient overlay (left-side darker for text readability)
    gradient = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)
    for x in range(BANNER_W):
        alpha = int(140 * (1 - min(1.0, x / (BANNER_W * 0.85))))
        grad_draw.line([(x, 0), (x, BANNER_H)], fill=(0, 0, 0, alpha))
    bg = Image.alpha_composite(bg, gradient)

    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas)

    # 3. Avatar with colored ring
    avatar_bytes = await _fetch_bytes(avatar_url)
    if avatar_bytes:
        try:
            avatar_src = Image.open(io.BytesIO(avatar_bytes))
        except Exception:
            avatar_src = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (90, 90, 90, 255))
    else:
        avatar_src = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (90, 90, 90, 255))

    avatar = _circular_avatar(avatar_src, AVATAR_SIZE)
    ring_size = AVATAR_SIZE + AVATAR_RING * 2

    # Draw ring (full circle behind avatar) + soft outer glow
    ring_layer = Image.new("RGBA", (ring_size + 40, ring_size + 40), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(ring_layer)
    accent_rgb = _hex_to_rgb(accent_color)
    glow_draw.ellipse(
        (20, 20, ring_size + 20, ring_size + 20),
        fill=(*accent_rgb, 255),
    )
    ring_layer = ring_layer.filter(ImageFilter.GaussianBlur(2))

    avatar_x = PADDING
    avatar_y = (BANNER_H - AVATAR_SIZE) // 2
    canvas.paste(ring_layer, (avatar_x - AVATAR_RING - 20, avatar_y - AVATAR_RING - 20), ring_layer)
    canvas.paste(avatar, (avatar_x, avatar_y), avatar)

    # 4. Text block — anchored top-left, positioned right of avatar
    text_x = avatar_x + AVATAR_SIZE + 50
    title_font = _load_font(_TITLE_FONT_CANDIDATES, 80)
    name_font = _load_font(_BODY_FONT_CANDIDATES, 50)

    line_gap = 18
    title_h = int(title_font.size * 1.05)
    name_h = int(name_font.size * 1.05)
    block_h = title_h + line_gap + name_h
    y0 = (BANNER_H - block_h) // 2

    # Title with subtle shadow
    draw.text(
        (text_x + 3, y0 + 3),
        title_text,
        font=title_font,
        fill=(0, 0, 0, 200),
        anchor="lt",
    )
    draw.text(
        (text_x, y0),
        title_text,
        font=title_font,
        fill=(255, 255, 255, 255),
        anchor="lt",
    )

    # Username (single line, accent color)
    y1 = y0 + title_h + line_gap
    draw.text(
        (text_x + 2, y1 + 2),
        username,
        font=name_font,
        fill=(0, 0, 0, 200),
        anchor="lt",
    )
    draw.text(
        (text_x, y1),
        username,
        font=name_font,
        fill=(*accent_rgb, 255),
        anchor="lt",
    )

    # 5. Export PNG bytes
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
