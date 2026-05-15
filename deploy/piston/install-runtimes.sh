#!/usr/bin/env bash
# Instala los runtimes de lenguaje en una instancia Piston self-host recién
# levantada. Piston arranca SIN lenguajes; hay que instalarlos vía su API.
#
# Uso:
#   PISTON_URL=http://localhost:2000/api/v2 ./install-runtimes.sh
#   (o pasa la URL como primer argumento)
#
# En Coolify: ejecútalo una vez desde un terminal con acceso al contenedor,
# o desde tu máquina apuntando a la URL pública del servicio Piston.

set -euo pipefail

PISTON_URL="${1:-${PISTON_URL:-http://localhost:2000/api/v2}}"
PISTON_URL="${PISTON_URL%/}"

# Lenguaje:version. Ajusta versiones si Piston ofrece otras (consulta
# GET $PISTON_URL/packages para ver disponibles).
RUNTIMES=(
  "python:3.12.0"
  "javascript:20.11.1"
  "typescript:5.0.3"
  "bash:5.2.0"
  "rust:1.68.2"
  "go:1.16.2"
  "java:15.0.2"
  "c++:10.2.0"
  "c:10.2.0"
)

echo "Piston API: $PISTON_URL"
echo "Esperando a que Piston responda..."
until curl -fsS "$PISTON_URL/runtimes" >/dev/null 2>&1; do
  sleep 3
  echo "  ...todavía no responde, reintentando"
done
echo "Piston listo. Instalando runtimes:"

for entry in "${RUNTIMES[@]}"; do
  lang="${entry%%:*}"
  ver="${entry##*:}"
  echo -n "  -> $lang $ver ... "
  code=$(curl -s -o /tmp/piston_install.json -w "%{http_code}" \
    -X POST "$PISTON_URL/packages" \
    -H 'Content-Type: application/json' \
    -d "{\"language\":\"$lang\",\"version\":\"$ver\"}")
  if [ "$code" = "200" ]; then
    echo "OK"
  else
    echo "FALLO (HTTP $code): $(cat /tmp/piston_install.json)"
  fi
done

echo
echo "Runtimes instalados. Verifica con:"
echo "  curl -s $PISTON_URL/runtimes | jq ."
