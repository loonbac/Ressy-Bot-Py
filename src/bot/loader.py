import importlib.util
import os
from pathlib import Path

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager


async def load_cogs(
    bot: Bot, config_manager: ConfigManager, cog_dir: str = "src/bot/cogs"
) -> tuple[list[str], list[tuple[str, str]]]:
    loaded: list[str] = []
    errors: list[tuple[str, str]] = []

    cog_path = Path(cog_dir)
    if not cog_path.exists():
        print(f"Warning: cogs directory {cog_dir} does not exist")
        return loaded, errors

    for file_path in sorted(cog_path.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        module_name = file_path.stem
        try:
            spec = importlib.util.spec_from_file_location(
                f"src.bot.cogs.{module_name}", file_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {file_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            setup = getattr(module, "setup", None)
            if setup is None:
                raise ImportError(f"No setup() function in {file_path}")
            await setup(bot, config_manager)
            loaded.append(module_name)
            print(f"Loaded cog: {module_name}")
        except Exception as exc:
            errors.append((module_name, str(exc)))
            print(f"Failed to load cog {module_name}: {exc}")

    return loaded, errors
