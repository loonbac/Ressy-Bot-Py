import io

import discord
from discord.ext import commands

from .banner import generate_welcome_banner


def _format_text(template: str, member: discord.Member) -> str:
    guild = member.guild
    return (
        template.replace("{user}", member.mention)
        .replace("{user_name}", member.display_name)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or len(guild.members)))
        .replace("{{user}}", member.mention)
    )


def _parse_color(raw: str, fallback: int = 0x23856B) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(0, min(0xFFFFFF, value))


class WelcomeCog(commands.Cog):
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self._last_message_id: dict[int, int] = {}

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
        embed.set_footer(text=f"{member.guild.name} · Miembro #{member.guild.member_count}")
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
        await self.send_welcome(member)


async def setup(bot, db):
    await bot.add_cog(WelcomeCog(db, bot))
