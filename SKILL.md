---
name: bilibili-video-report
description: "Use when downloading or analyzing a Bilibili/B站 video."
---

# B站视频 下载 → 分析 → 图文报告（端到端）

Canonical end-to-end pipeline: prove the URL is reachable → pull the video past Bilibili's
bot wall → verify the file → transcribe the audio → vision-read key frames → author an
illustrated markdown report.

Supersedes the two narrow recipes (`video-download`, `video-content-report`) by chaining them;
use this skill as the entry point. Source: https://github.com/mofahqc/bilibili-video-report
Verified end-to-end on a real BV video (BV1ezYx6EEqA: 164s, 1440x1080 AV1 + AAC, 80 ASR
segments, 4/4 frames vision-read OK).

## Toolchain (paths verified on the author's Windows box; env-overridable)

| piece | location / version | override |
|---|---|---|
| yt-dlp | `yt-dlp` on PATH, 2026.08.19 | — |
| ffmpeg / ffprobe | on PATH — `D:/ffmpeg-8.0-essentials_build/ffmpeg-8.0-essentials_build/bin` (8.0) | — |
| whisper (openai-whisper) | standalone Python 3.13, NOT the Hermes venv: `C:/Users/lenovo/AppData/Local/Programs/Python/Python313/Scripts/whisper.exe` | `$WHISPER_EXE`, else PATH |
| whisper models | `C:/Users/lenovo/.cache/whisper/` — `base.pt`, `large-v3-turbo.pt` (torch 2.7 + CUDA) | `~/.cache/whisper` |
| vision (识图) | DashScope compatible endpoint, `model=qwen3.7-plus`, key `ALIBABA_CODING_PLAN_API_KEY` (`sk-ws-…`) from the hermes `.env` | `--api-base --model --api-key-env` |
| standalone python | `C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe` | — |

**Two hard environment rules on this box**

1. `unset PYTHONPATH` before running anything with the standalone Python 3.13 (whisper, the
   helper scripts). The shell exports the Hermes venv's `site-packages`, which otherwise makes
   whisper import the wrong `torch`/`typing_extensions` and fail. `bili_transcribe.py` strips
   it from the child env itself; yt-dlp is unaffected. In a normal venv this is a no-op.
2. The main chat model (DeepSeek) returns **empty text** for `image_url` — it has no vision.
   Never "look at" a frame with the agent's own vision; always call `bili_vision.py`.

## Steps

Work in a scratch dir OUTSIDE the vault/workspace (`$LOCALAPPDATA/Temp/bili_<name>`), then copy
only the finished `.md` + `frames/` into the vault. Never download media into the vault.

### 0. Sanity-check the toolchain (cheap, catches a broken box before download)

```bash
unset PYTHONPATH
"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe" <skill>/scripts/check_env.py
# every REQUIRED line must read OK; MISSING exits 1
```

### 1. Cookie file (do this first — it also fixes the probe)

```bash
mkdir -p "$LOCALAPPDATA/Temp/bili_job" && cd "$LOCALAPPDATA/Temp/bili_job"
unset PYTHONPATH
"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe" \
  <skill>/scripts/fetch_bili_cookies.py .    # → ./cookies.txt (buvid3/buvid4/b_nut/b_lsid)
```

Cookie file is good for ~1 year — keep it and reuse; don't re-fetch every run.

### 2. Probe (cheap metadata check that surfaces a 412 before you commit)

```bash
yt-dlp --cookies cookies.txt --add-header "Referer:https://www.bilibili.com" \
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  --no-warnings --skip-download --print "%(title)s|%(duration)s|%(uploader)s|%(format_id)s" "URL"
```
A good result looks like `世界上一半的人…|164.568|毕的二阶导|100026+30280` (two ids = video+audio).

### 3. Download best ≤1080p, merged to mp4

```bash
yt-dlp --cookies cookies.txt --add-header "Referer:https://www.bilibili.com" \
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  --no-warnings -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 \
  --sleep-requests 1 -o "video.%(ext)s" "URL"
```

Long video → run as a tracked background job (`background=true, notify=true`), not a long
foreground call that times out mid-merge.

