# Verification · M0–M2 进度

日期：2026-11-18  
基线：Windows 11 x64 + NVIDIA RTX 5060 Ti 16GB（当时可用显存约 5GB）  
Python：3.11.16（sidecar venv）；PyTorch 2.7.1+cu128；CUDA 12.8

## 1. 构建与启动

| 检查 | 命令 | 结果 |
|---|---|---|
| 前端类型检查/构建 | `pnpm build` | 通过 |
| Rust 检查 | `cargo check`（MSVC BuildTools 18） | 通过 |
| Tauri debug 构建 | `pnpm tauri build --debug --no-bundle` | 通过，生成 `src-tauri/target/debug/voice-smith.exe` |
| 应用启动 | 运行 exe | 窗口加载，引擎 `gpt-sovits`，sidecar 自动启动 |
| 关闭清理 | 关闭窗口 | app + sidecar 退出，无残留（进程检查） |

## 2. 环境自检（M1）

- 资产：9/9 present；`assets.ready=true`。
- doctor：`pass=8, warn=0, fail=0`。
  - Python 3.11.16
  - PyTorch 2.7.1+cu128
  - CUDA 12.8
  - NVIDIA GeForce RTX 5060 Ti, 16311 MiB
  - ffmpeg（系统路径）
  - 磁盘 94.6 GB free
  - 文本前端（BERT/HuBERT/G2PW）已就绪
  - GPT/SoVITS/SV 权重已就绪
- 证据：[m2-doctor.png](../../evidence/m2-doctor.png)、[m2-assets.png](../../evidence/m2-assets.png)

## 3. 真实推理（M2）

### 3.1 直接 worker

- 模型：V2Pro（`s1v3.ckpt` + `s2Gv2Pro.pth` + BERT/HuBERT/SV/G2PW）
- 参考音频：Windows SAPI Huihui 6 秒 WAV
- 命令：`python sidecar/gpt_tts.py --engine ... --text 这是一段测试语音。 --ref ...`
- 结果：`OK ... sr=32000 seconds=1.74`，输出 WAV 111,404 bytes。

### 3.2 持久化 worker（sidecar）

- 首个任务：15.4 秒（含模型加载）
- 第二个任务：2.2 秒（worker 已预热）
- 音频：32kHz 单声道，WAV 约 218–228KB
- 证据：[m2-real-synthesis.png](../../evidence/m2-real-synthesis.png)

### 3.3 端到端 UI

- Workbench 选择 `示例音色（Huihui 参考）` → 提交合成
- 任务 `queued → running(10%) → succeeded(100%)`
- 页面出现音频播放器与“下载 WAV”按钮；文件可播放。
- 截图：[m2-real-synthesis.png](../../evidence/m2-real-synthesis.png)

## 4. 训练与微调发布（M3）

### 4.1 数据集

- 16 条 Huihui SAPI 中文语音，`.list` 格式 `路径|说话人|语言|文本`，总时长约 1 分钟。
- 阈值检查：条目非空、音频存在、总时长 ≥60s。

### 4.2 预处理

- `1-get-text.py`：BERT 特征 + 音素，输出 `2-name2text-0.txt`。
- `2-get-hubert-wav32k.py`：HuBERT + 32k 音频。
- `2-get-sv.py`：ERes2NetV2 说话人向量。
- `3-get-semantic.py`：语义 token。
- 全部使用 GPT-SoVITS 上游脚本（不重写模型代码），输出目录 `training/experiments/<exp>`。

### 4.3 训练

- S1：5 epochs，45 batch/epoch → **225 步**；loss ≈370，top-3 acc ≈0.94；输出 `demo-e1..e5.ckpt`。
- S2：2 epochs，96 batch/epoch → **192 步**；输出 `G_96.pth`、`D_96.pth` 与可加载权重 `*_e1_s96.pth`。
- 训练 API 作业：`queued → validate → text → hubert → sv → semantic → s1 → s2 → done`，总耗时 **134.8 秒**（预热后，16 条数据）。
- 训练日志按 job 写入 `training/logs/<job>.log`，UI 可查看。
- S1 断点恢复：冻结 sidecar 从 `epoch=0-step=11.ckpt` **Restored all states**，达到 max_epochs 后正常结束；修复了 PyTorch 2.7 `weights_only` 的 `WindowsPath` 反序列化问题。
- 训练取消：S1 启动后取消，状态在约 **0.6 秒**内变为 `cancelled`，训练子进程被清理。
- OOM 自愈：S1 失败且日志含 OOM 时 batch 减半重试；S2 降到 `segment_size=10240` 重试。batch=8 测试未触发 OOM（显存仍足够），更大显存压力用例待补。
- 数据集 QC：`POST /api/v1/datasets/qc` 检查时长、采样率、声道、峰值、削波、静音。当前 16 条 SAPI 数据总时长 **132.5s**、单声道，但静音比例约 **22.4%**，超过 20% 阈值 → 默认阻断，可用 `force` 豁免；训练前会跑同一 QC。

