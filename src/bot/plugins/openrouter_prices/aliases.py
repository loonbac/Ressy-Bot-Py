"""Fuzzy matching y resolución de aliases entre fuentes externas y OpenRouter.

Usa difflib.SequenceMatcher (stdlib) — sin dependencias adicionales.
Threshold default: 0.75.

Normalización agresiva antes de matchear:
- Strip prefijos "Provider: " típicos de OpenRouter names
- Lowercase, sin paréntesis (variantes), sin puntuación común
- Match contra MÚLTIPLES claves del modelo OpenRouter:
  * name
  * id (con y sin prefijo provider/)
  * canonical_slug si existe
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Regex para limpiar variantes (Latest), (Beta), (Free), (Thinking), etc.
_PARENS_RE = re.compile(r"\([^)]*\)")
# Regex para puntuación y separadores → espacio
_SEP_RE = re.compile(r"[\-_./:]+")
# Espacios múltiples
_MULTI_SPACE_RE = re.compile(r"\s+")
# Prefijos "Provider: " en nombres de OpenRouter
_PROVIDER_PREFIX_RE = re.compile(
    r"^(anthropic|openai|google|deepseek|meta|meta-?llama|mistralai|qwen|cohere|x-?ai|xai|"
    r"perplexity|databricks|amazon|nous|microsoft|nvidia|alibaba|xiaomi|"
    r"zhipuai|nebius|liquid|inception)\s*:?\s*",
    re.IGNORECASE,
)
# Sufijos comunes que no aportan a la identidad del modelo
_SUFFIX_NOISE_RE = re.compile(
    r"\b(instruct|chat|base|preview|free|thinking|latest|fc|nightly|"
    r"experimental|beta|stable|hf|v\d{8}|\d{8})\b",
    re.IGNORECASE,
)


def _normalize(text: str, strip_provider: bool = False) -> str:
    """Normaliza un nombre para fuzzy matching.

    - Lower
    - Quita paréntesis con su contenido
    - Opcionalmente quita prefijo "Provider: " o "provider/"
    - Reemplaza guiones/underscores/puntos/slashes por espacios
    - Quita sufijos comunes (instruct, chat, preview, ...)
    - Colapsa espacios múltiples
    - Trim
    """
    s = text.lower().strip()
    s = _PARENS_RE.sub(" ", s)
    if strip_provider:
        s = _PROVIDER_PREFIX_RE.sub("", s)
    s = _SEP_RE.sub(" ", s)
    s = _SUFFIX_NOISE_RE.sub(" ", s)
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    return s


def _variants(text: str) -> list[str]:
    """Genera variantes normalizadas de un nombre para maximizar match coverage."""
    out: list[str] = []
    seen: set[str] = set()
    for variant in (_normalize(text, strip_provider=False), _normalize(text, strip_provider=True)):
        if variant and variant not in seen:
            out.append(variant)
            seen.add(variant)
    return out


def fuzzy_match(
    target: str,
    candidates: list[str],
    threshold: float = 0.75,
) -> tuple[str | None, float]:
    """Compara target contra candidates usando SequenceMatcher con normalización.

    Args:
        target: Nombre externo a buscar.
        candidates: Lista de nombres OpenRouter (originales, sin normalizar).
        threshold: Ratio mínimo para considerar match.

    Returns:
        (best_match, ratio) — best_match es el string ORIGINAL del candidate
        (no normalizado) para que el caller pueda lookup correcto en su dict.
    """
    if not candidates:
        return None, 0.0

    target_variants = _variants(target)
    if not target_variants:
        return None, 0.0

    best_match: str | None = None
    best_ratio: float = 0.0

    for candidate in candidates:
        cand_variants = _variants(candidate)
        for tv in target_variants:
            for cv in cand_variants:
                if tv == cv:
                    return candidate, 1.0
                ratio = SequenceMatcher(None, tv, cv).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = candidate

    if best_ratio >= threshold:
        return best_match, best_ratio
    return None, best_ratio


async def resolve_alias(
    db,
    openrouter_id: str,
    source: str,
    external_name: str,
) -> str | None:
    """Resuelve el openrouter_id canónico para un nombre externo.

    Flujo:
    1. Si existe fila en model_aliases con campo source-específico → retorna openrouter_id.
    2. Si no, fuzzy match contra MÚLTIPLES claves del modelo (name + id + último-segmento-id).
    3. Si hay match sobre threshold → upsert en model_aliases con match_confidence → retorna id.
    4. Si no hay match → upsert con confidence baja → retorna None.
    """
    # 1. Verificar alias explícito existente
    existing = await db.get_alias(openrouter_id)
    if existing:
        if source == "artificial_analysis" and existing.get("artificial_analysis_name"):
            return openrouter_id
        if source == "bfcl_github" and existing.get("bfcl_key"):
            return openrouter_id

    # 2. Construir lookup multi-clave: para cada modelo de OpenRouter armar varias
    #    variantes de su nombre/ID para maximizar chances de match.
    all_models = await db.list_models(text_only=False, include_stale=True)

    # Map de "string a comparar" → openrouter_id real
    candidate_to_id: dict[str, str] = {}
    for m in all_models:
        or_id = m.get("id", "") or ""
        name = (m.get("name") or "").strip()
        if not or_id:
            continue
        # Variante 1: name oficial
        if name:
            candidate_to_id.setdefault(name, or_id)
        # Variante 2: ID completo (anthropic/claude-opus-4.7)
        candidate_to_id.setdefault(or_id, or_id)
        # Variante 3: ID sin prefijo provider (claude-opus-4.7)
        if "/" in or_id:
            tail = or_id.split("/", 1)[1]
            candidate_to_id.setdefault(tail, or_id)

    candidate_names = list(candidate_to_id.keys())
    best_name, ratio = fuzzy_match(external_name, candidate_names)

    if best_name is not None:
        matched_id = candidate_to_id[best_name]
        aa_name = external_name if source == "artificial_analysis" else None
        bfcl_key = external_name if source == "bfcl_github" else None
        await db.upsert_alias(
            openrouter_id=matched_id,
            artificial_analysis_name=aa_name,
            bfcl_key=bfcl_key,
            match_confidence=ratio,
        )
        return matched_id

    # 4. Sin match
    aa_name = None
    bfcl_key = None
    await db.upsert_alias(
        openrouter_id=openrouter_id,
        artificial_analysis_name=aa_name,
        bfcl_key=bfcl_key,
        match_confidence=ratio if ratio > 0 else None,
    )
    return None
