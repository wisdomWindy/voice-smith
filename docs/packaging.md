# 打包设计（运行时 / 引擎源码 / 权重三层拆分）

## 目标形态

VoiceSmith 把「引擎源码」「权重与工具」「Python 运行时」分成三层，互不捆绑：

```text
VoiceSmith/                         安装目录（Inno Setup 薄安装器）
  VoiceSmith.exe                    Tauri 2 / WebView2
  voice-smith.exe
  7zr.exe                           解压运行时/资产组件
  resources/upstream/GPT-SoVITS/    vendored 引擎源码（约 49MB，随安装包分发）
  runtime/                          首启下载并解压
    python.exe                      embeddable CPython 3.11 + pip
    sidecar/                        app.py / engine_paths.py / ...
    deps/core/*.whl                 FastAPI/uvicorn + 音频 DSP
    deps/torch/*.whl                torch/torchaudio cu128
  data/                             数据根（<install>/data；调试态 %APPDATA%）
    voice_smith.db
    voices/ outputs/ training/ logs/
    assets/                         权重与工具（离线资产包安装）
      gpt-sovits/
        GPT_SoVITS/pretrained_models/
        GPT_SoVITS/text/G2PWModel/
        tools/uvr5/uvr5_weights/
        tools/asr/models/
        tools/AP_BWE_main/24kto48k/
      bin/ffmpeg.exe, ffprobe.exe
```

关键点：**引擎源码来自 `vendor/GPT-SoVITS`，权重只存在于 `data/assets`**。
运行时 `sidecar/engine_paths.py` 会把 `data/assets` 的权重目录以 junction（Windows）
或 symlink（POSIX）挂载到引擎树中，上游代码里的相对路径无需改动：

| 上游相对路径 | 挂载来源 |
| --- | --- |
| `GPT_SoVITS/pretrained_models` | `data/assets/gpt-sovits/GPT_SoVITS/pretrained_models` |
| `GPT_SoVITS/text/G2PWModel` | `data/assets/gpt-sovits/GPT_SoVITS/text/G2PWModel` |
| `tools/uvr5/uvr5_weights` | `data/assets/gpt-sovits/tools/uvr5/uvr5_weights` |
| `tools/asr/models` | `data/assets/gpt-sovits/tools/asr/models` |
| `tools/AP_BWE_main/24kto48k` | `data/assets/gpt-sovits/tools/AP_BWE_main/24kto48k` |
| `runtime/ffmpeg.exe` | `data/assets/bin` |

挂载按需创建、幂等；目标已存在为普通目录（旧版就地权重）时保持原样、只标记
`unmanaged`，不删除任何用户文件。若引擎树只读（macOS `.app`），会把源码复制到
`data/engine/GPT-SoVITS-src` 后再挂载。

## 运行时组件

| 组件 | 产物 | 内容 | 安装位置 |
|---|---|---|---|
| base | `VoiceSmith-Runtime-base.7z` | CPython 3.11 embeddable、pip、`sidecar/*.py` | `runtime/` 与 `runtime/sidecar/` |
| core | `VoiceSmith-Deps-core.7z` | `core/*.whl` | `runtime/deps/core/` |
| torch | `VoiceSmith-Deps-torch.7z` | `torch/*.whl`（cu128） | `runtime/deps/torch/` |

三个组件分别有 `<name>-manifest.json`（`runtime-base`、`deps-core`、`deps-torch`），
由 `runtime-bundle.json` 汇总。安装器只下载 bundle 一次，再按组件下载 manifest 与分卷。

`runtime-bundle.json` 结构：

```json
{
  "version": "0.2.4",
  "platform": "windows-x64",
  "components": [
    {
      "name": "base",
      "manifest": "https://github.com/wisdomWindy/voice-smith/releases/download/v0.2.4/runtime-base-manifest.json",
      "sha256": "<整个 base 归档的 sha256>",
      "size": 12345678
    }
  ]
}
```

组件 manifest 沿用分卷格式：

```json
{
  "version": "0.2.4",
  "sha256": "<拼接后的归档 sha256>",
  "size": 3267748358,
  "parts": [
    { "url": "https://.../deps-torch.part01", "file": "deps-torch.part01", "size": 1887436800 }
  ]
}
```

