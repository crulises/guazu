#!/bin/zsh
# Ejemplo: copiar a ~/.zshenv (ver docs/03, "PATH en shells no interactivos"). No se ejecuta desde el repo.
# Entorno de desarrollo (guazu). Vive en .zshenv porque zsh lo lee SIEMPRE: shells interactivos,
# de login y tambien los no interactivos (scripts, make, herramientas como Claude Code o un IDE).
# .zshrc solo lo lee un shell interactivo, por eso Docker, Flutter, adb, psql, etc. "no estaban".
# Solo agrega lo que existe y no duplica entradas: se puede releer sin que crezca el PATH.

export LANG=en_US.UTF-8
export JAVA_HOME=/opt/homebrew/opt/openjdk@17
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export ANDROID_SDK_ROOT=$ANDROID_HOME

_guazu_path() {
  local d
  for d in "$@"; do
    [ -d "$d" ] || continue
    case ":$PATH:" in *":$d:"*) ;; *) PATH="$PATH:$d" ;; esac
  done
}

# Adelante: lo que debe ganarle a los atajos de macOS (por ejemplo el stub de /usr/bin/java).
_guazu_front() {
  local d
  for d in "$@"; do
    [ -d "$d" ] || continue
    case ":$PATH:" in *":$d:"*) PATH="${PATH//:$d:/:}"; PATH="${PATH#$d:}"; PATH="${PATH%:$d}" ;; esac
    PATH="$d:$PATH"
  done
}

_guazu_path /opt/homebrew/bin /opt/homebrew/sbin
_guazu_front \
  "$HOME/development/flutter/bin" \
  "$JAVA_HOME/bin" \
  "$ANDROID_HOME/cmdline-tools/latest/bin" \
  "$ANDROID_HOME/platform-tools" \
  "$ANDROID_HOME/emulator" \
  /opt/homebrew/opt/libpq/bin
_guazu_path \
  "$HOME/.pub-cache/bin" \
  /Applications/Docker.app/Contents/Resources/bin \
  "$HOME/.docker/bin"

unset -f _guazu_path _guazu_front
export PATH
