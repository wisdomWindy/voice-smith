# 打包设计（M4 / 运行时拆分）

## 目标形态

安装目录只包含 Tauri UI、安装器资源和 `7zr.exe`。Python 运行时与依赖在首次启动时
按需下载：

```text
VoiceSmith/
  VoiceSmith.exe                     Tauri 2 / WebView2
  resources/7zr.exe                  解压运行时组件

runtime/                             首次启动下载并解压
  python.exe                         embeddable CPython 3.11 + pip
  python311.zip / *.pyd / *.dll
  sidecar/
    app.py                           启动 FastAPI
    bootstrap.py                     安装离线 wheel
    ...
  deps/
    core/*.whl                       FastAPI/uvicorn + 音频 DSP 依赖
    torch/*.whl                      torch/torchaudio cu128 + 依赖

data/                                %APPDATA%/com.voicesmith.desktop
  voice_smith.db
  voices/ outputs/ training/
  logs/sidecar.log
  logs/bootstrap.log
```

`engine/GPT-SoVITS` 与模型权重仍由离线资产包安装，不进入安装器和运行时组件。

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
  "version": "0.2.3",
  "platform": "windows-x64",
  "components": [
    {
      "name": "base",
      "manifest": "https://github.com/wisdomWindy/voice-smith/releases/download/v0.2.3/runtime-base-manifest.json",
      "sha256": "<整个 base 归档的 sha256>",
      "size": 12345678
    }
  ]
}
```

组件 manifest 沿用分卷格式：

```json
{
  "version": "0.2.3",
  "sha256": "<拼接后的归档 sha256>",
  "size": 3267748358,
  "parts": [
    { "url": "https://.../deps-torch.part01", "file": "deps-torch.part01", "size": 1887436800 }
  ]
}
```

安装器会同时校验分卷大小、拼接后归档大小、组件 manifest 的 `sha256` 以及 bundle 中
声明的 `sha256`（两者不一致直接失败）。

## Sidecar 入口模式

`sidecar/entry.py` 同时服务源码与 PyInstaller（macOS 旧路径）：

```text
voicesmith-engine.exe --port ... --token ... --data-dir ...   启动 FastAPI
voicesmith-engine.exe --worker --engine <root>                持久化 GPT-SoVITS worker
voicesmith-engine.exe --run-script <script> --engine <root>   用冻结解释器跑上游脚本
```

Windows 拆分运行时不再冻结 sidecar，而是：

```text
runtime\python.exe sidecar\bootstrap.py                      安装 deps/core + deps/torch 的 wheel
runtime\python.exe sidecar\app.py --port ... --token ...      启动 FastAPI
```

`real_engine.py` 在源码模式下回退到当前解释器；`training.py` 复用同一解释器运行上游
脚本，因此训练/S1/S2 仍复用 GPT-SoVITS 上游代码。

## 构建顺序

```powershell
# 1) 运行时组件
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch

# 2) 分卷 + runtime-bundle.json（同时切分离线资产包）
scripts\split-release-assets.ps1 -Version 0.2.3

# 3) 薄安装器
pnpm tauri build --no-bundle
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" scripts\voicesmith.iss
```

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
8. 之后由 UI 触发离线资产包安装（GPT-SoVITS 引擎与权重）。

进度通过 `runtime-progress` 事件上报；下载进度按组件总大小加权。

## 运行时定位

Rust `start_engine` 优先使用：

1. `VOICE_SMITH_ENGINE_EXE` 显式路径（调试）
2. `runtime/python.exe` + `runtime/sidecar/app.py`（Windows 拆分运行时）
3. `VOICE_SMITH_RUNTIME` 显式 runtime 根（调试）
4. `resource_dir/voicesmith-engine/voicesmith-engine.exe`（macOS 旧冻结路径）
5. 开发态 `sidecar/.venv/Scripts/python.exe sidecar/app.py`

`install_runtime` 同时兼容旧的单包 manifest（macOS `runtime-<platform>-manifest.json`）：
没有 `components` 字段时按原逻辑解压整个归档，不执行 bootstrap。

引擎根目录按 `VOICE_SMITH_ENGINE` → `install_root/engine/GPT-SoVITS` 顺序解析。

## 历史尝试

- NSIS：5.09GB payload 超过 2GB，`Internal compiler error #12345`。
- 7zSD.sfx：2.08GB 安装包退出 1，受 2GB 限制。
- 7z.sfx：可自解压 >2GB，但不会自动执行安装脚本。
- 结论：改用 Inno Setup 6.7.3 薄安装器，运行时拆成 base/core/torch 按需下载。
- 旧版为 PyInstaller onedir 单包运行时（约 2.34GiB），Windows 已改成本拆分方案；
  macOS 暂时保留 `runtime-macos-*-manifest.json` 单包路径。

## 已知风险

- torch cu128 wheel 约 3.2GB，下载耗时长；已按 1.8GiB 分卷并支持 Range 续传/并行。
- pip 首次安装 wheel 需要数分钟，期间无输出到 UI，只能通过进度事件和日志观察。
- 组件 manifest 与 bundle 的 sha256 必须同时更新；发布脚本已串联生成。
- 引擎源码与权重不内置；干净机仍需资产导入流程。