### 4.4 微调音色发布与推理

- 训练成功自动登记音色 `trained_bfcd8c`（参考音频 + S1/S2 权重）。
- 用该音色真实合成：**18.2 秒**（含加载与权重切换），输出 32k 单声道 WAV 134,444 bytes。
- 同一 worker 紧接着切回基础音色 `demo_hui`：**3.2 秒**，验证权重双向切换无残留。
- 证据：[m3-training.png](../../evidence/m3-training.png)、[m3-voice.png](../../evidence/m3-voice.png)

## 5. 批量、导出与历史（M4 部分）

- `POST /api/v1/syntheses/batch`：逐条建任务，一个批次线程顺序执行；失败单条隔离。
- 批量状态 `GET /api/v1/syntheses/batch/{id}`：总数、完成数、平均进度、逐条状态。
- ZIP 导出：`GET /api/v1/syntheses/batch/{id}/zip`，只打包成功音频。
- 单条 MP3：`GET /api/v1/syntheses/{id}/export?format=mp3`，ffmpeg 转码。
- 历史页展示任务、状态、WAV/MP3 导出。
- 实测 2 条批量：两条 succeeded，ZIP 6,267 bytes，MP3 16,785 bytes。
- 证据：[m4-batch-ui.png](../../evidence/m4-batch-ui.png)、[m4-batch-history.png](../../evidence/m4-batch-history.png)

## 6. 打包（M4/M6 完成）

- PyInstaller onedir 冻结 sidecar：`voicesmith-engine.exe` + `_internal`，约 **5.09GB / 6.7k 文件**。
- 冻结 sidecar 独立启动：`/health` 返回 `engine=gpt-sovits`，资产 9/9，doctor 8/8。
- 冻结 sidecar 真实推理：V2Pro，32k WAV，约 17–20 秒（冷启动）。
- 冻结 sidecar 训练：`pkg_train9` 经 `--run-script` 跑通 1-get-text → HuBERT → SV → 语义 → S1 → S2，**214.9 秒 succeeded**，产出 S1/S2 权重。
- Tauri 通过 `VOICE_SMITH_ENGINE_EXE` 使用冻结 sidecar；应用内真实合成成功。
- 补齐：`transformers` 等包 metadata、`x_transformers` 源码、`budoux`/`jieba_fast`/`safehttpx` 数据、Lightning 版本兼容、frozen multiprocessing worker、gradio stub、UTF-8 控制台。
- Tauri release + resources 映射成功：`release/voice-smith.exe` 与 `release/voicesmith-engine/` 可直接启动并拉起冻结 sidecar。
- **Inno Setup 6.7.3 成功**：单文件安装器 **2.13GB**，低于 4GB 上限，也低于 PRD 3GB 目标。
- 静默安装到自定义目录：退出码 0；`voice-smith.exe`、`voicesmith-engine/`、`unins000.exe` 就位。
- 安装后实际拉起安装目录的冻结 sidecar；`/health` 为 `gpt-sovits`，资产 9/9，doctor 8/8，真实推理 **16.2–18.4s succeeded**。
- 最终 2.13GB 安装器复验：QC 返回 16 条/132.49s，模型库 19 个文件；卸载退出码 0、目录为 0。
- 静默卸载：退出码 0，安装目录清理为 0。
- **无 Python/PATH 验收**：`PATH` 仅 System32/Windows，未设 `VOICE_SMITH_ENGINE/PYTHON`；引擎放在 `%APPDATA%`；安装版 doctor **8/8 pass**，真实推理 **16.2s succeeded**；卸载后目录为 0。
- 证据：[m6-installed-app.png](../../evidence/m6-installed-app.png)、[m7-clean-install.png](../../evidence/m7-clean-install.png)、[m6-installer.md](../../evidence/m6-installer.md)
- 未完成：把 5GB sidecar 与 engine 源码放入 Tauri resources，生成 NSIS；安装包会超过 PRD 3GB 目标。

