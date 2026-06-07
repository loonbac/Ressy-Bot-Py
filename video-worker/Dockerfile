FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Runtime deps: Firefox, ffmpeg (x11grab+pulse), virtual display, audio, fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
      firefox-esr \
      ffmpeg \
      xvfb \
      x11-utils \
      x11-xserver-utils \
      pulseaudio \
      pulseaudio-utils \
      dbus-x11 \
      procps \
      curl \
      ca-certificates \
      fonts-liberation \
      fonts-noto-color-emoji \
      fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

# pnpm via corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

# Non-root user (Firefox + PulseAudio dislike running as root)
RUN useradd -m -u 1001 app

WORKDIR /app

# Install deps first (cache layer). Native deps fetch prebuilt binaries here.
COPY package.json ./
RUN pnpm install

# App source
COPY manager.js worker.js player.html entrypoint.sh ./
RUN chmod +x entrypoint.sh && chown -R app:app /app

USER app
ENV HOME=/home/app \
    WIDTH=1280 \
    HEIGHT=720 \
    FPS=30 \
    FIREFOX_BIN=firefox-esr \
    MANAGER_PORT=8081 \
    HTTP_PORT=8080 \
    MAX_WORKERS=5

EXPOSE 8081

ENTRYPOINT ["./entrypoint.sh"]
CMD ["node", "manager.js"]
