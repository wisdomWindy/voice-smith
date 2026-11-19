# 打包设计（M4）

## 目标形态

```text
VoiceSmith/
  VoiceSmith.exe                     Tauri 2 / WebView2
  resources/
    voicesmith-engine/               PyInstaller onedir sidecar
      voicesmith-engine.exe
      _internal/...                  FastAPI + torch + transformers ...
    engine/GPT-SoVITS/               引擎源码（权重由资产中心导入）
  data（%APPDATA%/com.voicesmith.desktop）
    voice_smith.db
    voices/
    outputs/
    training/
    engine/GPT-SoVITS/               用户导入的权重（可选）
```

## Sidecar 入口模式

`sidecar/entry.py` 同时服务源码与 PyInstaller：

```text
voicesmith-engine.exe --port ... --token ... --data-dir ...   启动 FastAPI
voicesmith-engine.exe --worker --engine <root>                持久化 GPT-SoVITS worker
voicesmith-engine.exe --run-script <script> --engine <root>   用冻结解释器跑上游脚本
```

`real_engine.py` 在 `sys.frozen` 时使用 `--worker`；`training.py` 使用
`--run-script`，因此训练/S1/S2 仍复用 GPT-SoVITS 上游脚本，不重写模型代码。

## 构建顺序

```powershell
# 1) 冻结 sidecar（输出约 4–6GB，建议放 C 盘）
python -m PyInstaller --noconfirm --clean ^
  --workpath C:\voicesmith\pyinstaller-build ^
  --distpath C:\voicesmith\pyinstaller-dist ^
  sidecar\voicesmith-engine.spec

# 2) 放进 Tauri resources
Copy-Item C:\voicesmith\pyinstaller-dist\voicesmith-engine sidecar\ -Recurse

# 3) 安装器
pnpm tauri build
```

Tauri 配置的 `bundle.resources` 需要包含 `voicesmith-engine/**` 与
`engine/GPT-SoVITS/**`（权重单独由资产中心导入，不打进安装包）。

## 运行时定位

Rust `start_engine` 优先使用：

1. `VOICE_SMITH_ENGINE_EXE` 显式路径（调试）
2. `resource_dir/voicesmith-engine/voicesmith-engine.exe`
3. `resource_dir/engine/voicesmith-engine/voicesmith-engine.exe`
4. 开发态 `sidecar/.venv/Scripts/python.exe sidecar/app.py`

引擎根目录按 `VOICE_SMITH_ENGINE` → `resources/engine/GPT-SoVITS` →
`%APPDATA%/.../engine/GPT-SoVITS` 顺序解析。

## 已验证

- Inno Setup 6.7.3 编译成功：`VoiceSmith-0.1.0-Setup.exe` **2.13GB**（单文件，低于 4GB 上限）。
- 静默安装到自定义目录成功，安装后：
  - `voice-smith.exe` + `voicesmith-engine/` 完整
  - 实际拉起安装目录下的冻结 sidecar
  - 真实 V2Pro 推理成功（16.2s）
  - 桌面/开始菜单快捷方式、卸载器存在
- 静默卸载成功，目标目录清理为 0。
- 证据：[m6-installed-app.png](../../evidence/m6-installed-app.png)、[m6-installer.md](../../evidence/m6-installer.md)

## 构建命令

```powershell
# 1) release 应用 + resources（不生成 Tauri 自带 NSIS）
pnpm tauri build --no-bundle

# 2) Inno Setup 编译安装器
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" scripts\voicesmith.iss
```

安装器输出：`C:\Users\yangjianlin\.voicesmith\inno-output\VoiceSmith-0.1.0-Setup.exe`。

## 历史尝试

- NSIS：5.09GB payload 超过 2GB，`Internal compiler error #12345`。
- 7zSD.sfx：2.08GB 安装包退出 1，受 2GB 限制。
- 7z.sfx：可自解压 >2GB，但不会自动执行安装脚本。
- 结论：改用 Inno Setup 6.7.3，单文件安装器 2.13GB，满足 PRD ≤3GB。

## 已知风险

- torch cu128 运行时约 3.2GB，安装包会超过 PRD 的 3GB 目标；可考虑 CPU 版
  安装包 + GPU 运行时按需下载，或分离模型/运行时下载。
- PyInstaller 对 `transformers`/`torch` 的分析较慢，首次构建约 10–20 分钟。
- 引擎源码与权重不内置；干净机需要资产导入流程。
- NSIS 对超大文件/安装时长需要实测。
