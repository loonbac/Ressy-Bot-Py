#!/usr/bin/env python3
"""Renderiza splash/splash.html a video-worker/splash.mp4.

La animación de carga de RessyTube es HTML/CSS (blobs, partículas, anillos,
título con shimmer). Como el worker ya no usa navegador en runtime, la
pre-renderizamos UNA vez a un mp4 que ffmpeg reproduce como splash.

Requiere: Playwright + Chromium y ffmpeg.
    uv run playwright install chromium     # si falta el navegador
    uv run python video-worker/splash/render.py

Regenerar tras editar splash.html, y commitear el splash.mp4 resultante.
"""
from __future__ import annotations

import asyncio
import glob
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "splash.html")
OUT = os.path.normpath(os.path.join(HERE, "..", "splash.mp4"))
WIDTH, HEIGHT, SECONDS = 1280, 720, 8


async def _record(raw_dir: str) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--no-sandbox", "--disable-gpu", "--force-color-profile=srgb"]
        )
        ctx = await browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=raw_dir,
            record_video_size={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        await page.goto(f"file://{HTML}")
        await page.wait_for_timeout((SECONDS + 1) * 1000)
        await ctx.close()  # flushea el webm
        await browser.close()
    return glob.glob(os.path.join(raw_dir, "*.webm"))[0]


def main() -> None:
    with tempfile.TemporaryDirectory() as raw_dir:
        webm = asyncio.run(_record(raw_dir))
        # Saltar el primer ~0.6s (warmup en blanco) y encodear a h264 compacto.
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", "0.6", "-i", webm, "-t", str(SECONDS), "-an",
                "-vf", f"fps=30,scale={WIDTH}:{HEIGHT}:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "slow", "-crf", "22",
                "-movflags", "+faststart", "-y", OUT,
            ],
            check=True,
        )
    print(f"escrito: {OUT}")


if __name__ == "__main__":
    main()
