from __future__ import annotations

from .database import AIChatDatabase


class ConversationStore:
    def __init__(self, db: AIChatDatabase) -> None:
        self.db = db

    async def build_messages(self, user_id: str, channel_id: str, prompt: str, system_prompt: str, limit: int) -> list[dict[str, str]]:
        history = await self.db.recent_messages(user_id, channel_id, max(1, limit))
        return [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": prompt}]

    async def remember_exchange(self, user_id: str, channel_id: str, prompt: str, reply: str) -> None:
        await self.db.add_message(user_id, channel_id, "user", prompt)
        await self.db.add_message(user_id, channel_id, "assistant", reply)
