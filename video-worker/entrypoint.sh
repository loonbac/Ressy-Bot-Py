#!/usr/bin/env bash
set -e

# Shared infra started ONCE per container: dbus + PulseAudio daemon. Each worker
# then loads its own null sink and spawns its own Xvfb display (see worker.js).

echo "[entrypoint] starting dbus..."
mkdir -p /tmp/dbus
eval "$(dbus-launch --sh-syntax)"
export DBUS_SESSION_BUS_ADDRESS

echo "[entrypoint] starting PulseAudio daemon..."
pulseaudio --start --exit-idle-time=-1 --disallow-exit >/tmp/pulse.log 2>&1 || true
sleep 1
echo "[entrypoint] pulse status:"
pactl info 2>/dev/null | head -n 3 || echo "  (pactl not ready yet)"

echo "[entrypoint] ready. exec: $*"
exec "$@"
