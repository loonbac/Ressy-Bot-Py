"""Funciones puras de normalización y ranking de modelos OpenRouter.

Sin importaciones de .database — solo recibe datos ya extraídos.
Normalización min-max. Pesos renormalizados en tiempo de cómputo.
"""
from __future__ import annotations

import json
import math


def normalize_higher_is_better(values: dict[str, float]) -> dict[str, float]:
    """Normalización min-max [0,1]. Mayor valor crudo → mayor score.

    Si max == min (todos iguales o un solo valor), devuelve 0.5 para todos.
    Input vacío devuelve dict vacío.
    """
    if not values:
        return {}
    min_val = min(values.values())
    max_val = max(values.values())
    if max_val == min_val:
        return {k: 0.5 for k in values}
    span = max_val - min_val
    return {k: (v - min_val) / span for k, v in values.items()}


def normalize_lower_is_better(values: dict[str, float]) -> dict[str, float]:
    """Normalización min-max invertida [0,1]. Menor valor crudo → mayor score.

    Si max == min, devuelve 0.5 para todos.
    Input vacío devuelve dict vacío.
    """
    if not values:
        return {}
    min_val = min(values.values())
    max_val = max(values.values())
    if max_val == min_val:
        return {k: 0.5 for k in values}
    span = max_val - min_val
    return {k: (max_val - v) / span for k, v in values.items()}


def weighted_score(
    per_benchmark: dict[str, dict[str, float]],
    weights: dict[str, float],
) -> dict[str, float]:
    """Calcula score ponderado por modelo.

    Args:
        per_benchmark: {benchmark_slug: {model_id: normalized_score in [0,1]}}
        weights: {benchmark_slug: weight}

    Reglas:
    - Solo benchmarks con weight > 0 Y al menos un modelo con datos participan.
    - Renormalización PER-MODELO: cada modelo solo se evalúa contra los benchmarks
      que tiene; los pesos disponibles se renormalizan a 1.0 para ese modelo.
      Esto evita penalizar arbitrariamente modelos nuevos que aún no tienen TODAS
      las métricas (ej. DeepSeek V4 sin BFCL data → no se hunde su score).
    - Si un modelo tiene <50% del peso disponible, se descarta (datos insuficientes).

    Returns:
        {model_id: total_score in [0,1]}
    """
    # Benchmarks activos: weight > 0 y al menos un modelo con datos
    active: list[str] = [
        slug for slug, w in weights.items()
        if w > 0 and per_benchmark.get(slug)
    ]
    if not active:
        return {}

    full_total = sum(weights[s] for s in active)
    if full_total <= 0:
        return {}

    # Recopilar todos los model_ids
    all_models: set[str] = set()
    for slug in active:
        all_models.update(per_benchmark[slug].keys())

    if not all_models:
        return {}

    # Umbral mínimo de cobertura: modelo debe tener al menos 50% del peso total
    # disponible en sus benchmarks. Menos que eso = data insuficiente, se omite.
    coverage_threshold = 0.5 * full_total

    result: dict[str, float] = {}
    for model_id in all_models:
        # Calcular peso disponible para este modelo (suma de pesos de benchmarks que tiene)
        available_weight = sum(
            weights[s] for s in active if model_id in per_benchmark[s]
        )
        if available_weight < coverage_threshold:
            continue

        # Score ponderado global: datos faltantes contribuyen 0
        score = 0.0
        for slug in active:
            score += per_benchmark[slug].get(model_id, 0.0) * weights[slug]
        result[model_id] = score / full_total

    return result


def rank_top_n(scores: dict[str, float], n: int) -> list[tuple[str, float]]:
    """Ordena por score descendente. Empates: orden alfabético por model_id ascendente.

    Returns:
        Lista de (model_id, score) con hasta n elementos.
    """
    if not scores:
        return []
    sorted_models = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return sorted_models[:n]


