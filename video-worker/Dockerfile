FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# ffmpeg/ffprobe estáticos (>=7) desde una imagen del registry de Docker, NO
# desde el CDN de releases de GitHub (que devolvía 504 en el tar grande de
# BtbN). El splash instantáneo depende de que find_stream_info no bloquee en el
# input de pipe vacío, validado en ffmpeg >= 7.
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /ffprobe /usr/local/bin/

# yt-dlp resuelve/baja los streams (single-binary, vía curl con reintentos).
# La animación de carga es un asset de video (splash.mp4), no drawtext: sin fuentes.
# Sin navegador: ya no se necesita Firefox/Xvfb/PulseAudio.
RUN apt-get update && apt-get install -y --no-install-recommends \
      procps \
      curl \
      ca-certificates \
 && curl -fsSL --retry 8 --retry-delay 3 --retry-all-errors --retry-connrefused \
      https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux \
      -o /usr/local/bin/yt-dlp \
 && chmod a+rx /usr/local/bin/yt-dlp /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
 && rm -rf /var/lib/apt/lists/*

# pnpm via corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

# Non-root user
RUN useradd -m -u 1001 app

WORKDIR /app

# Install deps first (cache layer). Native deps fetch prebuilt binaries here.
# pnpm-workspace.yaml declara onlyBuiltDependencies (pnpm 11 ya no lee el campo
# pnpm de package.json) para que no aborte con ERR_PNPM_IGNORED_BUILDS.
COPY package.json pnpm-workspace.yaml ./
RUN pnpm install

# App source + asset del splash de carga
COPY manager.js worker.js entrypoint.sh splash.mp4 ./
RUN chmod +x entrypoint.sh && chown -R app:app /app

USER app
ENV HOME=/home/app \
    WIDTH=1280 \
    HEIGHT=720 \
    FPS=30 \
    MANAGER_PORT=8081 \
    MAX_WORKERS=5

EXPOSE 8081

ENTRYPOINT ["./entrypoint.sh"]
CMD ["node", "manager.js"]
