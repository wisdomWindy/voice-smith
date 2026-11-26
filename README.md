# VoiceSmith · GPT-SoVITS 桌面 TTS 工坊

Windows 桌面应用：**Tauri 2 + Vue 3 + TypeScript + Python sidecar**。
GPT-SoVITS 在本地跑推理与训练，零服务器成本，默认零遥测。

当前进度：

- **M0 完成**：Tauri 窗口、Vue 界面、FastAPI sidecar、SQLite、doctor、mock 试听/异步合成。
- **M1 完成**：模型资产中心、真实 doctor（8/8）、快速音色（参考音频）。
- **M2 完成**：V5 Turbo 真实推理（48k）；持久化 worker 冷启动约 20s、热任务复用；UI 任务成功并可下载 WAV。
- **M3 完成**：数据集 `.list` → QC → BERT/HuBERT/SV/语义 → S1/S2 训练 → 自动发布微调音色 → 真实合成；S1 225 步、S2 192 步已验证，S1 断点恢复已修复。
- **模型资产**：7 个关键权重带 sha256；校验页可显示 `hash` 失败，导入后自动复核。
- **离线资产包 + 运行时**：主安装器自带 **GPT-SoVITS 引擎源码**（`vendor/GPT-SoVITS`，约 49MB）；首启先下载 `runtime-bundle.json` 与 base/core/torch 三个运行时组件（嵌入式 Python + wheel），`pip` 离线安装后启动 sidecar；再下载 `VoiceSmith-Offline-Assets.7z`（权重/工具，约 5.5GB），全程 sha256 校验、7zr 解压到 `<data>/assets`。不再依赖 `v5-engine` 单体发布包。首次启动只弹一个「首次设置」弹窗，确认一次后自动串联安装运行时、离线资产包与模型权重，不再分步确认。
- **合规与支持**：首启使用规约并入「首次设置」弹窗，随安装一次同意；设置页导出诊断包（版本/doctor/日志，不含音频/模型）。
- **ASR**：faster-whisper small 本地转写，支持文件夹批量生成训练 `.list`。
- **长音频切片**：5–15s、48k 单声道；3 分钟测试音频生成 18 段。
- **UVR5**：HP2 模型人声/伴奏分离，输出人声可直接进入 ASR/训练。
- **M5 情绪参考**：音色可绑定多套情绪参考音频；工作台切换后真实推理已验证。
- **模型库**：列出训练产出的 S1/S2/优化器权重，可删除（路径限制在 training/experiments）。
- **M4 安装器完成**：Thin Setup + Runtime Pack + Offline Assets 三段式；Inno Setup 薄安装器 **3.5MB**；v0.1.2 Release 已发布：Windows NSIS、macOS Intel DMG、macOS Apple Silicon DMG。macOS runtime/assets 仍待单独发布。

## 架构

```text
Tauri 2 (Rust) ── WebView2 ── Vue 3 + TS + Vite
      │ invoke/get_engine_info        │ HTTP + SSE
      │ spawn/supervise               │
Python sidecar (FastAPI, 127.0.0.1:random, token)
      │
GPT-SoVITS 引擎源码（vendor/GPT-SoVITS） + 权重（<data>/assets） + SQLite + 本地文件
```

## 引擎与资产分层

| 层 | 位置 | 来源 |
| --- | --- | --- |
| 引擎源码 | `vendor/GPT-SoVITS`（开发）→ `resources/upstream/GPT-SoVITS`（安装后） | 随仓库/安装包，`git` 锁定 |
| 权重与工具 | `<data>/assets/gpt-sovits/...`、`<data>/assets/bin/` | 离线资产包下载或资产页导入 |
| Python 运行时 | `<install>/runtime`、`runtime/deps/{core,torch}` | 运行时 bundle 下载 |

sidecar 启动时把 `<data>/assets` 里的权重目录以 junction/symlink 挂载进引擎树
（`sidecar/engine_paths.py`），因此上游相对路径（`GPT_SoVITS/pretrained_models`、
`GPT_SoVITS/text/G2PWModel`、`tools/uvr5/uvr5_weights`、`runtime/ffmpeg.exe`）
照常工作，而仓库里永远没有权重字节。引擎树只读时（例如 macOS .app），会复制一份
源码到 `<data>/engine/GPT-SoVITS-src` 后再挂载。

## 环境

- Windows 10 22H2 / Windows 11 x64
- Node.js 20+、pnpm 9+
- Rust stable（MSVC toolchain）+ Visual Studio Build Tools（C++ 桌面开发）
- WebView2 Runtime（安装器用 offlineInstaller）
- Python 3.11（GPT-SoVITS 支持 3.10–3.12；不要用 3.13 跑引擎）
- NVIDIA GPU：6GB 起推理，12GB 起训练

## 初始化

```powershell
pnpm install

# Python 3.11 sidecar 环境
uv venv --python 3.11 sidecar\.venv
uv pip install --python sidecar\.venv\Scripts\python.exe -r sidecar\requirements.txt

# 引擎源码已 vendor 在仓库内（vendor/GPT-SoVITS，锁定快照；不要另建 engine/）
pnpm check:engine

# 引擎 Python 依赖（torch 按显卡 CUDA 版本单独安装）
uv pip install --python sidecar\.venv\Scripts\python.exe -r sidecar\engine-requirements.txt
```

模型权重不放仓库：开发态可直接把权重导入 `<repo>/.data/assets/gpt-sovits/`，
或设置 `VOICE_SMITH_ASSETS_DIR` 指向一个带权重的目录树；首次启动时 sidecar 会把
它们挂载进 `vendor/GPT-SoVITS`。

