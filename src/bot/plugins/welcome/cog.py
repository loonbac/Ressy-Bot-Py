import io

import discord
from discord.ext import commands

from .banner import generate_welcome_banner


def _member_rank(member: discord.Member) -> int:
    """Return the join-order rank of `member` among non-bot members.

    Counts how many non-bot members joined the guild before (or at) this one.
    Falls back to total non-bot count if join timestamps are missing.
    """
    guild = member.guild
    target_join = member.joined_at
    if target_join is None:
        return sum(1 for m in guild.members if not m.bot) or (guild.member_count or 0)
    rank = sum(
        1
        for m in guild.members
        if not m.bot and m.joined_at is not None and m.joined_at <= target_join
    )
    return rank or 1


def _format_text(template: str, member: discord.Member) -> str:
    guild = member.guild
    rank = _member_rank(member)
    return (
        template.replace("{user}", member.mention)
        .replace("{user_name}", member.display_name)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(rank))
        .replace("{{user}}", member.mention)
    )


def _parse_color(raw: str, fallback: int = 0x23856B) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(0, min(0xFFFFFF, value))


class WelcomeCog(commands.Cog):
    def __init__(self, db, bot, config_manager=None):
        self.db = db
        self.bot = bot
        self.config_manager = config_manager
        self._last_message_id: dict[int, int] = {}

    def _configured_guild_id(self) -> int | None:
        if self.config_manager is None:
            return None
        raw = self.config_manager.get("guild_id") or ""
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def _get_config(self) -> dict[str, str]:
        rows = await self.db.execute_fetchall("SELECT key, value FROM welcome_config")
        return {r[0]: r[1] for r in rows}

    async def _build_banner_file(
        self, member: discord.Member, cfg: dict[str, str]
    ) -> discord.File | None:
        accent_color = _parse_color(cfg.get("embed_color", "2326507"))
        try:
            banner_bytes = await generate_welcome_banner(
                avatar_url=str(member.display_avatar.replace(size=512, format="png").url),
                username=member.name,
                title_text="BIENVENIDO/A",
                background_url=cfg.get("welcome_image_url") or "",
                accent_color=accent_color,
            )
        except Exception:
            return None
        return discord.File(io.BytesIO(banner_bytes), filename="welcome.png")

    async def _build_embed(self, member: discord.Member, cfg: dict[str, str]) -> discord.Embed:
        title = _format_text(cfg.get("embed_title") or "Bienvenid@ {user_name}", member)
        description = _format_text(cfg.get("welcome_message", ""), member)
        color = _parse_color(cfg.get("embed_color", "2326507"))
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{member.guild.name} · Miembro #{_member_rank(member)}")
        return embed

    async def send_welcome(
        self, member: discord.Member, *, force: bool = False
    ) -> dict[str, object]:
        """Send welcome embed + banner. Returns status dict.

        force=True ignores the enabled toggle (used by /test).
        """
        cfg = await self._get_config()
        result: dict[str, object] = {
            "enabled": cfg.get("enabled", "true") == "true",
            "sent_channel": False,
            "sent_dm": False,
            "channel_error": None,
            "dm_error": None,
        }

        if not force and not result["enabled"]:
            return result

        channel_id_raw = cfg.get("welcome_channel_id") or ""
        channel = None
        if channel_id_raw:
            try:
                channel = self.bot.get_channel(int(channel_id_raw))
            except ValueError:
                channel = None

        embed = await self._build_embed(member, cfg)
        banner_file = await self._build_banner_file(member, cfg)
        if banner_file is not None:
            embed.set_image(url="attachment://welcome.png")

        if channel is not None:
            if cfg.get("delete_previous", "false") == "true":
                prev_id = self._last_message_id.get(channel.id)
                if prev_id:
                    try:
                        prev = await channel.fetch_message(prev_id)
                        await prev.delete()
                    except Exception:
                        pass
            try:
                kwargs: dict = {"embed": embed}
                if banner_file is not None:
                    kwargs["file"] = banner_file
                sent = await channel.send(**kwargs)
                self._last_message_id[channel.id] = sent.id
                result["sent_channel"] = True
            except Exception as exc:
                result["channel_error"] = str(exc)

        if cfg.get("dm_enabled", "false") == "true":
            try:
                dm_kwargs: dict = {"embed": embed}
                dm_file = await self._build_banner_file(member, cfg)
                if dm_file is not None:
                    dm_kwargs["file"] = dm_file
                await member.send(**dm_kwargs)
                result["sent_dm"] = True
            except Exception as exc:
                result["dm_error"] = str(exc)

        return result

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        target_guild = self._configured_guild_id()
        if target_guild is not None and member.guild.id != target_guild:
            return
        await self.send_welcome(member)


async def setup(bot, db, config_manager=None):
    await bot.add_cog(WelcomeCog(db, bot, config_manager))
