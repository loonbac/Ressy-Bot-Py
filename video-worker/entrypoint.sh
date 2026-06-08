#!/usr/bin/env bash
set -e

# El worker ya no usa navegador ni audio del sistema: yt-dlp resuelve el stream
# y ffmpeg lo transcodifica directo. No hace falta arrancar dbus/PulseAudio/Xvfb.

echo "[entrypoint] yt-dlp: $(yt-dlp --version 2>/dev/null || echo 'NO ENCONTRADO')"
echo "[entrypoint] ready. exec: $*"
exec "$@"
