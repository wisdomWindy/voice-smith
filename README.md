# VoiceSmith · GPT-SoVITS 桌面 TTS 工坊

Windows 桌面应用：**Tauri 2 + Vue 3 + TypeScript + Python sidecar**。
GPT-SoVITS 在本地跑推理与训练，零服务器成本，默认零遥测。

当前进度：

- **M0 完成**：Tauri 窗口、Vue 界面、FastAPI sidecar、SQLite、doctor、mock 试听/异步合成。
- **M1 完成**：模型资产中心、真实 doctor（8/8）、快速音色（参考音频）。
- **M2 完成**：V4 真实推理（48k）；持久化 worker 冷启动约 20s、热任务复用；UI 任务成功并可下载 WAV。
- **M3 完成**：数据集 `.list` → QC → BERT/HuBERT/SV/语义 → S1/S2 训练 → 自动发布微调音色 → 真实合成；S1 225 步、S2 192 步已验证，S1 断点恢复已修复。
- **模型资产**：7 个关键权重带 sha256；校验页可显示 `hash` 失败，导入后自动复核。
- **离线资产包 + 运行时**：主安装器 **3.5MB**；首启先下载 `VoiceSmith-Runtime.7z`（2.34GiB），再下载 `VoiceSmith-Offline-Assets.7z`（3.02GiB），sha256 校验、7zr 解压。
- **合规与支持**：首启使用规约；设置页导出诊断包（版本/doctor/日志，不含音频/模型）。
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
GPT-SoVITS（engine/GPT-SoVITS） + SQLite + 本地文件
```

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

# 引擎代码（锁 commit；模型不放仓库）
git clone --depth 1 https://github.com/RVC-Boss/GPT-SoVITS.git engine\GPT-SoVITS

# 引擎 Python 依赖（torch 按显卡 CUDA 版本单独安装）
uv pip install --python sidecar\.venv\Scripts\python.exe -r sidecar\engine-requirements.txt
```

PyTorch 需按显卡选择：RTX 50 系用 CUDA 12.8 wheel（`torch 2.7.x+cu128`）。
`uv pip install --python sidecar\.venv\Scripts\python.exe --find-links https://mirrors.aliyun.com/pytorch-wheels/cu128/ torch==2.7.1 torchaudio==2.7.1`

## 模型资产

放在引擎目录（应用会自动扫描，也可在「模型资产」页离线导入）：

```text
engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/
  chinese-roberta-wwm-ext-large/
  chinese-hubert-base/
  s1v3.ckpt
  gsv-v4-pretrained/s2Gv4.pth
  gsv-v4-pretrained/vocoder.pth
  sv/pretrained_eres2netv2w24s4ep4.ckpt
engine/GPT-SoVITS/GPT_SoVITS/text/G2PWModel/
```

V4（48k）默认；V2Pro 作为显存/速度兼容档，额外权重见 `docs/GPT-SoVITS-integration.md`。

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

# 1) 冻结 sidecar（约 5.3GB；输出到 C 盘）
scripts\build-engine.ps1

# 2) 薄安装器（不含运行时）
pnpm tauri build --no-bundle
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" scripts\voicesmith.iss

# 3) 运行时包（约 2.34GiB）
scripts\build-runtime-pack.ps1

# 4) 离线资产包（约 3.02GiB）
scripts\build-assets-pack.ps1

# 5) 发布到 GitHub Release（需要 gh auth login）
scripts\publish-release.ps1 -Version 0.1.0
```

产物：

- `dist-assets/VoiceSmith-0.1.0-Setup.exe`（约 3.5MB）
- `dist-assets/VoiceSmith-Runtime.7z`（约 2.34GiB）
- `dist-assets/VoiceSmith-Offline-Assets.7z`（约 3.02GiB）

首次启动：安装运行时 → 安装离线资产 → 自动重启 sidecar。

## 目录

```text
src/                     Vue 3 前端
src-tauri/               Tauri 2 Rust 壳
sidecar/                 Python FastAPI sidecar
engine/GPT-SoVITS/       引擎（不提交权重）
docs/GPT-SoVITS-integration.md
docs/requests/...        需求/spec/plan/工件
PRD.md                   PRD v3.0
```

## 下一步

1. 干净机离线验收：安装 → 首启 → 资产导入 → 推理 → 训练冒烟 → 卸载。
2. 训练前处理：UVR5 人声分离、自动切片、ASR 转写校对。
3. 模型库版本/回滚、批量 A/B。
4. 训练健壮性：断点续训、取消后显存释放、OOM 自愈。
