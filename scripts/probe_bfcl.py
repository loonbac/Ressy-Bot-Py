#!/usr/bin/env python3
"""Probe BFCL GitHub repo structure — discovers real per-model score/ subdirs.

Uso:
    uv run python scripts/probe_bfcl.py

Output: /tmp/bfcl_probe/ con arbol de directorios + NDJSONs de ejemplo.

Sin auth token → respetar rate limit GitHub (60 req/h).
Con GITHUB_TOKEN env var → 5000 req/h.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

GITHUB_CONTENTS_URL = (
    "https://api.github.com/repos/HuanzhiMao/BFCL-Result/contents/"
)
RAW_BASE = "https://raw.githubusercontent.com/HuanzhiMao/BFCL-Result/main/"
OUT = Path("/tmp/bfcl_probe")
MAX_MODELS_TO_PROBE = 5
MAX_FILE_SIZE = 100_000  # bytes — only download small files


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _dump_json(data, name: str) -> None:
    """Dumps JSON pretty-printed to /tmp/bfcl_probe/."""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(
        json.dumps(data, indent=2, default=str)
        if isinstance(data, (dict, list))
        else str(data)
    )
    print(f"  📄 {path}")


async def probe() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        # --- 1. List date folders ---
        print("\n=== 1. Listing YYYY-MM-DD folders ===")
        resp = await client.get(GITHUB_CONTENTS_URL, headers=_headers())
        resp.raise_for_status()
        contents: list[dict] = resp.json()
        date_folders = sorted(
            [
                item["name"]
                for item in contents
                if item.get("type") == "dir"
                and item["name"].replace("-", "").isdigit()
            ],
            reverse=True,
        )
        print(f"  Total date folders: {len(date_folders)}")
        _dump_json(date_folders, "01_date_folders.json")

        if not date_folders:
            print("  ❌ No date folders found")
            return

        latest = date_folders[0]
        print(f"\n  Latest: {latest}")

        # --- 2. Explore latest folder ---
        print(f"\n=== 2. Exploring {latest} ===")
        resp = await client.get(
            f"{GITHUB_CONTENTS_URL}{latest}", headers=_headers()
        )
        resp.raise_for_status()
        latest_contents = resp.json()
        _dump_json(latest_contents, "02_latest_contents.json")

        dir_names = [item["name"] for item in latest_contents if item.get("type") == "dir"]
        file_names = [item["name"] for item in latest_contents if item.get("type") == "file"]
        print(f"  Subdirs: {dir_names}")
        print(f"  Files: {file_names}")

        # --- 3. Explore score/ ---
        if "score" not in dir_names:
            print("\n  ⚠️  No score/ folder found. Aborting.")
            return

        print(f"\n=== 3. Exploring {latest}/score/ ===")
        resp = await client.get(
            f"{GITHUB_CONTENTS_URL}{latest}/score", headers=_headers()
        )
        resp.raise_for_status()
        score_contents = resp.json()
        _dump_json(score_contents, "03_score_contents.json")

        model_dirs = [
            item["name"]
            for item in score_contents
            if item.get("type") == "dir"
        ]
        print(f"  Models found: {len(model_dirs)}")
        print(f"  First {min(MAX_MODELS_TO_PROBE, len(model_dirs))}: {model_dirs[:MAX_MODELS_TO_PROBE]}")

        # --- 4. For each model, explore subdirs (agentic, live, multi_turn, non_live) ---
        print(f"\n=== 4. Exploring models ({min(MAX_MODELS_TO_PROBE, len(model_dirs))} of {len(model_dirs)}) ===")
        all_model_data = {}
        ndjson_samples = {}
        structure_report = {
            "latest_folder": latest,
            "model_count": len(model_dirs),
            "probed_models": [],
            "subdirs_found": set(),
            "file_patterns": set(),
            "ndjson_first_line_schema": None,
        }

        for model_name in model_dirs[:MAX_MODELS_TO_PROBE]:
            print(f"\n  --- {model_name} ---")
            model_url = f"{GITHUB_CONTENTS_URL}{latest}/score/{model_name}"
            try:
                resp = await client.get(model_url, headers=_headers())
                resp.raise_for_status()
                model_contents = resp.json()
            except Exception as e:
                print(f"  ⚠️  Error listing model dir: {e}")
                continue

            subdirs = [item["name"] for item in model_contents if item.get("type") == "dir"]
            print(f"  Subdirs: {subdirs}")
            structure_report["subdirs_found"].update(subdirs)

            model_entry = {"subdirs": {}}

            for subdir_name in subdirs:
                subdir_url = f"{GITHUB_CONTENTS_URL}{latest}/score/{model_name}/{subdir_name}"
                try:
                    resp = await client.get(subdir_url, headers=_headers())
                    resp.raise_for_status()
                    subdir_contents = resp.json()
                except Exception as e:
                    print(f"    ⚠️  Error listing {subdir_name}: {e}")
                    continue

                files = [item["name"] for item in subdir_contents if item.get("type") == "file"]
                print(f"    {subdir_name}/ files: {files}")
                model_entry["subdirs"][subdir_name] = {"files": files, "raw": {}}

                for fname in files:
                    structure_report["file_patterns"].add(fname)

                    # Only download small files (<100KB)
                    size = next((item["size"] for item in subdir_contents if item["name"] == fname), 0)
                    if size > MAX_FILE_SIZE:
                        print(f"      ⏭️  {fname} ({size} bytes) — too large, skipping")
                        model_entry["subdirs"][subdir_name]["raw"][fname] = f"SKIPPED_SIZE_{size}"
                        continue

                    raw_url = f"{RAW_BASE}{latest}/score/{model_name}/{subdir_name}/{fname}"
                    print(f"      ⬇️  {fname}")
                    try:
                        raw_resp = await client.get(raw_url, headers=_headers(), timeout=15.0)
                        raw_resp.raise_for_status()
                        text = raw_resp.text

                        # NDJSON: first line is summary, rest are individual results
                        lines = text.strip().split("\n")
                        if lines:
                            try:
                                first_line = json.loads(lines[0])
                            except json.JSONDecodeError:
                                first_line = lines[0][:200]

                            # Store sample
                            sample_key = f"{model_name}/{subdir_name}/{fname}"
                            ndjson_samples[sample_key] = {
                                "model": model_name,
                                "subdir": subdir_name,
                                "file": fname,
                                "line_count": len(lines),
                                "first_line": first_line,
                                "second_line": json.loads(lines[1]) if len(lines) > 1 else None,
                            }
                            model_entry["subdirs"][subdir_name]["raw"][fname] = {
                                "line_count": len(lines),
                                "first_line": first_line,
                            }

                            if structure_report["ndjson_first_line_schema"] is None:
                                structure_report["ndjson_first_line_schema"] = {
                                    "keys": list(first_line.keys()) if isinstance(first_line, dict) else None,
                                    "type": type(first_line).__name__,
                                    "sample": first_line,
                                }

                            print(f"        Lines: {len(lines)} | First line keys: {list(first_line.keys()) if isinstance(first_line, dict) else 'N/A'}")
                        else:
                            model_entry["subdirs"][subdir_name]["raw"][fname] = {"line_count": 0, "first_line": None}

                    except Exception as e:
                        print(f"        ⚠️  Error: {e}")
                        model_entry["subdirs"][subdir_name]["raw"][fname] = f"ERROR: {e}"

            all_model_data[model_name] = model_entry
            structure_report["probed_models"].append(model_name)

        _dump_json(all_model_data, "04_model_samples.json")
        _dump_json(ndjson_samples, "05_ndjson_samples.json")

        # Convert sets to lists for JSON serialization
        structure_report["subdirs_found"] = sorted(structure_report["subdirs_found"])
        structure_report["file_patterns"] = sorted(structure_report["file_patterns"])
        _dump_json(structure_report, "06_structure_report.json")

        # --- 5. Summary ---
        print("\n\n=== RESUMEN ===")
        print(f"  Latest date folder: {latest}")
        print(f"  Subdirs in {latest}: {dir_names}")
        print(f"  Total models in score/: {len(model_dirs)}")
        print(f"  Model subdirs found: {structure_report['subdirs_found']}")
        print(f"  File patterns: {structure_report['file_patterns']}")
        print(f"  Output: {OUT}/")

        if structure_report["ndjson_first_line_schema"]:
            schema = structure_report["ndjson_first_line_schema"]
            print(f"\n  NDJSON first-line schema:")
            print(f"    Type: {schema['type']}")
            print(f"    Keys: {schema['keys']}")
            print(f"    Sample: {json.dumps(schema['sample'], indent=2)[:200]}")

        print("\n  ✅ Probes completed. Use these data for the tests.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(probe())
