#!/usr/bin/env bash
# Verifica el entorno de desarrollo (Doc 6 §Lista de verificación). Dice qué falta; no instala.
cd "$(dirname "$0")/.."
fallas=0
ok()   { printf '  OK     %-28s %s\n' "$1" "$2"; }
falta(){ printf '  FALTA  %-28s %s\n' "$1" "$2"; fallas=$((fallas + 1)); }
aviso(){ printf '  AVISO  %-28s %s\n' "$1" "$2"; }

version() { "$@" 2>&1 | head -1; }

# Flutter 3.50.0 / Dart 3.14
if command -v flutter >/dev/null; then
  v=$(flutter --version 2>/dev/null | head -1)
  case "$v" in *"3.50.0"*) ok flutter "$v" ;; *) falta flutter "se esperaba 3.50.0: $v" ;; esac
else falta flutter "no está en el PATH"; fi

# JDK 17
if command -v java >/dev/null && java -version 2>&1 | grep -q 'version "17'; then
  ok "jdk 17" "$(java -version 2>&1 | head -1)"
else falta "jdk 17" "JAVA_HOME=/opt/homebrew/opt/openjdk@17"; fi

# Android
if [ -n "${ANDROID_HOME:-}" ] && [ -d "$ANDROID_HOME/ndk/28.2.13676358" ]; then ok "android sdk + ndk" "$ANDROID_HOME"
else falta "android sdk + ndk" "ANDROID_HOME y ndk;28.2.13676358"; fi
if command -v avdmanager >/dev/null && avdmanager list avd 2>/dev/null | grep -q guazu_pixel; then ok "emulador guazu_pixel" ""
else falta "emulador guazu_pixel" "ver Doc 6 §Pasos"; fi

# Docker corriendo
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  mem=$(docker info --format '{{.MemTotal}}' 2>/dev/null)
  if [ "${mem:-0}" -ge 8000000000 ]; then ok docker "$((mem / 1073741824)) GB"
  else aviso docker "menos de 8 GB: subir en Settings > VM resources"; fi
else falta docker "no corre o no está en el PATH"; fi

# Supabase CLI 3.1.0 (la fija el CI)
if command -v supabase >/dev/null; then
  v=$(supabase --version 2>/dev/null | head -1)
  [ "$v" = "3.1.0" ] && ok supabase "$v" || falta supabase "se esperaba 3.1.0 (el CI la fija): $v"
else falta supabase "no instalado"; fi

command -v psql >/dev/null && ok psql "$(psql --version)" || falta psql "brew install libpq"
if command -v python3.12 >/dev/null; then ok python3.12 "$(python3.12 --version)"; else falta python3.12 "brew install python@3.12"; fi
if gh auth status >/dev/null 2>&1; then ok gh "logueado"; else falta gh "gh auth login"; fi
if command -v fly >/dev/null; then
  if fly auth whoami >/dev/null 2>&1; then ok fly "logueado"; else aviso fly "fly auth login"; fi
else falta fly "brew install flyctl"; fi

# iOS (solo macOS)
if [ "$(uname)" = "Darwin" ]; then
  if xcodebuild -version >/dev/null 2>&1; then ok xcode "$(xcodebuild -version | head -1)"; else falta xcode "instalar Xcode y aceptar la licencia"; fi
  command -v pod >/dev/null && ok cocoapods "$(pod --version 2>/dev/null | tail -1)" || falta cocoapods "brew install cocoapods"
fi

echo
if [ "$fallas" -eq 0 ]; then echo "Entorno listo."; else echo "Faltan $fallas cosas."; exit 1; fi
