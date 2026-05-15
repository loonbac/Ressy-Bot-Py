from __future__ import annotations

import html
import time
from pathlib import Path
from typing import Any


async def export_transcript(channel: Any, output_dir: str = "data/plugins/code_runner_transcripts") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"transcript-{getattr(channel, 'id', 'unknown')}-{int(time.time())}.html"
    try:
        import chat_exporter  # type: ignore

        transcript = await chat_exporter.export(channel)
        if transcript:
            path.write_text(transcript, encoding="utf-8")
            return str(path)
    except Exception:
        pass

    messages: list[str] = []
    history = getattr(channel, "history", None)
    if callable(history):
        async for msg in history(limit=None, oldest_first=True):
            author = html.escape(str(getattr(getattr(msg, "author", None), "display_name", "Usuario")))
            content = html.escape(str(getattr(msg, "content", "")))
            messages.append(f"<article><strong>{author}</strong><pre>{content}</pre></article>")
    body = "\n".join(messages) or "<p>Sin mensajes exportables.</p>"
    path.write_text(f"<!doctype html><html><meta charset='utf-8'><body>{body}</body></html>", encoding="utf-8")
    return str(path)
