from __future__ import annotations

import json
import re
from typing import Any

from .models import SecurityAnalysis


BLOCK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"/etc/passwd",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"fork\s*\(\s*\)",
]


def local_security_analysis(code: str) -> dict[str, Any]:
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, code, flags=re.IGNORECASE):
            return {
                "malicious": True,
                "severity": "critical",
                "reasons": ["El código contiene una operación peligrosa y fue bloqueado antes de ejecutarse."],
            }
    return {"malicious": False, "severity": "low", "reasons": []}


def local_security_check(code: str) -> tuple[bool, str]:
    analysis = local_security_analysis(code)
    if analysis["malicious"] and analysis["severity"] in {"high", "critical"}:
        return False, analysis["reasons"][0]
    return True, "ok"


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    # 1. Quitar bloque de razonamiento <think>...</think> de modelos MiniMax.
    text = _THINK_BLOCK_RE.sub("", text).strip()
    # 2. Quitar fences markdown ```json ... ```.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def parse_security_analysis(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        data: Any = raw
    else:
        cleaned = _strip_json_fence(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Último recurso: extraer el primer objeto {...} embebido en texto.
            match = _JSON_OBJECT_RE.search(cleaned)
            if match is None:
                raise
            data = json.loads(match.group(0))
    parsed = SecurityAnalysis.model_validate(data)
    return parsed.model_dump()


async def _call_security_ai(ai_chat: Any, code: str, language: str, model: str) -> str | dict[str, Any]:
    if hasattr(ai_chat, "analyze_code_security"):
        return await ai_chat.analyze_code_security(code, language, model)
    client = getattr(ai_chat, "client", None)
    chat = getattr(client, "chat", None)
    if callable(chat):
        prompt = (
            "Analiza seguridad PRE-EJECUCIÓN de este código. Devuelve SOLO JSON válido con: "
            "malicious:boolean, severity:'low'|'medium'|'high'|'critical', reasons:string[]. "
            "Marca high/critical si intenta borrar archivos, exfiltrar secretos, persistencia, red ofensiva, fork bomb o daño al sistema.\n"
            f"Lenguaje: {language}\nCódigo:\n```{language}\n{code}\n```"
        )
        return await chat(
            [
                {"role": "system", "content": "Eres un analizador de seguridad de código. Responde únicamente JSON."},
                {"role": "user", "content": prompt},
            ],
            model,
            temperature=0,
            max_completion_tokens=700,
        )
    # Último recurso para mocks/clientes antiguos: no inventa severidad, solo usa análisis textual existente.
    if hasattr(ai_chat, "analyze_code_execution"):
        analysis = await ai_chat.analyze_code_execution(code, language, "", "", model)  # type: ignore[misc]
        text = f"{analysis.get('purpose', '')} {' '.join(analysis.get('improvements', []))}".lower()
        if "peligroso" in text or "malicioso" in text:
            return {"malicious": True, "severity": "high", "reasons": ["La IA marcó el código como riesgoso."]}
        return {"malicious": False, "severity": "low", "reasons": []}
    raise RuntimeError("Cliente IA sin interfaz de análisis de seguridad")


async def structured_security_analysis(
    ai_chat: Any,
    code: str,
    language: str,
    *,
    enabled: bool,
    model: str,
) -> dict[str, Any]:
    local = local_security_analysis(code)
    if local["malicious"] and local["severity"] in {"high", "critical"}:
        return local
    if not enabled:
        return local
    if ai_chat is None:
        raise RuntimeError("El análisis IA de seguridad está habilitado, pero ai_chat no está disponible.")
    last_error: Exception | None = None
    for _ in range(2):
        try:
            return parse_security_analysis(await _call_security_ai(ai_chat, code, language, model))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"No se pudo interpretar el análisis IA de seguridad tras 2 intentos: {last_error}")


async def analyze_security_with_ai(ai_chat, code: str, language: str) -> tuple[bool, str]:
    analysis = await structured_security_analysis(ai_chat, code, language, enabled=ai_chat is not None, model="MiniMax-M2.7")
    if analysis["severity"] in {"high", "critical"} and analysis["malicious"]:
        return False, " ".join(analysis["reasons"]) or "El análisis de seguridad bloqueó el código."
    return True, "ok"


def extract_code_block(content: str) -> tuple[str, str] | None:
    match = re.search(r"```(?P<lang>[\w#+.-]*)\n(?P<code>.*?)```", content, flags=re.DOTALL)
    if not match:
        return None
    return (match.group("code").strip(), match.group("lang") or "python")


# Heurística para detectar código sin triple backticks. Devuelve (code, language)
# o None. Usado solo dentro de canales de sesión code_runner: si el usuario manda
# un mensaje "que parece código", se ejecuta directo sin requerir fence.
_CODE_PATTERNS: list[tuple[str, str]] = [
    # Python
    (r"^\s*(?:def|class|import|from)\s+\w", "python"),
    (r"^\s*print\s*\(", "python"),
    (r"if\s+__name__\s*==", "python"),
    (r"^\s*async\s+def\s+\w", "python"),
    # JavaScript / TypeScript
    (r"^\s*(?:function|const|let|var)\s+\w", "javascript"),
    (r"console\.(?:log|error|warn|info)\s*\(", "javascript"),
    (r"^\s*(?:export|import)\s+(?:default\s+)?[\w{*]", "typescript"),
    (r"=>\s*[{(]", "javascript"),
    (r"^\s*interface\s+\w", "typescript"),
    (r":\s*(?:string|number|boolean|void)\b", "typescript"),
    # Bash
    (r"^#!\s*/(?:usr/)?bin/(?:bash|sh|zsh)", "bash"),
    (r"^\s*echo\s+", "bash"),
    (r"\$\([\w\s'\".-]+\)", "bash"),
    # Rust / Go / C
    (r"^\s*fn\s+\w+\s*\(", "rust"),
    (r"^\s*package\s+\w+", "go"),
    (r"^\s*func\s+\w+\s*\(", "go"),
    (r"^\s*#include\s*<", "cpp"),
    (r"^\s*public\s+(?:static\s+)?(?:void|class)\s+", "java"),
]


def looks_like_code(text: str) -> tuple[str, str] | None:
    """Detecta si un texto plano parece código y devuelve (code, language)."""
    if not text or not text.strip():
        return None
    stripped = text.strip()
    # Mensajes muy cortos (saludos, preguntas) NO son código aunque matcheen.
    if len(stripped) < 12:
        return None
    # Si tiene signos de pregunta natural al final → probablemente lenguaje natural.
    last_line = stripped.splitlines()[-1].strip()
    if last_line.endswith("?") or last_line.endswith("¿") or stripped.startswith("¿"):
        return None
    # Cuenta de pistas técnicas. >=2 patrones distintos = código casi seguro.
    hits: dict[str, int] = {}
    for pattern, lang in _CODE_PATTERNS:
        if re.search(pattern, stripped, flags=re.MULTILINE):
            hits[lang] = hits.get(lang, 0) + 1
    if not hits:
        # Fallback ultra-básico: si tiene punto-y-coma + llaves y >2 líneas, JS/TS.
        if re.search(r";\s*$", stripped, flags=re.MULTILINE) and stripped.count("\n") >= 2 and "{" in stripped:
            return stripped, "javascript"
        return None
    # Si la suma de pistas es demasiado baja para texto largo, es ambiguo.
    total_hits = sum(hits.values())
    if total_hits < 2 and len(stripped) > 200:
        return None
    # Lenguaje con más matches gana.
    best_lang = max(hits.items(), key=lambda kv: kv[1])[0]
    return stripped, best_lang
