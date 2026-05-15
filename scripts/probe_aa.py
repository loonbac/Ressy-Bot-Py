#!/usr/bin/env python3
"""Probe Artificial Analysis API — verifica conectividad y estructura de respuesta.

Uso:
    uv run python scripts/probe_aa.py

Output:
  /tmp/aa_api_probe.json  — respuesta cruda truncada para inspeccion
  /tmp/aa_api_report.json — reporte estructurado
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
API_KEY = "aa_PauXVRbbLpzJqdcIZiofepBrIalOFLvp"
OUT = Path("/tmp")
RAW_RESPONSE = OUT / "aa_api_probe.json"
REPORT = OUT / "aa_api_report.json"


async def probe(
    dump_fields: bool = False,
    http_client: httpx.AsyncClient | None = None,
) -> dict | None:
    print(f"\n=== GET {API_URL} ===")
    client = http_client or httpx.AsyncClient(timeout=60.0)
    close_client = http_client is None
    try:
        response = await client.get(
            API_URL,
            headers={"x-api-key": API_KEY},
        )
        print(f"  Status: {response.status_code}")
        response.raise_for_status()

        payload = response.json()
    finally:
        if close_client and not getattr(client, "is_closed", False):
            await client.aclose()

    data = payload.get("data", [])

    if dump_fields:
        fields: dict[str, dict] = {}
        for model in data:
            evals = model.get("evaluations") or {}
            for key, value in evals.items():
                if value is None:
                    continue
                if key not in fields:
                    fields[key] = {"count": 0, "example": value}
                fields[key]["count"] += 1
        report = {
            "total_models": len(data),
            "fields": {
                k: {"count": v["count"], "example": v["example"]}
                for k, v in sorted(fields.items())
            },
        }
        out_path = OUT / "aa_api_fields.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"  Fields dump: {out_path}")
        return report

    # Guardar respuesta truncada
    truncated = {
        "status": payload.get("status"),
        "prompt_options": payload.get("prompt_options"),
        "model_count": len(data),
        "first_3_models": data[:3],
    }
    RAW_RESPONSE.write_text(json.dumps(truncated, indent=2, ensure_ascii=False))
    print(f"  Respuesta truncada: {RAW_RESPONSE}")

    # Reporte
    report: dict = {
        "total_models": len(data),
        "eval_keys_found": set(),
        "models_with_ifbench": 0,
        "models_with_tau2": 0,
        "models_with_intelligence_index": 0,
        "models_without_evaluations": 0,
        "sample_names": [m.get("name", "") for m in data[:10]],
    }

    for model in data:
        evals = model.get("evaluations") or {}
        if not evals:
            report["models_without_evaluations"] += 1
            continue
        report["eval_keys_found"].update(evals.keys())
        if evals.get("ifbench") is not None:
            report["models_with_ifbench"] += 1
        if evals.get("tau2") is not None:
            report["models_with_tau2"] += 1
        if evals.get("artificial_analysis_intelligence_index") is not None:
            report["models_with_intelligence_index"] += 1

    report["eval_keys_found"] = sorted(report["eval_keys_found"])

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"  Reporte: {REPORT}")

    print("\n=== RESUMEN ===")
    print(f"  Total modelos: {report['total_models']}")
    print(f"  Con ifbench: {report['models_with_ifbench']}")
    print(f"  Con tau2: {report['models_with_tau2']}")
    print(f"  Con intelligence_index: {report['models_with_intelligence_index']}")
    print(f"  Sin evaluations: {report['models_without_evaluations']}")
    print(f"  Claves de evaluacion encontradas: {report['eval_keys_found']}")
    print(f"  Primeros nombres: {report['sample_names'][:5]}")
    return None


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Probe Artificial Analysis API")
    parser.add_argument(
        "--dump-fields",
        action="store_true",
        help="List all evaluation keys from AA API with model counts and example values",
    )
    args = parser.parse_args()
    asyncio.run(probe(dump_fields=args.dump_fields))