async def compute_ranking_for_phase(db, phase: str, n: int = 10) -> list[dict]:
    """Calcula el ranking de modelos para una fase de perfil.

    1. Obtiene phase_profile (pesos por benchmark_slug + is_feature_factor).
    2. Extrae raw scores de model_benchmarks.
    3. Normaliza:
       - Benchmarks normales: normalize_higher_is_better
       - input_cache_read_ratio: compute (input_cache_read / prompt) por modelo → normalize_lower_is_better
       - supports_reasoning_effort / supports_verbosity: 1.0 si está en supported_parameters, else 0.0
    4. weighted_score → rank_top_n
    5. Devuelve [{rank, model_id, name, score, breakdown: [{slug, weighted_contribution}]}]
    """
    profile = await db.get_phase_profile(phase)
    if not profile:
        return []

    weights: dict[str, float] = {}
    is_feature: dict[str, bool] = {}
    for entry in profile:
        slug = entry["benchmark_slug"]
        weights[slug] = entry["weight"]
        is_feature[slug] = bool(entry["is_feature_factor"])

    # Cargar todos los modelos para feature factors y nombres
    all_models = await db.list_models(text_only=False, include_stale=True)
    model_name_map: dict[str, str] = {m["id"]: m.get("name", m["id"]) for m in all_models}

    per_benchmark: dict[str, dict[str, float]] = {}

    for slug, w in weights.items():
        if w == 0:
            per_benchmark[slug] = {}
            continue

        if not is_feature.get(slug, False):
            # Benchmark normal: pull de model_benchmarks
            rows = await db.list_model_benchmarks(benchmark_slug=slug)
            raw_values: dict[str, float] = {}
            for row in rows:
                score = row.get("score")
                if score is not None and not math.isnan(score):
                    raw_values[row["model_id"]] = float(score)
            per_benchmark[slug] = normalize_higher_is_better(raw_values)

        elif slug == "input_cache_read_ratio":
            # Ratio: input_cache_read / pricing_prompt por modelo → lower_is_better
            ratios: dict[str, float] = {}
            for m in all_models:
                prompt_raw = m.get("pricing_prompt") or "0"
                cache_raw = m.get("pricing_input_cache_read") or "0"
                try:
                    prompt_f = float(prompt_raw)
                    cache_f = float(cache_raw)
                    if prompt_f > 0:
                        ratios[m["id"]] = cache_f / prompt_f
                except (ValueError, TypeError):
                    pass
            per_benchmark[slug] = normalize_lower_is_better(ratios)

        elif slug in ("supports_reasoning_effort", "supports_verbosity"):
            # Feature flag: 1.0 si el parámetro está en supported_parameters
            param_name = slug.replace("supports_", "")  # reasoning_effort / verbosity
            flags: dict[str, float] = {}
            for m in all_models:
                raw_json = m.get("raw_json", "{}")
                try:
                    parsed = json.loads(raw_json)
                    supported = parsed.get("supported_parameters", [])
                    flags[m["id"]] = 1.0 if param_name in supported else 0.0
                except (json.JSONDecodeError, TypeError):
                    flags[m["id"]] = 0.0
            per_benchmark[slug] = flags

        else:
            per_benchmark[slug] = {}

    scores = weighted_score(per_benchmark, weights)
    top = rank_top_n(scores, n)

    # Calcular breakdowns
    active_slugs = [s for s, w in weights.items() if w > 0 and per_benchmark.get(s)]
    if active_slugs:
        total_w = sum(weights[s] for s in active_slugs)
        norm_w = {s: weights[s] / total_w for s in active_slugs}
    else:
        norm_w = {}

    result: list[dict] = []
    for rank_pos, (model_id, score) in enumerate(top, start=1):
        breakdown = []
        for slug in active_slugs:
            contrib = per_benchmark[slug].get(model_id, 0.0) * norm_w.get(slug, 0.0)
            breakdown.append({"benchmark_slug": slug, "weighted_contribution": contrib})
        result.append({
            "rank": rank_pos,
            "model_id": model_id,
            "name": model_name_map.get(model_id, model_id),
            "score": score,
            "breakdown": breakdown,
        })

    return result