## 7. 情绪参考

- 新增 `emotions` 表与 API：列出/创建/删除音色情绪参考。
- 工作台新增「情绪参考」选择；推理时用情绪参考音频替换音色参考，不改模型。
- 实测：为 `demo_hui` 添加「平静 Calm」参考，带 `emotion_id` 合成 **succeeded，26.3 秒**。
- 证据：[m5-emotion.png](../../evidence/m5-emotion.png)

## 8. 结论

M0（Tauri/Vue/sidecar/mock）、M1（资产/doctor/快速音色）、M2（V2Pro 真实推理 + 持久化 worker）、M3（QC + 预处理 + S1/S2 训练 + 自动发布 + 微调推理）、M4（批量/导出/历史 + PyInstaller sidecar + Inno 2.15GB 安装器）、M5（情绪参考）、ASR、UVR5、模型库已打通。  
尚未完成：干净 VM 断网全流程、OOM 真实触发用例、完整 `review.md`。

## 9. 模型库

- `GET /api/v1/models` 扫描 `training/experiments/**/*.ckpt|*.pth`，返回实验、类型、大小、修改时间。
- `DELETE /api/v1/models?path=...` 校验路径在 training/experiments 内，删除模型文件。
- 实测返回 **19 个模型文件**，含 S2 可加载权重、G/D 优化器权重、S1 checkpoint。
- 前端新增「模型」页，可查看/删除。

## 10. ASR 数据集转写

- `faster-whisper small`（CPU int8）本地转写。
- `POST /api/v1/asr` 单文件转写。
- `POST /api/v1/datasets/transcribe` 文件夹批量转写并生成 `.list`。
- 实测 16 个 SAPI WAV：生成 `datasets/asr_raw.list`，**16 条 / 132.49 秒**。
- 冻结 sidecar 单文件 ASR 复验成功（silero VAD 资源已打包）。
- 最终 2.15GB 安装器内 ASR 端点复验成功，`engine=gpt-sovits`。

## 11. UVR5 人声分离

- `POST /api/v1/uvr5` 使用引擎 `HP2_all_vocals.pth`（60.5MB）分离人声/伴奏。
- 源 sidecar 与冻结 sidecar 均验证成功：输出 `vocal_*.wav` / `instrument_*.wav` 各 1,551,404 bytes。
- 前端训练页新增「UVR5 分离」入口。
- 模型不内置，需放入 `tools/uvr5/uvr5_weights/HP2_all_vocals.pth`（资产中心/手动导入）。

## 12. 使用规约与诊断包

- 首启使用规约：`GET /api/v1/terms`、`POST /api/v1/terms/accept`，SQLite 持久化；App 首次 ready 时弹窗。
- 诊断包：`GET /api/v1/diagnostics` 返回 zip，含 `diagnostics.json`（版本/health/doctor/assets）、`sidecar.log`、`engine.log` 尾部；不含音频/模型。
- 实测：terms false→true；zip 含 3 个文件（5,312 / 20,000 / 23,376 bytes）。

## 13. 资产 sha256

- 7 个关键文件带 sha256：BERT、HuBERT、GPT、SoVITS、SV、G2PW、UVR5。
- `POST /api/v1/assets/verify` 返回 `missing`、`bad_hash`、`ready`。
- 实测全部 `hash_ok=true`，`ready=true`；将 UVR5 期望值改为全 0 后 `bad_hash=['uvr5']`，可检测篡改。
- 离线导入复制后自动校验，不匹配直接报错。
- 安装器已重编包含该检查与前端 hash 标记。

## 14. 长音频切片

- `POST /api/v1/datasets/slice`，默认 5–15s，输出 32k 单声道 WAV。
- 3 分钟测试音频 → **18 段**，每段 10.0s / 32000Hz / 单声道。
- 前端训练页新增「长音频切片」。

## 15. V4 默认迁移（2026-11-19）

