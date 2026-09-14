#!/usr/bin/env bash
# Install this skill into one Hermes profile, or into every profile on the machine.
#
#   ./install.sh              install into the default/shared profile  (<hermes>/skills/)
#   ./install.sh learning     install into profiles/learning
#   ./install.sh --all        install into the shared tree + every profile
#
# HERMES_HOME is honoured; on Windows %LOCALAPPDATA%\hermes is detected automatically.
# Override explicitly with:  HERMES_HOME=/path/to/hermes ./install.sh --all
#
# Safety: the script never removes anything outside <dest>/scripts, and it refuses to
# touch a destination that resolves to this checkout itself.
set -euo pipefail

SKILL_NAME="bilibili-video-report"
CATEGORY="media"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ────────────────────────────────────────────────────────────────
# Normalise a path so MSYS-style (/c/Users/x) and native (C:/Users/x) forms compare equal.
norm() {
  local p="${1//\\//}"
  p="${p%/}"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$p" 2>/dev/null || printf '%s' "$p"
  else
    printf '%s' "$p"
  fi
}

# Resolve the Hermes home. HERMES_HOME may point at a PROFILE dir
# (<root>/profiles/<name>) when set by an active Hermes session — step up to the root.
resolve_root() {
  local candidates=() c
  [ -n "${HERMES_HOME:-}" ] && candidates+=("$HERMES_HOME")
  [ -n "${LOCALAPPDATA:-}" ] && candidates+=("${LOCALAPPDATA}/hermes")
  candidates+=("$HOME/.hermes")
  for c in "${candidates[@]}"; do
    c="$(norm "$c")"
    [ -n "$c" ] || continue
    case "$c" in
      */profiles/*) printf '%s' "${c%%/profiles/*}"; return 0 ;;
    esac
    if [ -d "$c/skills" ] || [ -d "$c/profiles" ]; then
      printf '%s' "$c"; return 0
    fi
  done
  return 1
}

if ! HERMES_ROOT="$(resolve_root)"; then
  echo "Could not locate a Hermes home. Set it explicitly:" >&2
  echo "  HERMES_HOME=/path/to/hermes $0 ${1:-}" >&2
  exit 1
fi
echo "Hermes home: $HERMES_ROOT"

# ── install ────────────────────────────────────────────────────────────────
install_into() {  # $1 = skills root, e.g. <hermes>/skills
  local skills_root="$1" dest
  dest="$(norm "$skills_root/$CATEGORY/$SKILL_NAME")"

  if [ "$dest" = "$(norm "$SRC")" ]; then
    echo "skip (this checkout IS the install target): $dest"
    return 0
  fi

  mkdir -p "$(norm "$skills_root/$CATEGORY")"
  mkdir -p "$dest"
  cp "$SRC/SKILL.md" "$dest/SKILL.md"
  rm -rf "$dest/scripts"          # only ever this subdir
  cp -r "$SRC/scripts" "$dest/scripts"

  if [ ! -s "$dest/SKILL.md" ] || [ ! -d "$dest/scripts" ]; then
    echo "install FAILED (incomplete): $dest" >&2
    return 1
  fi
  echo "installed → $dest  ($(ls -1 "$dest/scripts" | wc -l | tr -d ' ') scripts)"
}

case "${1:-}" in
  "" )
    install_into "$HERMES_ROOT/skills"
    ;;
  --all )
    install_into "$HERMES_ROOT/skills"
    if [ -d "$HERMES_ROOT/profiles" ]; then
      for p in "$HERMES_ROOT"/profiles/*/; do
        [ -d "$p" ] || continue
        install_into "${p%/}/skills"
      done
    fi
    ;;
  * )
    if [ ! -d "$HERMES_ROOT/profiles/$1" ]; then
      echo "no such profile: $1" >&2
      echo "available: $(ls -1 "$HERMES_ROOT/profiles" 2>/dev/null | tr '\n' ' ')" >&2
      exit 1
    fi
    install_into "$HERMES_ROOT/profiles/$1/skills"
    ;;
esac

echo
case "${1:-}" in
  --all )   echo "verify with:  hermes skills list | grep bilibili-video   (repeat with -p <profile>)" ;;
  "" )      echo "verify with:  hermes skills list | grep bilibili-video" ;;
  * )       echo "verify with:  hermes -p $1 skills list | grep bilibili-video" ;;
esac
echo "check env:    python \"$SRC/scripts/check_env.py\""
