FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Runtime deps: ffmpeg (transcode) + yt-dlp (resuelve los streams de YouTube).
# Sin navegador: ya no se necesita Firefox/Xvfb/PulseAudio.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      python3 \
      procps \
      curl \
      ca-certificates \
 && curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux \
      -o /usr/local/bin/yt-dlp \
 && chmod a+rx /usr/local/bin/yt-dlp \
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

# App source
COPY manager.js worker.js entrypoint.sh ./
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
