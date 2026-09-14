#!/usr/bin/env bash
# Install this skill into a Hermes profile, another Agent Skills host, or a project.
#
#   ./install.sh                          Hermes shared tree      (<hermes>/skills/)
#   ./install.sh learning                 one Hermes profile      (<hermes>/profiles/learning/skills/)
#   ./install.sh --all                    Hermes shared tree + every profile
#
#   ./install.sh --agent claude-code      ~/.claude/skills/
#   ./install.sh --agent codex            ~/.agents/skills/
#   ./install.sh --agent opencode         ~/.config/opencode/skills/
#   ./install.sh --agent gemini-cli       ~/.gemini/skills/
#   ./install.sh --agent agents           ~/.agents/skills/   (universal/user scope)
#   ./install.sh --agent claude-code --project /path/to/repo
#                                         <repo>/.claude/skills/ + <repo>/.agents/skills/
#
#   ./install.sh --help
#
# HERMES_HOME is honoured; on Windows %LOCALAPPDATA%\hermes is detected automatically.
#
# Safety: never removes anything outside <dest>/scripts, and refuses to touch a
# destination that resolves to this checkout itself.
set -euo pipefail

SKILL_NAME="bilibili-video-report"
CATEGORY="media"          # Hermes only: which category folder to install under
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ────────────────────────────────────────────────────────────────
# Normalise a path so MSYS-style (/c/Users/x) and native (C:/Users/x) compare equal.
norm() {
  local p="${1//\\//}"
  p="${p%/}"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$p" 2>/dev/null || printf '%s' "$p"
  else
    printf '%s' "$p"
  fi
}

usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; }

# Resolve the Hermes home. HERMES_HOME may point at a PROFILE dir
# (<root>/profiles/<name>) when set by an active Hermes session — step up to the root.
resolve_hermes_root() {
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

install_into() {  # $1 = skills root, e.g. <hermes>/skills
  local skills_root="$1" dest
  dest="$(norm "$skills_root/$SKILL_NAME")"

  if [ "$dest" = "$(norm "$SRC")" ]; then
    echo "skip (this checkout IS the install target): $dest"
    return 0
  fi

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

install_hermes_global() { install_into "$(resolve_hermes_root)/skills/$CATEGORY"; }

# ── parse arguments ────────────────────────────────────────────────────────
MODE="hermes-global"
PROFILE=""
AGENT=""
PROJECT=""

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --all)     MODE="hermes-all"; shift ;;
    --agent)   MODE="agent"; AGENT="${2:-}"; [ -n "$AGENT" ] || { echo "--agent needs a name" >&2; exit 1; }; shift 2 ;;
    --project) MODE="agent"; PROJECT="${2:-}"; [ -n "$PROJECT" ] || { echo "--project needs a path" >&2; exit 1; }; shift 2 ;;
    -*)        echo "unknown option: $1 (try --help)" >&2; exit 1 ;;
    *)         MODE="hermes-profile"; PROFILE="$1"; shift ;;
  esac
done

# ── dispatch ───────────────────────────────────────────────────────────────
case "$MODE" in
  hermes-global )
    HERMES_ROOT="$(resolve_hermes_root)" || { echo "Hermes home not found; set HERMES_HOME" >&2; exit 1; }
    echo "Hermes home: $HERMES_ROOT"
    install_hermes_global
    ;;

  hermes-all )
    HERMES_ROOT="$(resolve_hermes_root)" || { echo "Hermes home not found; set HERMES_HOME" >&2; exit 1; }
    echo "Hermes home: $HERMES_ROOT"
    install_hermes_global
    if [ -d "$HERMES_ROOT/profiles" ]; then
      for p in "$HERMES_ROOT"/profiles/*/; do
        [ -d "$p" ] || continue
        install_into "${p%/}/skills/$CATEGORY"
      done
    fi
    ;;

  hermes-profile )
    HERMES_ROOT="$(resolve_hermes_root)" || { echo "Hermes home not found; set HERMES_HOME" >&2; exit 1; }
    echo "Hermes home: $HERMES_ROOT"
    if [ ! -d "$HERMES_ROOT/profiles/$PROFILE" ]; then
      echo "no such profile: $PROFILE" >&2
      echo "available: $(ls -1 "$HERMES_ROOT/profiles" 2>/dev/null | tr '\n' ' ')" >&2
      exit 1
    fi
    install_into "$HERMES_ROOT/profiles/$PROFILE/skills/$CATEGORY"
    ;;

  agent )
    if [ -n "$PROJECT" ]; then
      # Project scope: both the .agents/ standard and the Claude-compatible path.
      root="$(norm "$PROJECT")"
      [ -d "$root" ] || { echo "no such project dir: $root" >&2; exit 1; }
      echo "project: $root"
      install_into "$root/.agents/skills"
      install_into "$root/.claude/skills"
    else
      case "$AGENT" in
        claude-code)      GLOBAL="$HOME/.claude/skills" ;;
        codex)            GLOBAL="$HOME/.agents/skills" ;;
        opencode)         GLOBAL="$HOME/.config/opencode/skills" ;;
        gemini-cli)       GLOBAL="$HOME/.gemini/skills" ;;
        agents|universal) GLOBAL="$HOME/.agents/skills" ;;
        *)
          echo "unknown agent: $AGENT" >&2
          echo "known: claude-code codex opencode gemini-cli agents" >&2
          exit 1
          ;;
      esac
      echo "agent: $AGENT (global)"
      install_into "$GLOBAL"
    fi
    ;;
esac

echo
case "$MODE" in
  hermes-global )    echo "verify with:  hermes skills list | grep bilibili-video" ;;
  hermes-all )       echo "verify with:  hermes skills list | grep bilibili-video   (add -p <profile> per profile)" ;;
  hermes-profile )   echo "verify with:  hermes -p $PROFILE skills list | grep bilibili-video" ;;
  agent )            echo "verify with:  check the skill appears in your agent's skill list (/skills, \$ mention, etc.)" ;;
esac
echo "check env:    python \"$SRC/scripts/check_env.py\""
