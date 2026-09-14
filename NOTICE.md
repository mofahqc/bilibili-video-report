# 版权与第三方声明 / Copyright & Third-Party Notices

本文件汇总 `bilibili-video-report` 涉及的版权、商标与第三方许可事项，对仓库内所有文件有效。

---

## 1. 本项目

本项目代码（`SKILL.md`、`scripts/`、`install.sh` 及文档）为原创作品，
**MIT License，Copyright (c) 2026 mofahqc** —— 全文见 [LICENSE](LICENSE)。
欢迎按 MIT 条款使用、修改、再分发，保留版权与许可声明即可。

## 2. 本仓库不包含、也不分发任何第三方作品

| 运行时产物 | 为何不在仓库里 |
|---|---|
| 下载的视频 / 音频（`video.mp4`、`*.m4a`、`*.wav`） | 版权归各 UP 主；由使用者在本地用 `yt-dlp` 自行获取 |
| 视频关键帧截图（`frames/*.jpg`） | 同上；报告里的图片由使用者本地生成 |
| 模型权重（Whisper、Qwen 等） | 由各自的托管方与许可条款分发，运行时自行下载 |
| `ffmpeg` / `ffprobe` / `yt-dlp` 可执行文件 | 由使用者通过系统包管理器安装；本项目只调用其命令行 |
| API 凭据 / cookie | 只存在于使用者本机环境（`.env`、`cookies.txt`） |

`.gitignore` 已把上述运行时产物排除在版本控制之外，仓库内 14 个文件均为源码与文档。

## 3. 示例报告中的第三方内容

`examples/example-report.md` 是真实运行输出，其中包含对第三方作品的**有限摘录**：

| 内容 | 出处 | 许可 / 说明 |
|---|---|---|
| 视频标题、UP主名、少量转写摘录与时间轴 | 《世界上一半的人每天看见这个现象，却不知道为什么》，UP主 **毕的二阶导**，<https://www.bilibili.com/video/BV1ezYx6EEqA> | 版权归原 UP 主所有。仅作说明输出格式的**有限引用**并标注出处；权利人提出异议将立即移除。 |
| 英文引文、Figure 6 图注与公式符号 | Wheeler APS, Morad S, Buchholz N, Knight MM (2012) *The Shape of the Urine Stream — From Biophysics to Diagnostics.* **PLOS ONE** 7(10): e47133. <https://doi.org/10.1371/journal.pone.0047133> | **CC BY**（Creative Commons Attribution License）：允许使用、分发与复制，须注明原作者与出处 —— 本行即为该署名。该引文系视频画面中被高亮的论文原文，经视觉模型抄录。 |

> 示例报告中的健康相关内容仅用于演示技术流程，**不构成任何医疗建议**；原视频画面内亦带有同样的免责声明。

## 4. 商标声明

- **哔哩哔哩 / Bilibili（B站）** 为哔哩哔哩公司所有的商标或注册商标。本项目是**独立第三方工具**，与哔哩哔哩
  **不存在任何隶属、赞助、认可或合作关系**；文中出现 B站/哔哩哔哩仅为说明工具用途（指名性使用，nominative use）。
- **Hermes Agent / Nous Research**、**DashScope / 阿里云 / 通义千问（Qwen）**、**OpenAI / Codex**、
  **Anthropic / Claude**、**Cursor / Cline / GitHub Copilot / Gemini CLI** 等，均为其各自所有者的商标或注册商标。
  本项目与上述任何主体均无隶属或背书关系；提及它们仅为说明兼容性或可替换的组件。
- 本项目名称与文档**不使用**上述主体的 Logo 或视觉标识，亦不暗示任何官方关系。

## 5. 第三方依赖与许可

下列组件**不被本项目捆绑**，仅通过命令行或 HTTP 调用。使用者须自行遵守其许可条款：

| 组件 | 用途 | 许可（以各自仓库/文档为准） |
|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 视频下载 | The Unlicense（公有领域） |
| [FFmpeg](https://ffmpeg.org/legal.html) | 抽音轨 / 抽帧 / 合并（`ffmpeg`、`ffprobe`） | LGPL-2.1-or-later 或 GPL-3.0-or-later（取决于构建选项） |
| [openai-whisper](https://github.com/openai/whisper) | 语音转写 | MIT |
| [PyTorch](https://github.com/pytorch/pytorch) | whisper 推理后端 | BSD-3-Clause |
| Whisper 模型权重（如 `large-v3-turbo`） | ASR 模型 | MIT（同 whisper 仓库） |
| Qwen 视觉模型（默认 `qwen3.7-plus`，经 DashScope） | 画面识图 | 由模型许可与平台条款约定，见阿里云百炼文档 |
| [shields.io](https://shields.io/) | README 徽章 | CC0-1.0 |

> **打包注意**：若你把本技能与 FFmpeg 一起分发（例如塞进容器镜像或安装包），需自行履行 FFmpeg 的
> LGPL/GPL 义务：随附许可文本、保留版权声明；若使用 GPL 构建，还需提供对应源码。

## 6. 使用责任

- 本项目只提供**技术流程**，不提供、不托管、也不鼓励获取任何受版权保护的内容。
- 使用者须自行遵守**哔哩哔哩的服务条款**、目标站点的 robots/ToS 与所在地区版权法规。
- `fetch_bili_cookies.py` 获取的是哔哩哔哩**向匿名访客签发**的指纹 cookie，**不涉及账号凭据**；
  请勿用它进行登录态抓取、规避付费墙或突破访问权限。
- 下载内容请仅用于**个人学习与研究**，**不要二次分发**。
- 识图会把关键帧上传到你自己配置的 API 服务商，请自行评估内容与隐私合规。

## 7. 免责与联系

本项目按 MIT 条款「按原样」提供，不附带任何明示或默示担保；对使用后果（包括但不限于版权争议、
平台条款违反、健康信息误用）不承担责任。

如需就本仓库中的任何第三方内容做删除或修改，请通过 GitHub Issues 提出。
