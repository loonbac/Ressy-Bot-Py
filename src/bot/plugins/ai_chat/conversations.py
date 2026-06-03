from __future__ import annotations

from typing import Any

from .client import AIChatClient
from .database import AIChatDatabase


def estimate_tokens(text: str) -> int:
    """Estimación barata de tokens (~4 chars/token) sin dependencias de tokenizer."""
    if not text:
        return 0
    return len(text) // 4 + 1


def _messages_tokens(messages: list[dict[str, str]]) -> int:
    # +4 por mensaje aproxima el overhead de formato role/contenido.
    return sum(estimate_tokens(m.get("content", "")) + 4 for m in messages)


def _block(title: str, items: list[str]) -> dict[str, str]:
    body = "\n".join(f"- {i}" for i in items)
    return {"role": "system", "content": f"{title}\n{body}"}


class ConversationStore:
    """Motor de memoria jerárquica del plugin ai_chat.

    Capas (de mayor a menor permanencia):
      1. Memoria de largo plazo: hechos globales del servidor + por usuario.
      2. Resumen rodante: gist persistente de la conversación ya podada.
      3. Ventana reciente: mensajes verbatim acotados por presupuesto de tokens.
    """

    def __init__(self, db: AIChatDatabase, client: AIChatClient | None = None) -> None:
        self.db = db
        self.client = client

    async def build_messages(
        self,
        user_id: str,
        channel_id: str,
        prompt: str,
        system_prompt: str,
        limit: int,
        *,
        user_name: str | None = None,
        token_budget: int = 200_000,
        memory_enabled: bool = True,
        summary_enabled: bool = True,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # Identidad del usuario actual: la IA SIEMPRE debe saber con quién habla.
        if user_name:
            identity = f"Estás conversando con el usuario «{user_name}» (ID Discord: {user_id})."
        else:
            identity = f"Estás conversando con el usuario de ID Discord {user_id}."
        messages.append({"role": "system", "content": identity})

        if memory_enabled:
            global_facts = await self.db.list_memories("global", "")
            user_facts = await self.db.list_memories("user", str(user_id))
            if global_facts:
                messages.append(_block("Memoria global del servidor:", [m["content"] for m in global_facts]))
            if user_facts:
                messages.append(_block("Lo que recuerdas de este usuario:", [m["content"] for m in user_facts]))

        if summary_enabled:
            summary = await self.db.get_summary(user_id, channel_id)
            if summary:
                messages.append({"role": "system", "content": f"Resumen de la conversación previa:\n{summary}"})

        # Ventana reciente recortada al presupuesto restante de tokens.
        history = await self.db.recent_messages(user_id, channel_id, max(1, limit))
        remaining = token_budget - _messages_tokens(messages) - estimate_tokens(prompt)
        history = self._fit_budget(history, remaining)
        messages.extend(history)

        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _fit_budget(history: list[dict[str, str]], budget: int) -> list[dict[str, str]]:
        """Conserva los mensajes MÁS RECIENTES que entren en el presupuesto."""
        if budget <= 0:
            return []
        kept: list[dict[str, str]] = []
        used = 0
        for msg in reversed(history):
            cost = estimate_tokens(msg.get("content", "")) + 4
            if used + cost > budget:
                break
            kept.append(msg)
            used += cost
        kept.reverse()
        return kept

    async def remember_exchange(
        self,
        user_id: str,
        channel_id: str,
        prompt: str,
        reply: str,
        *,
        cfg: dict[str, str] | None = None,
    ) -> None:
        await self.db.add_message(user_id, channel_id, "user", prompt)
        await self.db.add_message(user_id, channel_id, "assistant", reply)
        if cfg is not None:
            await self.maybe_summarize(user_id, channel_id, cfg)

    async def maybe_summarize(self, user_id: str, channel_id: str, cfg: dict[str, str]) -> bool:
        """Funde mensajes viejos en el resumen rodante y poda la tabla.

        Devuelve True si resumió. Fail-safe: si el modelo falla NO poda mensajes,
        para no perder información (reintenta en el próximo turno).
        """
        if cfg.get("summary_enabled", "true") != "true" or self.client is None:
            return False
        keep = max(1, int(cfg.get("max_context_messages", "60")))
        trigger = max(1, int(cfg.get("summary_trigger_messages", "40")))
        total = await self.db.count_messages(user_id, channel_id)
        if total <= keep + trigger:
            return False

        all_msgs = await self.db.messages_asc(user_id, channel_id)
        overflow = all_msgs[:-keep]
        if not overflow:
            return False

        previous = await self.db.get_summary(user_id, channel_id)
        analysis_model = cfg.get("analysis_model")
        try:
            result = await self.client.summarize_and_extract(
                previous, [{"role": m["role"], "content": m["content"]} for m in overflow], analysis_model
            )
        except Exception:
            # No podar: preservar mensajes hasta poder resumir bien.
            return False

        last_id = int(overflow[-1]["id"])
        await self.db.set_summary(user_id, channel_id, result["summary"], last_id)
        await self.db.prune_messages_through(user_id, channel_id, last_id)

        if cfg.get("memory_enabled", "true") == "true":
            for fact in result.get("facts", []):
                await self.db.add_memory("user", str(user_id), fact, source="auto")
        return True