PyTorch 需按显卡选择：RTX 50 系用 CUDA 12.8 wheel（`torch 2.7.x+cu128`）。
`uv pip install --python sidecar\.venv\Scripts\python.exe --find-links https://mirrors.aliyun.com/pytorch-wheels/cu128/ torch==2.7.1 torchaudio==2.7.1`

## 模型资产

权重 / 工具放在数据目录的资产库（应用自动扫描，也可在「模型资产」页离线导入）：

```text
<data>/assets/                        开发态默认 .data/assets
  gpt-sovits/GPT_SoVITS/pretrained_models/
    chinese-roberta-wwm-ext-large/
    chinese-hubert-base/
    s1v3.ckpt
    gsv-v5-pretrained/s2Gv5turbo.pth
    gsv-v5-pretrained/vocoder.pth
    sv/pretrained_eres2netv2w24s4ep4.ckpt
    fast_langdetect/lid.176.bin
  gpt-sovits/GPT_SoVITS/text/G2PWModel/
  gpt-sovits/tools/uvr5/uvr5_weights/
  gpt-sovits/tools/asr/models/
  bin/ffmpeg.exe, ffprobe.exe
```

`VOICE_SMITH_ENGINE` / `VOICE_SMITH_ASSETS_DIR` / `VOICE_SMITH_DATA_DIR` 可覆盖
三层路径（排障用）；正常情况下由 Rust 壳在启动 sidecar 时注入。

V5 Turbo（48k，4 步）默认；V5 Dev 作为质量档；不再支持 V4/V3/V2。

## 开发运行

```powershell
pnpm tauri dev
```

Rust 会选空闲端口、生成 token，并启动 `sidecar/.venv/Scripts/python.exe sidecar/app.py`。
sidecar 日志：

```text
%APPDATA%\com.voicesmith.desktop\logs\sidecar.log
```

只跑前端（浏览器调试）：

```powershell
# 终端 1
sidecar\.venv\Scripts\python.exe sidecar\app.py --port 8765 --token dev-token --data-dir .data

# 终端 2
pnpm dev
# http://localhost:1420
```

浏览器模式默认连接 `127.0.0.1:8765`，token `dev-token`。

## 构建

```powershell
pnpm build

# 1) 冻结 sidecar（仅 macOS 旧路径；约 5.3GB，输出到 C 盘）
scripts\build-engine.ps1

# 2) 薄安装器：staged 引擎源码 + UI + 7zr（不含运行时与权重）
pnpm stage:engine
pnpm tauri build --no-bundle
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" scripts\voicesmith.iss

# 3) 运行时组件（嵌入式 Python + wheel）
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch

# 4) 权重资产包（只打权重/工具；需要一份带权重的 GPT-SoVITS 目录）
scripts\build-assets-pack.ps1 -WeightsRoot D:\program\GPT-SoVITS-v5

# 5) 分卷 + runtime-bundle.json
scripts\split-release-assets.ps1 -Version 0.1.0

# 6) 发布到 GitHub Release（需要 gh auth login）
scripts\publish-release.ps1 -Version 0.1.0
```

产物：

- `dist-assets/VoiceSmith-0.1.0-Setup.exe`（约 55MB，含引擎源码）
- `dist-assets/VoiceSmith-Runtime-base.7z`（约 10MB）
- `dist-assets/VoiceSmith-Deps-core.7z`（约 104MB）
- `dist-assets/VoiceSmith-Deps-torch.7z`（约 3.05GiB）
- `dist-assets/runtime-bundle.json` + 三个组件 manifest/分卷
- `dist-assets/VoiceSmith-Offline-Assets.7z`（约 5.5GB，仅权重/工具）

首次启动只弹一个「首次设置」弹窗：确认一次后自动下载运行时 bundle（base → core → torch）→
`bootstrap.py` 安装 wheel → 启动 sidecar → 同意使用规约 → 安装权重资产包（解压到
`<data>/assets` 并挂载）→ 自动重启 sidecar。

更新安装包时会**先删除旧的 `runtime/` 与 `upstream/` 环境文件再安装**，避免复用旧 sidecar
代码；`data/`、`projects/` 等用户数据保留。更新后首次启动会按新版本重新安装运行时。

## 目录

```text
src/                     Vue 3 前端
src-tauri/               Tauri 2 Rust 壳（resources/upstream 由 pnpm stage:engine 生成）
sidecar/                 Python FastAPI sidecar（engine_paths.py 定义路径契约）
vendor/GPT-SoVITS/       引擎源码（只读；权重不提交）
<data>/assets/           权重/工具资产库（开发态 .data/assets，不入库）
scripts/                 构建、打包、分卷、路径自检
docs/GPT-SoVITS-integration.md
docs/requests/...        需求/spec/plan/工件
PRD.md                   PRD v3.0
```

## 下一步

1. 干净机离线验收：安装 → 首启 → 资产导入 → 推理 → 训练冒烟 → 卸载。
2. 训练前处理：UVR5 人声分离、自动切片、ASR 转写校对。
3. 模型库版本/回滚、批量 A/B。
4. 训练健壮性：断点续训、取消后显存释放、OOM 自愈。

## 构建缓存

本地 Rust/Tauri 与 PyInstaller 构建缓存统一放在项目内：

```text
.cache/tauri-target/
.cache/pyinstaller-build/
.cache/pyinstaller-dist/
```

`.cargo/config.toml` 已固定 `target-dir`，不要再用 C 盘的 `CARGO_TARGET_DIR` 覆盖。