安装器会同时校验分卷大小、拼接后归档大小、组件 manifest 的 `sha256` 以及 bundle 中
声明的 `sha256`（两者不一致直接失败）。

## 权重资产包

`VoiceSmith-Offline-Assets.7z`（分卷后为 `assets.partNN` + `assets-<platform>-manifest.json`）
只包含权重与工具，布局与 `data/assets` 一致：

```text
gpt-sovits/GPT_SoVITS/pretrained_models/...
gpt-sovits/GPT_SoVITS/text/G2PWModel/...
gpt-sovits/tools/uvr5/uvr5_weights/...
gpt-sovits/tools/asr/models/...
gpt-sovits/tools/AP_BWE_main/24kto48k/...
bin/ffmpeg.exe, bin/ffprobe.exe
manifest.json       每个文件的 size + sha256
```

由 `scripts/build-assets-pack.ps1 -WeightsRoot <带权重的 GPT-SoVITS 目录>` 生成；
默认读取 `VOICE_SMITH_WEIGHTS_SRC`，否则 `D:\program\GPT-SoVITS-v5`，再否则旧的
`%APPDATA%\com.voicesmith.desktop\engine\GPT-SoVITS`。构建时只拷贝白名单目录，
不会把引擎源码或 Python 运行时打进资产包。

`sidecar/asset_install.py` 兼容三种包布局：

1. 新布局 `gpt-sovits/` + `bin/`：解压后复制到 `data/assets`；
2. 旧单体包 `engine/GPT-SoVITS/`：只导入其中的权重目录与 `runtime/ffmpeg*.exe`，
   忽略旧包里的源码（源码永远来自安装包内 vendor 副本）；
3. 裸权重树 `GPT_SoVITS/`：直接复制到 `gpt-sovits/`。

安装完成后立即调用 `ensure_mounts()`，并校验 `s1v3.ckpt` / `s2Gv5turbo.pth` /
`vocoder.pth` 是否存在，缺失则报错不重启。

## Sidecar 入口模式

`sidecar/entry.py` 同时服务源码与 PyInstaller（macOS 旧路径）：

```text
voicesmith-engine.exe --port ... --token ... --data-dir ...   启动 FastAPI
voicesmith-engine.exe --worker --engine <root> --data-dir ... 持久化 GPT-SoVITS worker
voicesmith-engine.exe --run-script <script> --engine <root>   用冻结解释器跑上游脚本
```

Windows 拆分运行时不再冻结 sidecar，而是：

```text
runtime\python.exe sidecar\bootstrap.py                      安装 deps/core + deps/torch 的 wheel
runtime\python.exe sidecar\app.py --port ... --token ...      启动 FastAPI
```

`real_engine.py` 在源码模式下回退到当前解释器；`training.py` 复用同一解释器运行上游
脚本，因此训练/S1/S2 仍复用 GPT-SoVITS 上游代码，只是预训练权重路径指向资产库。

## 构建顺序

```powershell
# 1) 引擎源码 staged 到 src-tauri/resources/upstream（安装包内分发）
pnpm stage:engine

# 2) 运行时组件
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch

# 3) 权重资产包（只含权重/工具）
scripts\build-assets-pack.ps1 -WeightsRoot D:\program\GPT-SoVITS-v5

# 4) 分卷 + runtime-bundle.json（同时切分资产包）
scripts\split-release-assets.ps1 -Version 0.2.4

# 5) 薄安装器
pnpm tauri build --no-bundle
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" scripts\voicesmith.iss
```

`pnpm tauri build` 的 `beforeBuildCommand` 会先执行 `pnpm stage:engine`；Inno 脚本
把 `src-tauri/resources/upstream` 装到 `{app}\resources\upstream`。

wheel 目录可以用以下命令准备（示例）：

```powershell
python -m pip download --dest .cache\wheels-core `
  -r sidecar\requirements.txt librosa scikit-learn soundfile scipy numpy numba
python -m pip download --dest .cache\wheels-torch `
  --index-url https://download.pytorch.org/whl/cu128 `
  --extra-index-url https://pypi.org/simple `
  torch torchaudio
