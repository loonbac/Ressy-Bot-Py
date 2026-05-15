"""Scraper de benchmarks BFCL desde el repositorio GitHub HuanzhiMao/BFCL-Result.

Estrategia (2 API calls total):
1. GET /repos/HuanzhiMao/BFCL-Result/contents/ → lista de date folders + sus tree SHAs
2. GET /repos/HuanzhiMao/BFCL-Result/git/trees/{date_sha}?recursive=1 → todos los archivos
   bajo el date folder más reciente. Solo 1 call por date subtree.
3. Filtra paths que matchen `score/MODEL/FILE.json` (estructura FLAT real del repo).
4. Para cada archivo descarga vía raw.githubusercontent.com (no cuenta contra rate limit).
5. Lee primera línea NDJSON, extrae accuracy.
6. Agrupa por modelo. Resolve alias → upsert benchmarks.

Categorías BFCL en filenames (no subdirs):
- BFCL_v3_live_*       → categoría "live"
- BFCL_v3_multi_turn_* → categoría "multi_turn"
- BFCL_v3_*parallel*   → cuenta para bfcl_parallel
- BFCL_v3_*            → cuenta para bfcl_v3 overall

Códigos de error:
- "rate_limited"           → HTTP 403 + X-RateLimit-Remaining=0
- "unauthorized"           → HTTP 401 (token inválido)
- "no_token_rate_limited"  → 403 sin token configurado, sugerir setear github_token
- "no_data"                → tree vacío o ningún archivo válido
- str(exc)                 → cualquier otra excepción
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import defaultdict
from typing import Any

import httpx

from src.bot.plugins.openrouter_prices.aliases import resolve_alias
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

GITHUB_CONTENTS_URL = (
    "https://api.github.com/repos/HuanzhiMao/BFCL-Result/contents/"
)
TREE_URL_TPL = (
    "https://api.github.com/repos/HuanzhiMao/BFCL-Result/git/trees/{sha}?recursive=1"
)
RAW_BASE = "https://raw.githubusercontent.com/HuanzhiMao/BFCL-Result/main/"

_DATE_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Path bajo el subtree del date folder: score/MODEL/<cualquier nivel de subdirs>/FILE.json
# Captura model (primer segmento tras score/) y rest_path (subdirs/filename relativo)
_SCORE_PATH_RE = re.compile(
    r"^score/(?P<model>[^/]+)/(?P<rest>.+\.json)$"
)
_PARALLEL_PATTERN = re.compile(r"parallel", re.IGNORECASE)


class BFCLScraper:
    """Scraper de resultados BFCL usando GitHub Contents API + Trees API + raw downloads."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        github_token: str = "",
        max_models: int = 200,
    ) -> None:
        self._client = http_client
        self._owns_client = http_client is None
        self.github_token = github_token
        self.max_models = max_models

    async def scrape(self, db) -> ScrapeResult:
        started_at = int(time.time())
        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            result = await self._do_scrape(db, client, started_at)
        except asyncio.TimeoutError:
            result = ScrapeResult(
                source="bfcl",
                rows_updated=0,
                started_at=started_at,
                finished_at=int(time.time()),
                status="error",
                error="scrape_timeout",
            )
        except asyncio.CancelledError:
            result = ScrapeResult(
                source="bfcl",
                rows_updated=0,
                started_at=started_at,
                finished_at=int(time.time()),
                status="error",
                error="scrape_cancelled",
            )
            raise
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            result = ScrapeResult(
                source="bfcl",
                rows_updated=0,
                started_at=started_at,
                finished_at=int(time.time()),
                status="error",
                error=msg,
            )
        finally:
            if self._owns_client and not client.is_closed:
                await client.aclose()

        await db.record_scrape_run(
            source="bfcl",
            started_at=result.started_at,
            finished_at=result.finished_at,
            status=result.status,
            error=result.error,
            rows_updated=result.rows_updated,
            aliases_missed=result.aliases_missed,
        )
        return result

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json"}
        if self.github_token:
            h["Authorization"] = f"Bearer {self.github_token}"
        return h

    def _classify_error(self, status_code: int) -> str | None:
        if status_code == 401:
            return "unauthorized"
        if status_code == 403:
            return "no_token_rate_limited" if not self.github_token else "rate_limited"
        if status_code == 404:
            return "no_data"
        if status_code != 200:
            return f"github_http_{status_code}"
        return None

    async def _do_scrape(
        self,
        db,
        client: httpx.AsyncClient,
        started_at: int,
    ) -> ScrapeResult:
        # --- 1. Contents API root → date folders ---
        try:
            contents_resp = await client.get(GITHUB_CONTENTS_URL, headers=self._headers())
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            return self._error(
                started_at, f"contents_net_error: {str(exc) or type(exc).__name__}"
            )

        err = self._classify_error(contents_resp.status_code)
        if err:
            return self._error(started_at, err)

        try:
            contents: list[dict[str, Any]] = contents_resp.json()
        except Exception as exc:
            return self._error(
                started_at,
                f"json_parse_error: {str(exc) or type(exc).__name__}",
            )

        # Filtrar carpetas YYYY-MM-DD y guardar su tree SHA
        date_entries: list[tuple[str, str]] = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "dir":
                continue
            name = item.get("name") or ""
            if not _DATE_FOLDER_RE.match(name):
                continue
            sha = item.get("sha")
            if not sha:
                continue
            date_entries.append((name, sha))

        if not date_entries:
            return self._error(started_at, "no_data")

        # Más reciente primero
        date_entries.sort(key=lambda t: t[0], reverse=True)
        latest_date, latest_sha = date_entries[0]

        # --- 2. Trees API recursive sobre la SHA del date folder ---
        tree_url = TREE_URL_TPL.format(sha=latest_sha)
        try:
            tree_resp = await client.get(tree_url, headers=self._headers())
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            return self._error(
                started_at, f"tree_net_error: {str(exc) or type(exc).__name__}"
            )

        err = self._classify_error(tree_resp.status_code)
        if err:
            return self._error(started_at, err)

        try:
            tree_data = tree_resp.json()
        except Exception as exc:
            return self._error(
                started_at,
                f"json_parse_error: {str(exc) or type(exc).__name__}",
            )

        all_entries = tree_data.get("tree") or []
        truncated = bool(tree_data.get("truncated"))

        # --- 3. Filtrar score/MODEL/.../FILE.json (subdirs variables) ---
        # Valor en dict: lista de paths relativos al modelo (subdirs/file.json)
        per_model: dict[str, list[str]] = defaultdict(list)
        for entry in all_entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "blob":
                continue
            path = entry.get("path") or ""
            m = _SCORE_PATH_RE.match(path)
            if not m:
                continue
            per_model[m.group("model")].append(m.group("rest"))

        if not per_model:
            return self._error(started_at, "no_data")

        models_sorted = sorted(per_model.keys())[: self.max_models]

        # --- 4. Descargar NDJSON files via raw ---
        rows_updated = 0
        aliases_missed = 0
        extracted: list[dict] = []
        fetched_at = int(time.time())
        models_with_scores = 0

        # Paralelización GLOBAL: una sola gather para TODAS las (model, file) pairs
        # con semáforo limitando concurrencia. raw.githubusercontent.com soporta >100/s.
        sem = asyncio.Semaphore(80)

        async def _fetch_accuracy(model: str, rel_path: str) -> tuple[str, str, float | None]:
            url = f"{RAW_BASE}{latest_date}/score/{model}/{rel_path}"
            async with sem:
                try:
                    resp = await client.get(url)
                except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                    return model, rel_path, None
            if resp.status_code != 200:
                return model, rel_path, None
            text = resp.text
            if not text:
                return model, rel_path, None
            first_line = text.splitlines()[0]
            if not first_line:
                return model, rel_path, None
            try:
                summary = json.loads(first_line)
            except json.JSONDecodeError:
                return model, rel_path, None
            acc = summary.get("accuracy")
            if acc is None:
                return model, rel_path, None
            try:
                return model, rel_path, float(acc)
            except (TypeError, ValueError):
                return model, rel_path, None

        # Construir lista global de todas las tareas (model, rel_path)
        all_tasks = []
        for model_name in models_sorted:
            for rel_path in per_model[model_name]:
                all_tasks.append((model_name, rel_path))

        # Una sola gather paralela sobre todo (return_exceptions evita
        # que un download fallido aborte los 19999 restantes)
        results = await asyncio.gather(
            *(_fetch_accuracy(m, p) for m, p in all_tasks),
            return_exceptions=True,
        )

        # Re-agrupar resultados por modelo (descartar excepciones individuales)
        per_model_accs: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for r in results:
            if isinstance(r, BaseException):
                continue
            model, rel_path, acc = r
            if acc is not None:
                per_model_accs[model].append((rel_path, acc))

        # Procesar cada modelo con scores recolectados
        for model_name, pairs in per_model_accs.items():
            if not pairs:
                continue
            all_accuracies = [p[1] for p in pairs]
            parallel_accuracies = [
                p[1] for p in pairs if _PARALLEL_PATTERN.search(p[0])
            ]

            models_with_scores += 1
            bfcl_v3 = sum(all_accuracies) / len(all_accuracies)

            matched_id = await resolve_alias(
                db=db,
                openrouter_id=model_name,
                source="bfcl_github",
                external_name=model_name,
            )
            if matched_id is None:
                aliases_missed += 1
                continue

            await db.upsert_model_benchmark(
                model_id=matched_id,
                benchmark_slug="bfcl_v3",
                score=bfcl_v3,
                raw_value=f"avg_{len(all_accuracies)}_files",
                fetched_at=fetched_at,
                source="bfcl_github",
            )
            rows_updated += 1

            if parallel_accuracies:
                bfcl_parallel = sum(parallel_accuracies) / len(parallel_accuracies)
                await db.upsert_model_benchmark(
                    model_id=matched_id,
                    benchmark_slug="bfcl_parallel",
                    score=bfcl_parallel,
                    raw_value=f"parallel_{len(parallel_accuracies)}_files",
                    fetched_at=fetched_at,
                    source="bfcl_github",
                )
                rows_updated += 1

            extracted.append(
                {
                    "model": model_name,
                    "overall": bfcl_v3,
                    "parallel": (
                        sum(parallel_accuracies) / len(parallel_accuracies)
                        if parallel_accuracies
                        else None
                    ),
                    "matched_id": matched_id,
                }
            )

        if models_with_scores == 0:
            return self._error(started_at, "no_data")

        return ScrapeResult(
            source="bfcl",
            rows_updated=rows_updated,
            started_at=started_at,
            finished_at=int(time.time()),
            status="ok",
            extracted=extracted,
            aliases_missed=aliases_missed,
            error=("tree_truncated" if truncated else None),
        )

    @staticmethod
    def _error(started_at: int, msg: str) -> ScrapeResult:
        return ScrapeResult(
            source="bfcl",
            rows_updated=0,
            started_at=started_at,
            finished_at=int(time.time()),
            status="error",
            error=msg,
        )
