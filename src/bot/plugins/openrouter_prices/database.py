"""Base de datos SQLite para el plugin openrouter_prices.

Maneja el schema, la configuración y el catálogo de modelos de OpenRouter.
Sigue el patrón de BlackboardDatabase: clase async, aiosqlite, métodos CRUD aislados.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).parent / "seeds"
PHASES_ENABLED_DEFAULT = json.dumps(["orchestrator", "sdd_init"])
REQUIRED_PHASE_METADATA_KEYS = {"description", "rationale", "reserved_zero"}


# Valores por defecto semilla (INSERT OR IGNORE — nunca pisa config customizada)
DEFAULTS: dict[str, str] = {
    "enabled": "true",
    "ttl_seconds": "3600",
    "max_models_command": "10",
    "discord_channel_id": "",
    # Nuevas claves REQ-EXT-11
    "openrouter_refresh_interval_hours": "24",
    "aa_scrape_enabled": "true",
    "aa_scrape_interval_days": "7",
    "bfcl_scrape_enabled": "true",
    "bfcl_scrape_interval_days": "7",
    "weekly_report_enabled": "true",
    "weekly_report_channel_id": "",
    "weekly_report_day": "monday",
    "weekly_report_hour": "9",
    "weekly_report_count": "10",
    "ranking_embed_enabled": "true",
    "ranking_embed_channel_id": "",
    "ranking_embed_cron_days": "14",
    "ranking_phase": "orchestrator",
    "github_token": "",
    "bfcl_scrape_max_models": "200",
    "aa_api_key": "",
    "stale_threshold_days": "14",
    # Nuevas claves PR2
    "phases_enabled": PHASES_ENABLED_DEFAULT,
    "ranking_embed_per_phase": "true",
}

# Mapa de sort alias → columna real en la tabla 'models'
SORT_COLUMNS: dict[str, str] = {
    "prompt": "pricing_prompt",
    "completion": "pricing_completion",
    "context": "context_length",
    "name": "name",
}


class OpenRouterDatabase:
    """Gestión de persistencia SQLite para precios de OpenRouter."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Abre la conexión y crea el schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_schema()
        await self._seed_defaults()
        await self._run_migrations()

    async def close(self) -> None:
        """Cierra la conexión de forma ordenada."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def _create_schema(self) -> None:
        """Crea las 3 tablas y 2 índices si no existen."""
        assert self._db is not None

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id                                 TEXT PRIMARY KEY,
                name                               TEXT,
                description                        TEXT,
                created_at                         INTEGER,
                context_length                     INTEGER,
                input_modalities                   TEXT,
                output_modalities                  TEXT,
                modality                           TEXT,
                pricing_prompt                     TEXT,
                pricing_completion                 TEXT,
                pricing_image                      TEXT,
                pricing_request                    TEXT,
                pricing_web_search                 TEXT,
                pricing_input_cache_read           TEXT,
                pricing_input_cache_write          TEXT,
                top_provider_context_length        INTEGER,
                top_provider_max_completion_tokens INTEGER,
                top_provider_is_moderated          INTEGER,
                raw_json                           TEXT NOT NULL,
                stale                              INTEGER NOT NULL DEFAULT 0,
                fetched_at                         INTEGER NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_models_stale ON models(stale)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_models_pricing_prompt ON models(pricing_prompt)"
        )

        # ------------------------------------------------------------------
        # Tablas nuevas: benchmarks, model_benchmarks, phase_profiles,
        # model_aliases, scrape_runs
        # ------------------------------------------------------------------

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                slug             TEXT UNIQUE NOT NULL,
                display_name     TEXT NOT NULL,
                source           TEXT NOT NULL,
                higher_is_better INTEGER NOT NULL DEFAULT 1,
                description      TEXT
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS model_benchmarks (
                model_id        TEXT NOT NULL,
                benchmark_slug  TEXT NOT NULL,
                score           REAL,
                raw_value       TEXT,
                fetched_at      INTEGER NOT NULL,
                source          TEXT NOT NULL,
                PRIMARY KEY (model_id, benchmark_slug)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS phase_profiles (
                phase           TEXT NOT NULL,
                benchmark_slug  TEXT NOT NULL,
                weight          REAL NOT NULL DEFAULT 0.0,
                is_feature_factor INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (phase, benchmark_slug)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS model_aliases (
                openrouter_id            TEXT PRIMARY KEY,
                artificial_analysis_name TEXT,
                bfcl_key                 TEXT,
                match_confidence         REAL,
                updated_at               INTEGER NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL,
                started_at   INTEGER NOT NULL,
                finished_at  INTEGER,
                status       TEXT NOT NULL,
                error        TEXT,
                rows_updated INTEGER NOT NULL DEFAULT 0
            )
        """)

        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_benchmarks_slug ON model_benchmarks(benchmark_slug)"
        )

        await self._db.commit()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def _seed_defaults(self) -> None:
        """Siembra valores por defecto con INSERT OR IGNORE (idempotente)."""
        assert self._db is not None
        for key, value in DEFAULTS.items():
            await self._db.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()
        await self._seed_benchmarks()
        await self._seed_phase_profile()

    async def _seed_benchmarks(self) -> None:
        """Siembra los 8 benchmarks iniciales desde seeds/benchmarks_seed.json."""
        assert self._db is not None
        seed_path = SEEDS_DIR / "benchmarks_seed.json"
        if not seed_path.exists():
            return
        with open(seed_path) as f:
            data = json.load(f)
        for b in data.get("benchmarks", []):
            await self._db.execute(
                """INSERT OR IGNORE INTO benchmarks
                   (slug, display_name, source, higher_is_better, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    b["slug"],
                    b["display_name"],
                    b["source"],
                    1 if b.get("higher_is_better", True) else 0,
                    b.get("description", ""),
                ),
            )
        await self._db.commit()

    async def _seed_phase_profile(self) -> None:
        """Siembra todos los perfiles de fase desde seeds/*_phase_weights.json.

        Para cada archivo:
        - Valida que los pesos sumen 1.0 (tolerancia 1e-9).
        - Si es invalido: log warning y se salta ese perfil.
        - Si es valido: INSERT OR IGNORE idempotente.
        """
        assert self._db is not None
        for seed_path in sorted(SEEDS_DIR.glob("*_phase_weights.json")):
            with open(seed_path) as f:
                data = json.load(f)
            phase = data.get("phase", seed_path.stem.replace("_phase_weights", ""))
            self._warn_invalid_phase_metadata(seed_path, data)
            weights = data.get("weights", [])
            total = sum(w.get("weight", 0.0) for w in weights)
            if abs(total - 1.0) > 1e-9:
                logger.warning(
                    "Skipping phase profile '%s' from %s: weights sum to %.9f, expected 1.0",
                    phase,
                    seed_path.name,
                    total,
                )
                continue
            for w in weights:
                await self._db.execute(
                    """INSERT OR IGNORE INTO phase_profiles
                       (phase, benchmark_slug, weight, is_feature_factor)
                       VALUES (?, ?, ?, ?)""",
                    (
                        phase,
                        w["benchmark_slug"],
                        w["weight"],
                        1 if w.get("is_feature_factor", False) else 0,
                    ),
                )
            await self._db.commit()

    def _warn_invalid_phase_metadata(self, seed_path: Path, data: dict[str, Any]) -> None:
        """Advierte contratos de metadata incompletos sin bloquear el seed."""
        metadata = data.get("metadata")
        if metadata is None:
            if "_metadata" in data:
                logger.warning(
                    "Seed %s usa '_metadata'; debe migrarse a 'metadata'.",
                    seed_path.name,
                )
            else:
                logger.warning(
                    "Seed %s no tiene metadata; se recomienda metadata.description, metadata.rationale y metadata.reserved_zero.",
                    seed_path.name,
                )
            return

        missing = sorted(REQUIRED_PHASE_METADATA_KEYS - set(metadata.keys()))
        if missing:
            logger.warning(
                "Seed %s tiene metadata incompleta; faltan: %s.",
                seed_path.name,
                ", ".join(missing),
            )

        if "reserved_zero" in metadata and not isinstance(metadata["reserved_zero"], list):
            logger.warning(
                "Seed %s tiene metadata.reserved_zero invalido; debe ser una lista de strings.",
                seed_path.name,
            )

    async def _run_migrations(self) -> None:
        """Run idempotent schema/data migrations."""
        assert self._db is not None

        # Migration 1: Rename aa_omniscience_nh → aa_intelligence_index
        await self._db.execute("""
            UPDATE OR IGNORE model_benchmarks
            SET benchmark_slug = 'aa_intelligence_index'
            WHERE benchmark_slug = 'aa_omniscience_nh'
        """)
        # Solo renombrar phase_profiles si hay filas legacy; en DB nueva no tocar
        legacy_phase = await self._db.execute_fetchall(
            "SELECT 1 FROM phase_profiles WHERE benchmark_slug = 'aa_omniscience_nh' LIMIT 1"
        )
        if legacy_phase:
            await self._db.execute("""
                DELETE FROM phase_profiles WHERE benchmark_slug = 'aa_intelligence_index'
            """)
            await self._db.execute("""
                UPDATE phase_profiles
                SET benchmark_slug = 'aa_intelligence_index'
                WHERE benchmark_slug = 'aa_omniscience_nh'
            """)
        await self._db.execute("""
            DELETE FROM benchmarks WHERE slug = 'aa_omniscience_nh'
        """)
        # Asegurar que el nuevo benchmark exista (legacy DB no lo tendria)
        await self._db.execute("""
            INSERT OR IGNORE INTO benchmarks
            (slug, display_name, source, higher_is_better, description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "aa_intelligence_index",
            "AA Intelligence Index",
            "artificial_analysis",
            1,
            "Artificial Analysis Intelligence Index — score compuesto de inteligencia agregada de multiples benchmarks AA",
        ))
        # Migration 2: Purge orphan aa_omniscience slug (never populated by any scraper)
        try:
            await self._db.execute("DELETE FROM model_benchmarks WHERE benchmark_slug = 'aa_omniscience'")
            await self._db.execute("DELETE FROM phase_profiles WHERE benchmark_slug = 'aa_omniscience'")
            await self._db.execute("DELETE FROM benchmarks WHERE slug = 'aa_omniscience'")
            await self._db.commit()
        except Exception:
            # Safe-guard: tabla puede no existir en edge cases
            pass

        # Migration 2b: Normalizar slug tau2_bench_telecom → tau2_telecom
        # (los seeds y los scrapers usan tau2_telecom; rows antiguos quedaban huérfanos)
        try:
            await self._db.execute(
                "UPDATE OR REPLACE model_benchmarks SET benchmark_slug = 'tau2_telecom' "
                "WHERE benchmark_slug = 'tau2_bench_telecom'"
            )
            await self._db.execute(
                "UPDATE OR REPLACE phase_profiles SET benchmark_slug = 'tau2_telecom' "
                "WHERE benchmark_slug = 'tau2_bench_telecom'"
            )
            await self._db.execute(
                "DELETE FROM benchmarks WHERE slug = 'tau2_bench_telecom'"
            )
            await self._db.commit()
        except Exception:
            pass

        # Migration 3: Add aliases_missed column to scrape_runs
        try:
            await self._db.execute(
                "ALTER TABLE scrape_runs ADD COLUMN aliases_missed INTEGER NOT NULL DEFAULT 0"
            )
            await self._db.commit()
        except aiosqlite.OperationalError:
            # Column already exists
            pass

        # Migration 4: phases_enabled debe almacenarse como JSON array string.
        rows = await self._db.execute_fetchall(
            "SELECT value FROM config WHERE key = 'phases_enabled' LIMIT 1"
        )
        if not rows:
            await self._db.execute(
                "INSERT INTO config (key, value) VALUES (?, ?)",
                ("phases_enabled", PHASES_ENABLED_DEFAULT),
            )
        else:
            current = str(rows[0]["value"] or "").strip()
            if current and not current.startswith("["):
                phases = [part.strip() for part in current.split(",") if part.strip()]
                await self._db.execute(
                    "UPDATE config SET value = ? WHERE key = 'phases_enabled'",
                    (json.dumps(phases),),
                )
            elif not current:
                await self._db.execute(
                    "UPDATE config SET value = ? WHERE key = 'phases_enabled'",
                    (PHASES_ENABLED_DEFAULT,),
                )
        await self._db.commit()

    async def get_config(self) -> dict[str, str]:
        """Devuelve toda la configuración como dict de strings."""
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT key, value FROM config")
        return {row["key"]: row["value"] for row in rows}

    async def update_config(self, updates: dict[str, str]) -> None:
        """Actualiza uno o más valores de configuración (INSERT OR REPLACE)."""
        assert self._db is not None
        for key, value in updates.items():
            await self._db.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Models upsert + stale marking
    # ------------------------------------------------------------------

    async def upsert_models(self, models: list[dict[str, Any]], fetched_at: int) -> int:
        """Inserta o actualiza modelos y marca como stale los ausentes.

        Args:
            models: Lista de dicts con la forma devuelta por la API de OpenRouter.
            fetched_at: Timestamp Unix del momento del fetch.

        Returns:
            Número de modelos insertados/actualizados.
        """
        assert self._db is not None
        if not models:
            return 0

        upserted_ids: list[str] = []

        for raw in models:
            model_id = raw.get("id", "")
            if not model_id:
                continue

            arch = raw.get("architecture") or {}
            pricing = raw.get("pricing") or {}
            top = raw.get("top_provider") or {}

            input_mod = arch.get("input_modalities", [])
            output_mod = arch.get("output_modalities", [])

            await self._db.execute(
                """
                INSERT INTO models (
                    id, name, description, created_at, context_length,
                    input_modalities, output_modalities, modality,
                    pricing_prompt, pricing_completion, pricing_image,
                    pricing_request, pricing_web_search,
                    pricing_input_cache_read, pricing_input_cache_write,
                    top_provider_context_length, top_provider_max_completion_tokens,
                    top_provider_is_moderated,
                    raw_json, stale, fetched_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, 0, ?
                )
                ON CONFLICT(id) DO UPDATE SET
                    name                               = excluded.name,
                    description                        = excluded.description,
                    created_at                         = excluded.created_at,
                    context_length                     = excluded.context_length,
                    input_modalities                   = excluded.input_modalities,
                    output_modalities                  = excluded.output_modalities,
                    modality                           = excluded.modality,
                    pricing_prompt                     = excluded.pricing_prompt,
                    pricing_completion                 = excluded.pricing_completion,
                    pricing_image                      = excluded.pricing_image,
                    pricing_request                    = excluded.pricing_request,
                    pricing_web_search                 = excluded.pricing_web_search,
                    pricing_input_cache_read           = excluded.pricing_input_cache_read,
                    pricing_input_cache_write          = excluded.pricing_input_cache_write,
                    top_provider_context_length        = excluded.top_provider_context_length,
                    top_provider_max_completion_tokens = excluded.top_provider_max_completion_tokens,
                    top_provider_is_moderated          = excluded.top_provider_is_moderated,
                    raw_json                           = excluded.raw_json,
                    stale                              = 0,
                    fetched_at                         = excluded.fetched_at
                """,
                (
                    model_id,
                    raw.get("name", ""),
                    raw.get("description", ""),
                    raw.get("created"),
                    raw.get("context_length"),
                    json.dumps(input_mod),
                    json.dumps(output_mod),
                    arch.get("modality", ""),
                    pricing.get("prompt"),
                    pricing.get("completion"),
                    pricing.get("image"),
                    pricing.get("request"),
                    pricing.get("web_search"),
                    pricing.get("input_cache_read"),
                    pricing.get("input_cache_write"),
                    top.get("context_length"),
                    top.get("max_completion_tokens"),
                    1 if top.get("is_moderated") else 0,
                    json.dumps(raw),
                    fetched_at,
                ),
            )
            upserted_ids.append(model_id)

        # Marcar stale los modelos que NO estuvieron en este fetch
        if upserted_ids:
            placeholders = ",".join("?" * len(upserted_ids))
            await self._db.execute(
                f"UPDATE models SET stale = 1 WHERE id NOT IN ({placeholders})",
                upserted_ids,
            )

        await self._db.commit()
        return len(upserted_ids)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_models(
        self,
        text_only: bool = True,
        sort_by: str = "prompt",
        sort_dir: str = "asc",
        limit: int | None = None,
        include_stale: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista modelos con filtros opcionales.

        Args:
            text_only: Si True, solo devuelve modelos con "text" en input_modalities.
            sort_by: Columna de ordenamiento: "prompt", "completion", "context", "name".
            sort_dir: Dirección: "asc" o "desc".
            limit: Máximo de filas a devolver.
            include_stale: Si False (defecto), excluye modelos marcados stale.
        """
        assert self._db is not None

        col = SORT_COLUMNS.get(sort_by, "pricing_prompt")
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

        conditions: list[str] = []
        params: list[Any] = []

        if not include_stale:
            conditions.append("stale = 0")

        if text_only:
            # Substring check sobre JSON serializado — eficiente con el índice existente
            conditions.append('input_modalities LIKE \'%"text"%\'')

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""

        sql = f"""
            SELECT * FROM models
            {where}
            ORDER BY {col} {direction}
            {limit_clause}
        """

        rows = await self._db.execute_fetchall(sql, params)
        return [dict(r) for r in rows]

    async def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Devuelve un modelo por ID, o None si no existe."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT * FROM models WHERE id = ?", (model_id,)
        )
        return dict(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def get_metadata(self) -> dict[str, str]:
        """Devuelve todos los pares key/value de la tabla metadata."""
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT key, value FROM metadata")
        return {row["key"]: row["value"] for row in rows}

    async def set_metadata(self, key: str, value: str) -> None:
        """Inserta o reemplaza un valor de metadata."""
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Count
    # ------------------------------------------------------------------

    async def count_models(self, stale: bool = False) -> int:
        """Cuenta modelos. Si stale=True, cuenta solo los marcados stale."""
        assert self._db is not None
        if stale:
            rows = await self._db.execute_fetchall(
                "SELECT COUNT(*) as n FROM models WHERE stale = 1"
            )
        else:
            rows = await self._db.execute_fetchall("SELECT COUNT(*) as n FROM models")
        return rows[0]["n"] if rows else 0

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    async def get_benchmarks(self) -> list[dict[str, Any]]:
        """Devuelve todos los benchmarks de la tabla benchmarks."""
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT * FROM benchmarks")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Model benchmarks
    # ------------------------------------------------------------------

    async def upsert_model_benchmark(
        self,
        model_id: str,
        benchmark_slug: str,
        score: float | None,
        raw_value: str,
        fetched_at: int,
        source: str,
    ) -> None:
        """Inserta o actualiza un score de benchmark para un modelo."""
        assert self._db is not None
        await self._db.execute(
            """INSERT INTO model_benchmarks
               (model_id, benchmark_slug, score, raw_value, fetched_at, source)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(model_id, benchmark_slug) DO UPDATE SET
                   score      = excluded.score,
                   raw_value  = excluded.raw_value,
                   fetched_at = excluded.fetched_at,
                   source     = excluded.source""",
            (model_id, benchmark_slug, score, raw_value, fetched_at, source),
        )
        await self._db.commit()

    async def list_model_benchmarks(
        self,
        benchmark_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista filas de model_benchmarks, opcionalmente filtradas por slug."""
        assert self._db is not None
        if benchmark_slug:
            rows = await self._db.execute_fetchall(
                "SELECT * FROM model_benchmarks WHERE benchmark_slug = ?",
                (benchmark_slug,),
            )
        else:
            rows = await self._db.execute_fetchall("SELECT * FROM model_benchmarks")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase profiles
    # ------------------------------------------------------------------

    async def get_phase_profile(self, phase: str) -> list[dict[str, Any]]:
        """Devuelve los pesos de un perfil de fase."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT * FROM phase_profiles WHERE phase = ?",
            (phase,),
        )
        result = []
        for r in rows:
            row = dict(r)
            # Convertir is_feature_factor a bool
            row["is_feature_factor"] = bool(row.get("is_feature_factor", 0))
            result.append(row)
        return result

    async def replace_phase_profile(
        self,
        phase: str,
        weights: list[dict[str, Any]],
    ) -> int:
        """Reemplaza completamente los pesos de un perfil de fase.

        Borra todas las filas existentes para `phase` e inserta las nuevas.
        weights es una lista de dicts con keys: benchmark_slug, weight, is_feature_factor.

        Returns:
            Cantidad de filas insertadas.
        """
        assert self._db is not None
        await self._db.execute("DELETE FROM phase_profiles WHERE phase = ?", (phase,))
        inserted = 0
        for w in weights:
            slug = w.get("benchmark_slug")
            if not slug:
                continue
            weight_val = float(w.get("weight", 0.0))
            is_ff = 1 if w.get("is_feature_factor") else 0
            await self._db.execute(
                """INSERT INTO phase_profiles (phase, benchmark_slug, weight, is_feature_factor)
                   VALUES (?, ?, ?, ?)""",
                (phase, slug, weight_val, is_ff),
            )
            inserted += 1
        await self._db.commit()
        return inserted

    async def get_registered_phases(self) -> list[str]:
        """Devuelve los nombres de fase distintos registrados en phase_profiles."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT DISTINCT phase FROM phase_profiles ORDER BY phase"
        )
        return [r["phase"] for r in rows]

    def _load_phase_seed_metadata(self) -> dict[str, dict[str, Any]]:
        """Carga metadata por fase desde los seed files disponibles."""
        metadata_by_phase: dict[str, dict[str, Any]] = {}
        for seed_path in sorted(SEEDS_DIR.glob("*_phase_weights.json")):
            try:
                data = json.loads(seed_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            phase = data.get("phase", seed_path.stem.replace("_phase_weights", ""))
            metadata = data.get("metadata") or {}
            if isinstance(metadata, dict):
                metadata_by_phase[phase] = metadata
        return metadata_by_phase

    async def get_phase_summary(self, phase_slug: str) -> dict[str, int]:
        """Devuelve conteos agregados para una fase registrada."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            """SELECT benchmark_slug, weight, is_feature_factor
               FROM phase_profiles
               WHERE phase = ?""",
            (phase_slug,),
        )
        seed_metadata = self._load_phase_seed_metadata().get(phase_slug, {})
        reserved_zero = seed_metadata.get("reserved_zero", [])
        reserved_slugs = set(reserved_zero if isinstance(reserved_zero, list) else [])
        return {
            "weights_count": len(rows),
            "active_benchmarks_count": sum(1 for row in rows if float(row["weight"] or 0) > 0),
            "reserved_benchmarks_count": sum(
                1
                for row in rows
                if float(row["weight"] or 0) == 0 and row["benchmark_slug"] in reserved_slugs
            ),
            "feature_factors_count": sum(1 for row in rows if int(row["is_feature_factor"] or 0) == 1),
        }

    async def get_last_scrape_finished_at(self) -> int | None:
        """Devuelve el timestamp finished_at más reciente entre scrape_runs."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT MAX(finished_at) AS finished_at FROM scrape_runs WHERE finished_at IS NOT NULL"
        )
        value = rows[0]["finished_at"] if rows else None
        return int(value) if value is not None else None

    async def get_phases(self) -> list[dict[str, Any]]:
        """Devuelve fases registradas con metadata y conteos agregados."""
        phases = await self.get_registered_phases()
        seed_metadata = self._load_phase_seed_metadata()
        last_finished_at = await self.get_last_scrape_finished_at()
        result: list[dict[str, Any]] = []
        for phase in phases:
            summary = await self.get_phase_summary(phase)
            metadata = seed_metadata.get(phase, {})
            result.append({
                "slug": phase,
                "description": str(metadata.get("description", "")),
                "last_ranking_computed_at": last_finished_at,
                **summary,
            })
        return result

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    async def get_alias(self, openrouter_id: str) -> dict[str, Any] | None:
        """Devuelve la fila de alias para un openrouter_id, o None si no existe."""
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT * FROM model_aliases WHERE openrouter_id = ?",
            (openrouter_id,),
        )
        return dict(rows[0]) if rows else None

    async def upsert_alias(
        self,
        openrouter_id: str,
        artificial_analysis_name: str | None,
        bfcl_key: str | None,
        match_confidence: float | None,
    ) -> None:
        """Inserta o actualiza una fila en model_aliases."""
        import time as _time
        assert self._db is not None
        updated_at = int(_time.time())
        await self._db.execute(
            """INSERT INTO model_aliases
               (openrouter_id, artificial_analysis_name, bfcl_key, match_confidence, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(openrouter_id) DO UPDATE SET
                   artificial_analysis_name = excluded.artificial_analysis_name,
                   bfcl_key                 = excluded.bfcl_key,
                   match_confidence         = excluded.match_confidence,
                   updated_at               = excluded.updated_at""",
            (openrouter_id, artificial_analysis_name, bfcl_key, match_confidence, updated_at),
        )
        await self._db.commit()

    async def list_aliases(self) -> list[dict[str, Any]]:
        """Devuelve todas las filas de model_aliases."""
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT * FROM model_aliases")
        return [dict(r) for r in rows]

    async def list_all_model_slugs(self) -> list[str]:
        """Devuelve todos los IDs (slugs) de la tabla models."""
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT id FROM models")
        return [r["id"] for r in rows]

    # ------------------------------------------------------------------
    # Scrape runs
    # ------------------------------------------------------------------

    async def record_scrape_run(
        self,
        source: str,
        started_at: int,
        finished_at: int | None,
        status: str,
        error: str | None,
        rows_updated: int,
        aliases_missed: int = 0,
    ) -> None:
        """Registra una ejecución de scraper."""
        assert self._db is not None
        await self._db.execute(
            """INSERT INTO scrape_runs
               (source, started_at, finished_at, status, error, rows_updated, aliases_missed)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source, started_at, finished_at, status, error, rows_updated, aliases_missed),
        )
        await self._db.commit()

    async def get_scrape_health(self, source: str | None = None) -> list[dict]:
        """Devuelve la ejecución más reciente por fuente, o la más reciente de una fuente específica."""
        assert self._db is not None
        if source:
            rows = await self._db.execute_fetchall(
                "SELECT * FROM scrape_runs WHERE source = ? ORDER BY started_at DESC LIMIT 1",
                (source,),
            )
        else:
            rows = await self._db.execute_fetchall(
                """SELECT * FROM scrape_runs
                   WHERE (source, started_at) IN (
                       SELECT source, MAX(started_at) FROM scrape_runs GROUP BY source
                   )"""
            )
        return [dict(r) for r in rows]

    async def list_scrape_runs(
        self,
        source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista ejecuciones de scraper, opcionalmente filtradas por source."""
        assert self._db is not None
        if source:
            rows = await self._db.execute_fetchall(
                "SELECT * FROM scrape_runs WHERE source = ? ORDER BY started_at DESC LIMIT ?",
                (source, limit),
            )
        else:
            rows = await self._db.execute_fetchall(
                "SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in rows]
