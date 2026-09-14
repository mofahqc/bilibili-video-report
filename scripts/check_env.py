#!/usr/bin/env python3
"""Check the toolchain the bilibili-video-report pipeline needs.

Usage:
    python scripts/check_env.py [--json]

Prints one line per dependency with OK / MISSING / WARN, plus the resolved
whisper path, the cached whisper models and whether an API key is reachable.
Exit code 0 only when every REQUIRED item is present. Standard library only.
"""

import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_NAMES = ("DASHSCOPE_API_KEY", "ALIBABA_CODING_PLAN_API_KEY")
WHISPER_FALLBACK = (
    r"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/Scripts/whisper.exe")
MODEL_DIRS = [os.path.expanduser("~/.cache/whisper")]


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def run_version(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, first_line(proc.stderr) or f"exit {proc.returncode}"
    return first_line(proc.stdout + proc.stderr), None


def check_ytdlp():
    exe = shutil.which("yt-dlp")
    if not exe:
        return "MISSING", "not on PATH -- pip install yt-dlp", None
    ver, err = run_version([exe, "--version"])
    return ("OK", ver, exe) if ver else ("WARN", err, exe)


def check_ffmpeg():
    problems = []
    paths = {}
    for name in ("ffmpeg", "ffprobe"):
        exe = shutil.which(name)
        if not exe:
            problems.append(f"{name} not on PATH")
        else:
            paths[name] = exe
    if problems:
        return "MISSING", "; ".join(problems), None
    ver, _ = run_version([paths["ffmpeg"], "-version"])
    return "OK", (ver or "present")[:70], paths["ffmpeg"]


def check_whisper():
    exe = os.environ.get("WHISPER_EXE")
    if exe and os.path.exists(exe):
        return "OK", f"$WHISPER_EXE -> {exe}", exe
    found = shutil.which("whisper") or shutil.which("whisper.exe")
    if found:
        return "OK", found, found
    if os.path.exists(WHISPER_FALLBACK):
        return "OK", f"standalone fallback -> {WHISPER_FALLBACK}", WHISPER_FALLBACK
    return "MISSING", "pip install openai-whisper (or set WHISPER_EXE)", None


def check_models():
    found = []
    for d in MODEL_DIRS:
        found += [os.path.basename(p) for p in sorted(glob.glob(os.path.join(d, "*.pt")))]
    if not found:
        return "WARN", "none cached yet -- first run downloads the model", None
    return "OK", ", ".join(found), None


def check_key():
    for name in KEY_NAMES:
        if os.environ.get(name):
            return "OK", f"${name} (env)", None
    roots = [os.environ.get("HERMES_HOME"), os.path.expanduser("~/.hermes")]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(os.path.join(os.environ["LOCALAPPDATA"], "hermes"))
    roots.append(r"C:/Users/lenovo/AppData/Local/hermes")
    pattern = r"^(?:%s)\s*=\s*[\"']?([^\"'\s]+)" % "|".join(re.escape(n) for n in KEY_NAMES)
    for root in [r for r in roots if r and os.path.isdir(r)]:
        for path in [os.path.join(root, ".env")] + sorted(
                glob.glob(os.path.join(root, "profiles", "*", ".env"))):
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            for line in text.splitlines():
                m = re.match(pattern, line.strip())
                if m:
                    value = m.group(1)
                    masked = value[:6] + "..." + value[-3:]
                    return "OK", f"{masked} (from {path})", None
    return "WARN", "no key: export DASHSCOPE_API_KEY=... (vision step will fail)", None


def check_scripts():
    expected = ["fetch_bili_cookies.py", "bili_transcribe.py", "bili_vision.py"]
    missing = [s for s in expected if not os.path.exists(os.path.join(HERE, s))]
    if missing:
        return "WARN", "missing: " + ", ".join(missing), None
    return "OK", "fetch_bili_cookies.py, bili_transcribe.py, bili_vision.py", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    rows = [
        ("python", "OK", f"{platform.python_version()} ({sys.executable})", None),
        ("yt-dlp", *check_ytdlp()),
        ("ffmpeg", *check_ffmpeg()),
        ("whisper", *check_whisper()),
        ("whisper models", *check_models()),
        ("vision API key", *check_key()),
        ("helper scripts", *check_scripts()),
    ]

    if args.json:
        print(json.dumps([{"name": n, "status": s, "detail": d, "path": p}
                          for n, s, d, p in rows], ensure_ascii=False, indent=2))
    else:
        width = max(len(n) for n, *_ in rows)
        for name, status, detail, _ in rows:
            print(f"{status:<8}{name:<{width + 2}}{detail}")
        bad = [n for n, s, _, _ in rows if s == "MISSING"]
        print()
        print("required items missing: " + ", ".join(bad) if bad
              else "all required items present -- ready to run")
    return 1 if any(s == "MISSING" for _, s, _, _ in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