### 4. Verify the file (never skip — catches silent audio-only / truncated pulls)

```bash
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_name,width,height,channels -of default=noprint_wrappers=1 video.mp4
```
Expect one video stream (codec may be `av1`/`hevc` — fine), one `aac` audio stream, and a
`duration` matching the probe.

### 5. Transcribe (ASR)

```bash
unset PYTHONPATH
"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe" \
  <skill>/scripts/bili_transcribe.py video.mp4
# → writes video.wav (16k mono) + video.json, prints start<TAB>end<TAB>text per segment
```
Under the hood: `ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 out.wav` then
`whisper out.wav --model large-v3-turbo --language zh --output_format json`.
`--output_format` takes exactly ONE value (`json` or `all`) — a comma list errors out.
Reference timing: 164s audio → 27s on the GPU.

### 6. Pick key timestamps and extract frames

From the transcript, choose one timestamp per topic / per 板书 change (and at each formula
reveal). Extract a frame per timestamp:

```bash
mkdir -p frames
ffmpeg -y -loglevel error -ss <sec> -i video.mp4 -frames:v 1 -q:v 2 frames/f<sec>.jpg
```

### 7. Vision-read the frames (DashScope)

```bash
unset PYTHONPATH
"C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe" \
  <skill>/scripts/bili_vision.py frames --out vision_results.json
```
The script batches, caches per frame filename into `vision_results.json` (re-runs skip done
frames), and asks for: 标题 → 所有公式(LaTeX) → 要点文字 → 图形描述. If a run risks exceeding
~50s, chunk it over several calls — the cache makes that safe. Per-call `max_tokens=700` is
enough. Point `--api-base/--model/--api-key-env` at any OpenAI-compatible VLM if the default
endpoint is not available.

### 8. Author the report

```
# <视频标题> — 图文解析
> 来源: <URL> · UP主: <uploader> · 时长: <dur> · 生成日期: <date>

## 一句话总结
<one sentence>

## 内容结构
| 主题 | 时间 |
|---|---|
| 1. … | 00:00–01:20 |

## 1. <主题>  `00:12`
![frame](frames/f12.jpg)
- **讲解**: <what the speech says, condensed>
- **板书/公式**: $…$  (from the vision read)
- **怎么用 / 注意**: <takeaway>

## 重点 & 易错提醒
- …
```

Keep frame images as relative links (`frames/xx.jpg`) and copy `frames/` next to the `.md`,
else the links break. Deliver with `MEDIA:<abs path to .md>`.

## Pitfalls

- **Bilibili HTTP 412 is a cookie problem, not a header problem.** `Referer` + a Chrome
  `User-Agent` alone does NOT clear the WAF; it checks the anonymous `buvid3`/`buvid4` cookies.
  Get them from `https://api.bilibili.com/x/frontend/finger/spi` — **GET** (POST returns 405) —
  via `scripts/fetch_bili_cookies.py`, and pass `--cookies cookies.txt`.
- **`--cookies-from-browser chrome/edge` does NOT work here.** Edge's store fails DPAPI
  decryption; Chrome's cookie DB is locked while Chrome runs. Use the SPI anonymous cookies —
  no login, no credentials needed.
- **Audio finishes last.** yt-dlp pulls the video stream, then the audio `.m4a`; a timed-out run
  leaves `video.f<id>.mp4` + `video.f<id>.m4a.part`. Re-run with `--continue
  --merge-output-format mp4` to just finish+merge — do not delete and re-download.
- **1080p+ (1080P 高码率/4K) needs a logged-in account**; anonymously stay at ≤1080p.
- **Long videos**: split the ASR/vision work into several calls and cache (frames →
  `vision_results.json`) so a timeout doesn't lose progress; extract media to Temp, not the vault.
- **Frames**: a ~140KB JPG base64s fine, no resize needed. Name files by timestamp (`f123.jpg`)
  so the report's time labels and image links stay in sync.
- The cookie script builds its own opener with `ProxyHandler({})` — keep that, or a local system
  proxy can break the SPI call.
- The pipeline is yt-dlp-generic (YouTube, etc.); only the cookie step is Bilibili-specific.
