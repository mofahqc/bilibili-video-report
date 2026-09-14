#!/usr/bin/env python3
"""Video -> 16 kHz mono wav -> whisper JSON timeline.

Usage:
    python bili_transcribe.py <video> [--model large-v3-turbo] [--lang zh]
                              [--outdir DIR] [--keep-pythonpath]

Writes <outdir>/<stem>.wav + <outdir>/<stem>.json and prints one
"start<TAB>end<TAB>text" line per segment (plus a summary on stderr).

The whisper CLI is resolved from $WHISPER_EXE, then PATH, then the standalone
Python install on the author's Windows box -- so this works both inside a normal
virtualenv and on a box where whisper lives outside the agent's own interpreter.

PYTHONPATH / PYTHONHOME are stripped from the child environment by default: when
the calling shell exports another venv's site-packages (Hermes does), whisper
imports the wrong torch/typing_extensions and dies. Pass --keep-pythonpath if
your setup needs them.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

WINDOWS_FALLBACK = (
    r"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/Scripts/whisper.exe")


def find_whisper():
    exe = os.environ.get("WHISPER_EXE")
    if exe and os.path.exists(exe):
        return exe
    found = shutil.which("whisper") or shutil.which("whisper.exe")
    if found:
        return found
    if os.path.exists(WINDOWS_FALLBACK):
        return WINDOWS_FALLBACK
    raise SystemExit(
        "whisper not found. Install it (`pip install openai-whisper`) or point "
        "WHISPER_EXE at the executable.")


def run(cmd, keep_pythonpath):
    env = os.environ.copy()
    if not keep_pythonpath:
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")
    return proc


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="input video/audio file")
    ap.add_argument("--model", default="large-v3-turbo",
                    help="whisper model (default: large-v3-turbo)")
    ap.add_argument("--lang", default="zh", help="spoken language (default: zh)")
    ap.add_argument("--outdir", default=None, help="output dir (default: next to input)")
    ap.add_argument("--keep-pythonpath", action="store_true",
                    help="do not strip PYTHONPATH/PYTHONHOME from the child env")
    args = ap.parse_args()

    video = os.path.abspath(args.video)
    if not os.path.exists(video):
        raise SystemExit(f"no such file: {video}")
    outdir = os.path.abspath(args.outdir or os.path.dirname(video) or ".")
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(video))[0]
    wav = os.path.join(outdir, stem + ".wav")

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not on PATH -- install it first")
    whisper = find_whisper()

    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
         "-vn", "-ac", "1", "-ar", "16000", wav], args.keep_pythonpath)
    print(f"# wav: {wav}", file=sys.stderr)

    run([whisper, wav, "--model", args.model, "--language", args.lang,
         "--output_format", "json", "--output_dir", outdir], args.keep_pythonpath)

    jpath = os.path.join(outdir, stem + ".json")
    data = json.load(open(jpath, encoding="utf-8"))
    segments = data.get("segments", [])
    for seg in segments:
        print(f"{seg['start']:.2f}\t{seg['end']:.2f}\t{seg['text'].strip()}")
    print(f"# {len(segments)} segments -> {jpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
