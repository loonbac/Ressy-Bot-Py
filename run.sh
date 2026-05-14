#!/bin/bash
# Run both the main bot and the YouTube callback server

# Start callback server in background
echo "Starting YouTube callback server on port 8001..."
uv run python -m src.bot.plugins.youtube_notifier.callback_server &
CALLBACK_PID=$!

# Run main bot (blocks)
echo "Starting main bot on port 8000..."
uv run ressy-bot

# When main bot exits, stop callback server
kill $CALLBACK_PID 2>/dev/null
