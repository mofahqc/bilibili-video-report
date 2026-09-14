# 疑难排查详解

本文件是 README [疑难排查](../README.md#疑难排查) 表的展开版：每条都给出**现象 → 根因 → 处理**，
以及验证方法。全部来自真实踩坑记录。

---

## 1. B站 HTTP 412 Precondition Failed

**现象**

```
ERROR: HTTP Error 412: Precondition Failed
```

或下载到 0% 就报错；有时探测（`--skip-download`）也直接失败。

**根因**

B站 WAF 对下载链路做风控，不只看 `Referer` 和 `User-Agent`，还校验匿名指纹 cookie
`buvid3` / `buvid4`。**只补请求头，实测依然 412** —— 这是最常见的错误结论。

**处理**

```bash
python scripts/fetch_bili_cookies.py .          # → ./cookies.txt
yt-dlp --cookies cookies.txt --add-header "Referer:https://www.bilibili.com" ... "URL"
```

`fetch_bili_cookies.py` 做的事：
1. `GET https://api.bilibili.com/x/frontend/finger/spi` → `{"code":0,"data":{"b_3":..,"b_4":..}}`
2. 用 `b_3`/`b_4` 生成 `buvid3`/`buvid4`，再补 `b_nut`（当前时间戳）和随机的 `b_lsid`
3. 写成 Netscape 格式的 `cookies.txt`，有效期 1 年

**注意**

- 端点必须是 **GET**；用 POST 会返回 **405**。
- 脚本内部用 `ProxyHandler({})` 自建 opener，**刻意绕过系统代理**：挂着本地代理时，SPI 请求常被拦截或改写。
- cookie 文件可以长期复用，不必每次重取。

**验证**

```bash
head -2 cookies.txt          # 应看到 buvid3
yt-dlp --cookies cookies.txt --skip-download --print "%(title)s" "URL"   # 应打印标题
```

---

## 2. `--cookies-from-browser` 失败

**现象**

```
ERROR: Could not copy Chrome cookie database ...
Failed to decrypt with DPAPI ...
```

**根因**

- **Edge**：cookie 库用 Windows DPAPI 加密，在非交互/不同用户上下文下解密失败。
- **Chrome**：运行中的 Chrome 会锁定 cookie SQLite 数据库，yt-dlp 读不到。

**处理**

别用这个参数。SPI 匿名 cookie 走的是「访客指纹」路径，**不需要登录、不需要任何凭据**，
也不碰浏览器的 cookie 库。

---

## 3. 下载中断，只剩 `.part` 文件

**现象**

```
Downloading 1 format(s): 100026+30280
[download] Destination: video.f100026.mp4      ← 视频流下完了
[download] Destination: video.f30280.m4a       ← 音频流中途断掉
```
目录里留下 `video.f100026.mp4` 和 `video.f30280.m4a.part`，没有 `video.mp4`。

**根因**

DASH 格式的视频流、音频流是**两个分开的请求**，音频在后。超时/断网卡在音频阶段，
合并（`--merge-output-format mp4`）就不会执行。

**处理**

```bash
yt-dlp --cookies cookies.txt ... --continue --merge-output-format mp4 -o "video.%(ext)s" "URL"
```

`--continue` 会接着下剩余的音频并完成合并。**不要删掉重下** —— 长视频重下是纯浪费。
长任务建议放到后台跑并开启完成通知，别用一个可能超时的前台调用扛完。

**验证**

```bash
ffprobe -v error -show_entries stream=codec_type -of csv=p=0 video.mp4
# video
# audio        ← 两个都要有
```

---

## 4. whisper 报 `ImportError` / `typing_extensions` 冲突

**现象**

```
ImportError: cannot import name 'TypeAliasType' from 'typing_extensions'
```
或 `torch` 版本相关的一堆连锁报错，而单独手敲同样的命令却是好的。

**根因**

agent 宿主的 shell 导出了**另一个虚拟环境**的 `site-packages`（Hermes 就会这样）。whisper 在
独立解释器里跑，却被这个 `PYTHONPATH` 带进了不匹配的依赖。

**处理**

```bash
unset PYTHONPATH && whisper ...
```

`bili_transcribe.py` **默认已经**从子进程环境里剥离 `PYTHONPATH` / `PYTHONHOME`；如果你的部署
确实依赖它们，加 `--keep-pythonpath`。

---

## 5. 识图返回空字符串

**现象**

视觉步骤拿到的 `content` 是 `""`，或干脆是"我无法查看图片"之类的套话。

**根因**

**模型本身不支持图片输入。** 很多主力对话模型（DeepSeek 等）是纯文本的：收到
`{"type":"image_url"}` 不会报错，只返回空 —— 看起来很像是"读过了但没内容"，很容易被当成
提示词问题浪费时间。

**处理**

用真正的 VLM，走 `bili_vision.py`（默认 DashScope `qwen3.7-plus`）。换供应商：

```bash
python scripts/bili_vision.py frames \
  --api-base https://api.openai.com/v1/chat/completions \
  --model gpt-4o-mini \
  --api-key-env OPENAI_API_KEY
```

**验证**：先用单帧试一次，确认有内容输出再批量跑。

---

## 6. 高清（1080P 高码率 / 4K）拿不到

**现象**

`-f` 选到 1080p 就报"requested format not available"，或只给到 360p/480p。

**根因**

B站的高码率与 4K 流需要登录态。匿名访客只能拿到 ≤1080p 的常规码率。

**处理**

这是预期行为，保持 `-f "bv*[height<=1080]+ba/b[height<=1080]"` 即可。真要高清就得登录
（本仓库不处理登录态，也不建议把账号 cookie 交给自动化脚本）。

---

## 7. 帧图片是黑的 / 识图内容跑偏

**现象**

抽出来的帧是转场黑帧、纯字幕帧，或者视觉模型认错了内容。

**根因**

`-ss` 的时间点正好落在转场、片头或没有板书的画面。

**处理**

时间点不要凭感觉选：从 `bili_transcribe.py` 的输出里找**讲到关键概念的句子**，落在该句
`start` 附近取帧。要更稳的话，在目标时间点前后各抽一帧（±2s）再挑。

```bash
for t in 148 150 152; do
  ffmpeg -y -loglevel error -ss $t -i video.mp4 -frames:v 1 -q:v 2 "frames/f$t.jpg"
done
```

---

## 8. 报告里图片全部裂开

**现象**

Markdown 打开后所有 `frames/*.jpg` 都是破图。

**根因**

用了绝对路径、或者只交付了 `.md` 没带 `frames/` 目录。

**处理**

图片一律用**相对路径** `frames/f12.jpg`，并把 `frames/` 与 `.md` 放在同一层目录下一起交付。
帧文件名带时间戳（`f150.jpg`），报告里的时间标签和图片链接就永远对得上。

---

## 9. 中文转写乱码 / 中英混杂

**现象**

转写结果变成拼音、英文，或中英混杂。

**根因**

未指定语言，whisper 自己猜错了。

**处理**

```bash
whisper out.wav --model large-v3-turbo --language zh --output_format json
```

`bili_transcribe.py` 默认已带 `--language zh`。

顺带一提：`--output_format` **只接受单个取值**，写 `json,all` 会直接报错。

---

## 10. `check_env.py` 报 MISSING 怎么读

```
OK      yt-dlp          2026.08.19
MISSING ffmpeg          ffmpeg not on PATH; ffprobe not on PATH
WARN    whisper models  none cached yet -- first run downloads the model
```

- `MISSING` = 流水线跑不动，必须先装（脚本退出码为 1）
- `WARN` = 能跑，但要知道后果（例如模型要现下、key 没配则识图步骤会失败）
- 加 `--json` 可接进 CI 或其它脚本
