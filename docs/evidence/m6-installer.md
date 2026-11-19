# M6 安装器验证

- 构建：Inno Setup 6.7.3 `ISCC.exe scripts/voicesmith.iss`
- 产物：`C:\Users\yangjianlin\.voicesmith\inno-output\VoiceSmith-0.1.0-Setup.exe`
- 大小：2,287,078,719 bytes（2.13GB）
- 静默安装：
  `VoiceSmith-0.1.0-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=...`
  - 退出码 0
  - `voice-smith.exe`、`voicesmith-engine/voicesmith-engine.exe`、`unins000.exe` 存在
- 安装后启动：
  - 进程：`VoiceSmith-installed\voicesmith-engine\voicesmith-engine.exe`
  - `/health`：`engine=gpt-sovits`，资产 9/9，doctor 8/8
  - 真实推理：`state: succeeded 100`，16.2 秒，WAV 209,964 bytes
- 静默卸载：
  `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`
  - 退出码 0
  - 安装目录已删除
- 截图：`m6-installed-app.png`
- 最终 2.13GB 安装器复验：
  - doctor 8/8；推理 18.4s succeeded
  - 数据集 QC：16 条 / 132.49s，检测到静音 22.4% 并阻断
  - 模型库：19 个模型文件
  - 卸载退出码 0，目录删除
- 截图：`m7-clean-install.png`