- PRD 默认从 V2Pro 改为 **V4（48k）**；V2Pro 保留兼容档。
- 资产：`gsv-v4-pretrained/s2Gv4.pth`（733.4MB）+ `vocoder.pth`（55.1MB），sha256 已加入。
- 推理：`/health` 返回 `model=v4`；`demo_hui` 真实合成 **21.4s**，输出 48000Hz/单声道/3.64s。
- 训练：S1 + V4 S2（`s2_train_v3.py` + `s2v4.json`）完成 96 步，总耗时 **165s**，产出 `*_e1_s96.pth`。
- 微调 V4 权重写 `b"04"` header；`trained_fecfe2` 真实合成 **24.4s**，48k。
- 单卡 V4 trainer 通过本地 gloo 进程组启动；引擎 `head2version[b"04"]` 按非 LoRA 识别。
- 安装器重编 **2.15GB**，包含 V4 资产清单/推理/训练路径。

## 16. 离线资产包

- 产物：`VoiceSmith-Offline-Assets.7z`，3,244,469,305 bytes（3.02GiB）。
- sha256：`35bfe73266a5dfb5fbfdce1b5fbaa61580a07bafb9b09df06cb5a2a48ea968b8`。
- 内容：engine 3.03GB + ASR 0.45GB + manifest；含 V4 权重、BERT/HuBERT/G2PW/SV、UVR5 HP2、ffmpeg。
- 主安装器保持 2.15GB；首次启动在资产缺失时弹出「安装离线资产」对话框。
- 下载/校验/7zr 解压/安装已用本地 HTTP 端到端验证：`done`，安装后 3.48GB，`s2Gv4.pth` 与 faster-whisper 缓存存在。
- 详见 `docs/release/offline-assets.md`。

## 17. 三段式分发（Thin Setup + Runtime + Assets）

- 主安装器：**3.5MB**，仅 UI + 7zr + licenses；不再含 PyTorch sidecar。
- 运行时包：`VoiceSmith-Runtime.7z` **2.34GiB**，sha256 `16830e39...74a2c474`。
- 离线资产包：`VoiceSmith-Offline-Assets.7z` **3.02GiB**，sha256 `35bfe732...68b8`。
- 首启 `runtime_missing` 弹窗；下载/校验/7zr 解压到 `%APPDATA%\...\runtime`，重启 sidecar。
- 实测：thin 安装 → 运行时弹窗 → 本地 HTTP 安装 → `gpt-sovits` 就绪 → V4 推理成功；无 console 窗口。
- 代码已推送到 `https://github.com/wisdomWindy/voice-smith`（main）。
- 未完成：GitHub Release 单资产上限 2GB，runtime/assets 需拆分 part + manifest；`gh` 未认证，尚未创建 Release。

## 18. Huihui 噪音修复（2026-11-19）

- 现象：V4 Huihui 输出峰值 1.0、RMS 0.94、88% 采样削波，听感为强噪音。
- 根因：上游 `TTS.audio_postprocess` 返回 **int16**；`gpt_worker`/`gpt_tts` 直接 `astype(float32)`，未除以 32768，全部溢出削波。
- 修复：整数音频 `astype(float32)/32768.0`，浮点保持原值。
- 复测：48k/3.44s，峰值 **0.631**、RMS **0.054**、削波 **0**。
- 已重编 runtime pack 并上传：sha256 `785b9350af04ad5971c1a3a8f87a930b9429c4c52a97562988264785ecf4a83c`。

## 19. 已知问题

- 首次真实推理需加载模型（约 10–15 秒）；训练任务需要独占 GPU，当前未与推理任务做显存互斥。
- 真实推理/训练依赖当前机器的 C 盘资产目录；安装器尚未把这些资产纳入发布流程。
- 试听按钮当前仍走 mock；正式任务走真实引擎。
- 训练数据集目前需要用户提供 `.list`；UVR5/切片/ASR 自动前处理尚未接入。
- S1 断点恢复已修复（`torch.serialization.add_safe_globals`）；已从 `epoch=0-step=11.ckpt` 恢复全部状态。长训断点/取消/OOM 自愈仍需完整用例。
- 批量取消只能标记任务，正在进行的真实推理会跑完当前条；结果不会覆盖 cancelled。