```

`build-runtime-base.ps1` 还会把 pip 安装进 embeddable Python，否则
`bootstrap.py` 的 `python -m pip install --no-index` 无法运行。

## 安装流程

1. 首启检测 `runtime\python.exe` + `runtime\sidecar\app.py`，缺失则弹出安装。
2. 下载 `runtime-bundle.json`，读取 base/core/torch 组件 manifest。
3. 逐组件下载分卷、校验大小、拼接、校验 sha256。
4. 解压 base：`python/*` 展平到 `runtime/`，`sidecar/` 保持为 `runtime/sidecar/`。
5. 解压 core/torch 到 `runtime/deps/{core,torch}/`。
6. 运行 `runtime\python.exe sidecar\bootstrap.py`，用 `pip install --no-index` 安装
   两个 wheel 目录；日志写入 `data/logs/bootstrap.log`。
7. 运行 `runtime\python.exe sidecar\app.py`，等待端口就绪后返回。
8. UI 触发离线权重资产安装：下载 → sha256 → 7zr 解压 → 写入 `data/assets` →
   创建引擎挂载 → 重启 sidecar。

进度通过 `runtime-progress` 事件上报；下载进度按组件总大小加权。

## 路径解析

Rust `start_engine` 解析 sidecar 与引擎：

1. `VOICE_SMITH_PYTHON` / `VOICE_SMITH_RUNTIME` / `VOICE_SMITH_ENGINE_EXE` 显式覆盖（调试）
2. `runtime/python.exe` + `runtime/sidecar/app.py`（Windows 拆分运行时）
3. `resource_dir/voicesmith-engine/voicesmith-engine.exe`（macOS 旧冻结路径）
4. 开发态 `sidecar/.venv/Scripts/python.exe sidecar/app.py`

引擎源码按以下顺序解析（`resolve_engine_source`，与 `engine_paths.py` 对齐）：

1. `VOICE_SMITH_ENGINE`
2. 开发态 `vendor/GPT-SoVITS`
3. `resource_dir/upstream/GPT-SoVITS`（Tauri `bundle.resources`）
4. `resources/upstream/GPT-SoVITS`、`<install>/upstream/GPT-SoVITS`
5. 旧布局 `<install>/engine/GPT-SoVITS`、`<data>/engine/GPT-SoVITS`

sidecar 启动参数额外注入 `VOICE_SMITH_ASSETS_DIR=<data>/assets` 与
`VOICE_SMITH_DATA_DIR=<data>`，worker/训练子进程继承。

`install_runtime` 同时兼容旧的单包 manifest（macOS `runtime-<platform>-manifest.json`）：
没有 `components` 字段时按原逻辑解压整个归档，不执行 bootstrap。

## 历史尝试

- NSIS：5.09GB payload 超过 2GB，`Internal compiler error #12345`。
- 7zSD.sfx：2.08GB 安装包退出 1，受 2GB 限制。
- 7z.sfx：可自解压 >2GB，但不会自动执行安装脚本。
- 结论：改用 Inno Setup 6.7.3 薄安装器，运行时拆成 base/core/torch 按需下载。
- 旧版为 PyInstaller onedir 单包运行时（约 2.34GiB），Windows 已改成本拆分方案；
  macOS 暂时保留 `runtime-macos-*-manifest.json` 单包路径。
- 旧版资产包是「引擎源码 + 权重」单体（`v5-engine` Release）。现在源码随安装包，
  资产包只保留权重/工具；旧包仍可被识别，只会导入权重部分。

## 已知风险

- torch cu128 wheel 约 3.2GB，下载耗时长；已按 1.8GiB 分卷并支持 Range 续传/并行。
- pip 首次安装 wheel 需要数分钟，期间无输出到 UI，只能通过进度事件和日志观察。
- 组件 manifest 与 bundle 的 sha256 必须同时更新；发布脚本已串联生成。
- junction 挂载需要写引擎树权限；安装目录在 `%LOCALAPPDATA%\VoiceSmith`（用户可写），
  只读场景会走源码复制兜底。
- 杀软/备份工具可能跟随 junction 扫描权重目录；权重仍在 `data/assets`，不会重复计费。
- 干净机仍需资产下载/导入流程；引擎源码不再依赖外部 Release。
