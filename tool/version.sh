#!/usr/bin/env bash
# Versión del próximo APK de una app. Uso: tool/version.sh <cliente|negocio>
# Imprime: "<version> <commit> <build-number>".
#
# - `0.0.x` es el número de compilación (Doc 2 §Versionado). La SERIE (0.0, 0.1, ...) sale de
#   `version:` en app/apps/<app>/pubspec.yaml: la cambia una persona al cerrar un ciclo.
# - El último número sube solo en cada ejecución (cada `make apk-<app>`). Al cambiar de serie
#   vuelve a empezar (0.1.0 es la primera release; después 0.1.1, ...).
# - El contador vive en el .git COMPARTIDO (no en el árbol de trabajo): no genera cambios ni
#   conflictos y los worktrees cuentan juntos. Un contador por app.
#   (VERSION_COUNTER_FILE lo redirige a otro archivo: sirve para probar el script.)
set -euo pipefail
app="${1:?uso: tool/version.sh <cliente|negocio>}"
cd "$(dirname "$0")/.."
pubspec="app/apps/$app/pubspec.yaml"
[ -f "$pubspec" ] || { echo "no existe $pubspec" >&2; exit 1; }

serie=$(sed -n 's/^version: *\([0-9][0-9]*\.[0-9][0-9]*\)\..*/\1/p' "$pubspec")
[ -n "$serie" ] || { echo "no pude leer la versión de $pubspec" >&2; exit 1; }

contador="${VERSION_COUNTER_FILE:-$(cd "$(git rev-parse --git-common-dir)" && pwd)/guazu-apk-version-$app}"
serie_previa=""
patch=0
if [ -f "$contador" ]; then read -r serie_previa patch < "$contador"; fi
if [ "$serie_previa" = "$serie" ]; then
  patch=$((patch + 1))
elif [ -z "$serie_previa" ]; then
  patch=1
else
  patch=0
fi
echo "$serie $patch" > "$contador"

commit=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain)" ]; then commit="$commit+local"; fi
# versionCode de Android: tiene que crecer siempre para poder instalar encima.
echo "$serie.$patch $commit $(date +%s)"
