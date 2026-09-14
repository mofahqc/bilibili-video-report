#!/usr/bin/env python3
"""Vision-read a directory of video frames through an OpenAI-compatible VLM, with a cache.

Usage:
    python bili_vision.py <frames_dir> [--out vision_results.json]
                          [--model qwen3.7-plus] [--api-base URL]
                          [--api-key-env ENV_NAME] [--prompt-file prompt.txt]
                          [--frames 12,45,201] [--max-tokens 700] [--timeout 90]

Defaults target the DashScope OpenAI-compatible endpoint (qwen3.7-plus), whose key
is read from $DASHSCOPE_API_KEY / $ALIBABA_CODING_PLAN_API_KEY, or from a Hermes
.env file ($HERMES_HOME/.env, ~/.hermes/.env, $LOCALAPPDATA/hermes/.env, then
<hermes>/profiles/*/.env). Point --api-base/--model/--api-key-env at any other
OpenAI-compatible vision model (OpenAI, OpenRouter, a local llama.cpp server, ...).

Every answer is cached in the output JSON keyed by frame filename, so re-runs skip
frames already done -- splitting a long video across several invocations is safe.
Prints one block per frame:  === <file> ===  followed by the answer.

Why not the agent's own vision? DeepSeek (and other text-only chat models) return
empty content for image_url parts. A dedicated VLM call is the only reliable path.
"""

import argparse
import base64
import glob
import json
import os
import re
import sys
import time
import urllib.request

DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen3.7-plus"
DEFAULT_PROMPT = (
    "这是一张视频截图。请输出：1) 画面标题/板书主标题（若有文字，原样抄录） "
    "2) 所有公式，用 LaTeX 表示 3) 要点文字（逐条） 4) 图形/图表/示意图描述。"
    "只输出内容，不要寒暄，不要重复我的要求。")


def hermes_roots():
    """Candidate Hermes home dirs, most specific first."""
    roots = []
    if os.environ.get("HERMES_HOME"):
        roots.append(os.environ["HERMES_HOME"])
    roots.append(os.path.expanduser("~/.hermes"))
    if os.environ.get("LOCALAPPDATA"):                       # Windows
        roots.append(os.path.join(os.environ["LOCALAPPDATA"], "hermes"))
    roots.append(r"C:/Users/lenovo/AppData/Local/hermes")    # author's box
    seen, out = set(), []
    for r in roots:
        if r and r not in seen and os.path.isdir(r):
            seen.add(r)
            out.append(r)
    return out


def find_key(explicit_env=None):
    names = [n for n in (explicit_env, "DASHSCOPE_API_KEY",
                         "ALIBABA_CODING_PLAN_API_KEY") if n]
    for name in names:
        val = os.environ.get(name)
        if val:
            return val.strip().strip('"').strip("'")
    pattern = r"^(?:%s)\s*=\s*[\"']?([^\"'\s]+)" % "|".join(re.escape(n) for n in names)
    for root in hermes_roots():
        candidates = [os.path.join(root, ".env")]
        candidates += sorted(glob.glob(os.path.join(root, "profiles", "*", ".env")))
        for path in candidates:
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            for line in text.splitlines():
                m = re.match(pattern, line.strip())
                if m:
                    return m.group(1)
    raise SystemExit(f"no API key: export {names[0]}=... (or put it in a Hermes .env)")


def ask(api_base, key, model, path, prompt, max_tokens, timeout):
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
    ext = "jpeg" if ext in ("jpg", "jpeg") else ext
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64}"}}]}]}
    req = urllib.request.Request(
        api_base, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    resp = json.loads(opener.open(req, timeout=timeout).read().decode())
    return resp["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames_dir")
    ap.add_argument("--out", default=None, help="cache JSON (default: <parent>/vision_results.json)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--api-base", default=DEFAULT_API_BASE,
                    help="OpenAI-compatible /chat/completions URL")
    ap.add_argument("--api-key-env", default=None, help="env var to read the key from first")
    ap.add_argument("--prompt-file", default=None, help="file with the vision prompt")
    ap.add_argument("--frames", default=None, help="comma list of filename substrings")
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()

    frames_dir = args.frames_dir.rstrip("/\\")
    out = args.out or os.path.join(os.path.dirname(frames_dir) or ".", "vision_results.json")
    prompt = open(args.prompt_file, encoding="utf-8").read() if args.prompt_file else DEFAULT_PROMPT
    key = find_key(args.api_key_env)

    files = sorted(sum((glob.glob(os.path.join(frames_dir, f"*.{ext}"))
                        for ext in ("jpg", "jpeg", "png", "webp")), []))
    if args.frames:
        wanted = [w.strip() for w in args.frames.split(",") if w.strip()]
        files = [f for f in files if any(w in os.path.basename(f) for w in wanted)]
    if not files:
        raise SystemExit(f"no frames found in {frames_dir}")

    cache = {}
    if os.path.exists(out):
        try:
            cache = json.load(open(out, encoding="utf-8"))
        except ValueError:
            cache = {}

    for path in files:
        name = os.path.basename(path)
        if name in cache:
            continue
        last_error = None
        for attempt in (1, 2):
            try:
                cache[name] = ask(args.api_base, key, args.model, path, prompt,
                                  args.max_tokens, args.timeout)
                last_error = None
                break
            except Exception as exc:                          # noqa: BLE001
                last_error = exc
                time.sleep(2 * attempt)
        if last_error is not None:
            print(f"!!! {name}: {last_error}", file=sys.stderr)
            continue
        json.dump(cache, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    for path in files:
        name = os.path.basename(path)
        print(f"=== {name} ===")
        print(cache.get(name, "(failed)"))
        print()
    done = sum(1 for p in files if os.path.basename(p) in cache)
    print(f"# {done}/{len(files)} frames -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
