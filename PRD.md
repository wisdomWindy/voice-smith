# GPT-SoVITS 桌面 TTS 工坊 · PRD

| 项 | 内容 |
|---|---|
| 文档版本 | v3.0 |
| 状态 | 设计定稿，待实现 |
| 日期 | 2026-11-18 |
| 产品形态 | **Windows 桌面应用（Tauri 2 + Vue 3 + Python sidecar）** |
| 产品代号 | voice-smith |
| 工作台场景 | GPT-SoVITS 桌面 TTS（`intent_7c4a9e2b6d1f8053`） |
| 源项目 | [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)（MIT） |
| 一句话 | 把 GPT-SoVITS 的零样本/微调 TTS 收敛成 Windows 桌面工坊：Tauri 壳 + Vue 界面 + 本地 Python 引擎，零服务器成本、数据不出机。 |
| 取代 | v1.0 云端方案、v2.0 PySide6 方案（均已废弃） |

## 0. 决策摘要

1. **形态是桌面端，不是云端服务。** 模型、推理、训练、数据都在用户机器上；没有账号、没有配额、没有服务器账单、没有 abuse 邮箱。
2. **是 TTS，不是 SVC。** GPT-SoVITS 做文本转语音与零样本音色克隆；so-vits-svc 的歌声转换不在范围内。
3. **零服务器成本。** 运营成本只剩开发与分发；用户承担自己的 GPU 与电费。
4. **本地优先，离线可用。** 首次安装后可在断网状态完成推理与训练；联网只用于可选的模型下载/更新检查。
5. **UI 用 Tauri 2 + Vue 3 + TypeScript。** Rust 壳负责窗口/托盘/文件对话框/sidecar 生命周期；Vue 3 + Vite 负责界面；Python sidecar 负责 GPT-SoVITS 推理/训练。
6. **数据用 SQLite + 本地文件。** 任务、音色、模型登记进 SQLite；大文件（音频/模型/日志）进本地目录，临时文件 + 原子改名。
7. **模型资产单独管理。** 安装包不内置第三方权重；首次运行引导下载或离线导入，sha256 校验，损坏可修复。
8. **默认零遥测。** 不收集使用数据；更新检查默认关闭，用户可手动开启。
9. **用户对输出用途负责。** 首次启动展示使用规约；不做内容审核、不做名人声纹库、不做授权审核。本地工具，平台不运营内容。
10. **硬件分层。** 6GB 显存可推理；12GB 起可训练；CPU 可推理但明确标注 RTF 与不可训练。

## 1. 背景与问题

### 1.1 为什么是桌面端

云端 TTS 服务有三座山：GPU 账单、滥用投诉、合规运营。对非商业项目，这三样都不划算：

- 免费公开服务会被刷，GPU 成本不可控；
- 平台要处理 abuse 投诉与下架，运营面积大；
- 用户的声音数据要上传到别人的服务器，隐私差。

桌面端把这三件事一次性消掉：

- 算力是用户自己的，边际成本为 0；
- 没有公开服务，就没有平台侧内容运营；
- 音频、参考音频、模型都在本地，断网可用。

### 1.2 GPT-SoVITS 的工程缺口

GPT-SoVITS 能力强，但仍是研究/脚本形态：

- 装 Python、PyTorch、CUDA、ffmpeg 与一堆权重，版本错配就崩；
- 推理要手写参数，训练要跑 UVR5、切片、ASR、S1/S2 多段脚本；
- 没有任务队列、断点续训、显存自适应、取消与恢复；
- 没有安装器，普通用户拿不到“双击即用”的体验。

### 1.3 要解决的问题

把 GPT-SoVITS 收敛成一个 **Windows 桌面工坊**：

- 安装后自检环境，缺什么给什么修复指引；
- 模型资产可下载、可离线导入、可校验、可修复；
- 文本进去，音频出来；长文可后台跑、可取消、可恢复；
- 5 秒参考音频就能用自己的声音；1–10 分钟数据可微调；
- 训练可断点、可暂停、可取消、OOM 可自愈；
- 打包后不需要用户另装 Python。

## 2. 目标与非目标

### 2.1 目标

| ID | 目标 | 可观测判据 |
|---|---|---|
| G1 | 安装即用 | 干净 Windows 机器安装后 10 分钟内出第一段音频（不含模型下载） |
| G2 | 推理可接受 | GTX 1660 6GB 上 10 秒输入 RTF ≤2.0；RTX 3060 上 ≤1.0 |
| G3 | 训练可控 | 12GB 显存上 100 步冒烟 ≤10 分钟；断点续训步数连续 |
| G4 | 不卡死 | 训练满载时 UI 事件循环 P95 <200ms；24h 无未捕获崩溃 |
| G5 | 零遥测 | 默认不联网、不上传；更新检查默认关闭 |
| G6 | 卸载干净 | 安装目录、注册表、服务、计划任务残留为 0 |

### 2.2 非目标

- 不做云端服务、账号、配额、计费；
- 不做移动端、macOS/Linux 首发；
- 不做 SVC 歌声转换；
- 不做实时对话式 TTS；
- 不做公开音色市场/分享页/社区；
- 不做内容审核、名人声纹库、授权审核；
- 不承诺“所有显卡都能训练”；硬件分层写清楚。

## 3. 用户与场景

### 3.1 用户画像

| 用户 | 特征 | 核心诉求 | 硬件 |
|---|---|---|---|
| 个人创作者 | 短视频配音、口播、有声内容 | 免费、离线、能用自己的声音 | 6–12GB GPU |
| 小型工作室 | 批量配音、参数预设复用 | 稳定、可追溯、可批量 | 12–24GB GPU |
| 声音所有者 | 想把自己的声音做成私有音色 | 数据不出机、可删除、可微调 | 12GB+ |

### 3.2 十条 P0 用户旅程

| ID | 旅程 | 成功判据 |
|---|---|---|
| J1 | 安装与自检：安装 → 首启 → doctor | 8 项检查全绿或给出可复制修复命令 |
| J2 | 离线导入模型：断网 → 导入目录 → 校验 | 资产可用，无需联网 |
| J3 | 快速试听：输入 50 字 → 选音色 → 播放 | 30 秒内听到音频 |
| J4 | 用自己的声音：上传 8 秒参考 → 零样本试听 | 不训练即可合成，可删除 |
| J5 | 微调音色：5 分钟数据 → 质检 → 训练 → 发布 | 训练完成，模型可加载 |
| J6 | 情绪配音：绑定“紧张”参考音频 → 合成 | 已绑定生效；未绑定明确提示 |
| J7 | 长文配音：800 字 → 后台任务 → 导出 | 任务完成，UI 不冻结，可取消 |
| J8 | 批量推理：10 条文本 → 批量 → 汇总 | 失败单条隔离，可只重跑失败项 |
| J9 | 中断恢复：训练到一半取消 → 续训 | 从最近 checkpoint 恢复，步数连续 |
| J10 | 卸载与删除：删除音色/数据 → 卸载 | 本地无残留，卸载干净 |

## 4. 成功指标

| 指标 | 目标 | 说明 |
|---|---|---|
| 安装成功率 | ≥98% | 干净 Win10/11，无 Python |
| 首音频时间 | ≤10 分钟 | 不含模型下载 |
| 10s 推理 RTF | ≤2.0（6GB）/≤1.0（3060） | 中位值 |
| 100 步冒烟 | ≤10 分钟 | 12GB 显存 |
| 训练完成率 | ≥90% | 不含用户取消 |
| UI 事件循环 P95 | <200ms | 训练满载 |
| 24h 崩溃 | 0 | 浸泡测试 |
| 遥测请求 | 0 | 默认配置 |
| 卸载残留 | 0 | 文件/注册表/服务/计划任务 |

## 5. 范围与版本

### 5.1 版本切分

| 版本 | 范围 | 目标 |
|---|---|---|
| **MVP** | Windows 安装器、doctor、模型资产、零样本、单条推理、微调、情绪参考、导出、历史、任务中心 | 可用 |
| **V1** | 批量、参数预设、A/B 对比、模型压缩/ONNX 入口、多语言 | 好用 |
| **V2** | macOS/Linux、插件 API、可选的 BYO 云 TTS | 扩展 |

### 5.2 MVP 范围

**In：**

- Windows 10 22H2 / Windows 11 x64；
- 内置 Python 运行时，无需用户安装 Python；
- doctor 八项：Python、torch/CUDA、GPU/显存、ffmpeg、磁盘、文本前端（BERT/HuBERT/G2PW）、GPT/SoVITS/SV 权重；
- 模型资产中心：sha256、下载、离线导入、修复；
- 文本编辑、试听、单条推理、800 字后台任务；
- 快速音色（零样本）与精细音色（微调）；
- 参考音频绑定情绪；
- 导出 WAV/MP3、历史、删除；
- 任务中心、错误码、日志导出；
- Tauri 2 安装器（NSIS）+ PyInstaller sidecar；用户无需安装 Python/Rust/Node。

**Out：**

- 云端训练/推理；
- 账号、配额、计费；
- 公开分享/社区；
- 内容审核/名人声纹/授权审核；
- 移动端、macOS/Linux；
- 实时对话 TTS、SVC。

## 6. 功能需求

### 6.1 需求总表

| ID | 需求 | 优先级 | 版本 |
|---|---|---|---|
| FR-01 | 环境自检与修复 | P0 | MVP |
| FR-02 | 模型资产中心 | P0 | MVP |
| FR-03 | 文本编辑与试听 | P0 | MVP |
| FR-04 | 快速音色（零样本） | P0 | MVP |
| FR-05 | 精细音色训练（微调） | P0 | MVP |
| FR-06 | 参考音频与情绪绑定 | P0 | MVP |
| FR-07 | 推理参数与预设 | P0 | MVP |
| FR-08 | 单条与批量推理 | P0 | MVP |
| FR-09 | 历史、导出与删除 | P0 | MVP |
| FR-10 | 任务中心与错误码 | P0 | MVP |
| FR-11 | 本地数据与隐私 | P0 | MVP |
| FR-12 | 打包、安装与卸载 | P0 | MVP |
| FR-13 | A/B 对比 | P1 | V1 |
| FR-14 | 模型压缩/ONNX 入口 | P1 | V1 |
| FR-15 | 多语言/方言 | P1 | V1 |
| FR-16 | CPU 推理优化 | P2 | V1 |

### 6.2 P0 需求详述

#### FR-01 环境自检与修复

- **用户故事**：作为用户，我想知道机器能不能跑，缺什么、怎么修。
- **Given** 干净 Windows；**When** 首启；**Then** doctor 检查 Python/torch/CUDA/GPU/ffmpeg/磁盘/文本前端（BERT/HuBERT/G2PW）/GPT-SoVITS-SV 权重，逐项 pass/fail/修复命令。
- **Given** 缺少 ffmpeg；**When** 打开 doctor；**Then** 显示“缺失”，给出可复制的修复步骤，训练/推理入口置灰。
- **验收**：每项失败态可构造；修复后复检通过。

#### FR-02 模型资产中心

- **用户故事**：作为用户，我想下载或离线导入模型，且知道文件没坏。
- **Given** 首次运行；**When** 打开资产中心；**Then** 列出必需资产、大小、来源、sha256、状态。
- **Given** 断网；**When** 选择本地目录导入；**Then** 校验通过后可用，无需联网。
- **Given** 文件被篡改 1 字节；**When** 重扫；**Then** sha256 拒绝，提示重下/替换。
- **验收**：断网导入成功；篡改检测成功；损坏可修复。

#### FR-03 文本编辑与试听

- **用户故事**：作为创作者，我想输入一段文字并立刻听到结果。
- **Given** ≤50 字；**When** 点击试听；**Then** 30 秒内返回音频（6GB 基线）。
- **Given** 800 字；**When** 提交；**Then** 进入后台任务，显示进度与 ETA，UI 不冻结。
- **验收**：试听可用；长文可取消；按模型原生采样率输出，可重采样导出 44.1/48kHz。

#### FR-04 快速音色（零样本）

- **用户故事**：作为声音所有者，我想上传 5–10 秒参考音频就用自己的声音。
- **Given** 8 秒干净人声 + 转写；**When** 创建快速音色；**Then** 30 秒内可试听，无需训练。
- **Given** 参考音频太短/太吵/多说话人；**When** 提交；**Then** 拒绝并给出原因。
- **验收**：快速音色可合成、可删除；默认私有。

#### FR-05 精细音色训练（微调）

- **用户故事**：作为声音所有者，我想用 1–10 分钟数据训练更稳定的音色。
- **Given** 5 分钟干净人声；**When** 提交训练；**Then** 显示阶段、进度、预计耗时；UI 不冻结。
- **Given** 训练到 S1 失败；**When** 重试；**Then** 从 S1 断点继续，不重跑 UVR5/ASR。
- **Given** 显存不足；**When** 启动训练；**Then** 自动降 batch_size 重试一次；仍失败给结构性建议。
- **验收**：100 步冒烟；断点续训；取消 5 秒内释放显存。

#### FR-06 参考音频与情绪绑定

- **用户故事**：作为声音所有者，我想为“开心/悲伤/紧张”绑定参考音频。
- **Given** 已发布音色；**When** 上传 3–10 秒参考 + 转写 + 情绪标签；**Then** 质检通过后绑定，可试听。
- **Given** 未绑定某情绪；**When** 选择该情绪；**Then** 明确不可用，不静默回退中性。
- **验收**：绑定/替换/删除可用；未绑定提示正确。

#### FR-07 推理参数与预设

- **用户故事**：作为用户，我想调语速、音量、情绪，并保存常用组合。
- **Given** 音色不支持情绪强度；**When** 打开参数面板；**Then** 强度置灰并说明原因。
- **Given** 语速 0.5–2.0；**When** 输入越界；**Then** 裁剪并提示。
- **验收**：参数透传日志可查；预设可保存/复用。

#### FR-08 单条与批量推理

- **用户故事**：作为工作室，我想一次跑多条文本，失败不阻塞队列。
- **Given** 10 条文本；**When** 批量提交；**Then** 逐条执行，失败单条隔离，末尾汇总。
- **Given** 单条损坏；**When** 批量结束；**Then** 可只重跑失败项。
- **验收**：批量报告；失败隔离；重跑失败项。

#### FR-09 历史、导出与删除

- **用户故事**：作为用户，我想找回上周的音频，或删除不想保留的记录。
- **Given** 历史列表；**When** 搜索/筛选；**Then** 返回任务、音色、时间、参数快照。
- **Given** 任务成功；**When** 导出；**Then** 下载 WAV/MP3（模型原生采样率，可选重采样 44.1/48kHz），文件名含音色与时间。
- **Given** 删除音色；**When** 确认；**Then** 模型、参考音频、缓存清理。
- **验收**：删除后不可访问；历史可重跑。

#### FR-10 任务中心与错误码

- **用户故事**：作为用户，我想知道任务卡在哪、为什么失败、下一步做什么。
- **Given** 任务失败；**When** 打开详情；**Then** 显示中文现象、原因、下一步、错误码、日志尾部。
- **验收**：12 类错误码均有可复现用例与可读提示。

#### FR-11 本地数据与隐私

- **用户故事**：作为用户，我想确认数据只在我机器上。
- **Given** 默认配置；**When** 运行推理/训练；**Then** 无网络请求、无遥测、日志本地。
- **Given** 删除账户数据/音色；**When** 确认；**Then** SQLite、模型、参考音频、缓存清理。
- **验收**：抓包无遥测；删除无残留；更新检查默认关闭。

#### FR-12 打包、安装与卸载

- **用户故事**：作为用户，我想双击安装，不需要装 Python。
- **Given** 干净 Win10/11；**When** 安装；**Then** 首启成功，doctor 可运行。
- **Given** 卸载；**When** 完成；**Then** 安装目录、注册表、服务、计划任务残留为 0。
- **验收**：干净机安装；离线跑通推理；卸载干净。

## 7. 文本预处理与 SSML

### 7.1 规范化

| 类型 | 规则 |
|---|---|
| 数字/日期/单位 | 按中文读法展开，可配置 |
| 英文/缩写 | 保留字母串，按需逐字母/单词读 |
| 多音字 | 默认词典；V1 支持用户词典 |
| URL/邮箱 | 读作“链接/邮箱”或跳过，可配置 |
| Emoji/颜文字 | 默认移除 |
| Markdown | 去标记，保留文本 |
| 空白 | 合并连续空白；段落停顿 |

### 7.2 分段

- 单段 ≤200 字；单任务 ≤10,000 字；≤50 段。
- 按句号/问号/感叹号/换行切分；避免切断数字、URL、英文单词、引号。
- 段落间 300ms、句间 120ms，可关闭。
- 提交前可预览前 3 段。

### 7.3 SSML

- MVP 仅支持 `<break time="..."/>`，翻译为停顿。
- `<phoneme>` 等标签：本地不支持的返回 `unsupported`，按纯文本处理。
- 所有文本转义，禁止字符串拼接 SSML。
- 非法 SSML 降级为纯文本并回执 `approximated`。

## 8. 音色体系与情绪

### 8.1 音色类型

| 类型 | 来源 | 是否需要联网 | 能力 | 备注 |
|---|---|---|---|---|
| 本地音色 | GPT-SoVITS 零样本/微调 | 否 | 音色、情绪参考音频、语速 | 主力 |
| 平台免费 | Edge TTS（可选） | 是 | 语速/音调/音量 | 非公开接口，默认关闭 |
| 云预置 | Azure/火山/ElevenLabs（V1，BYO Key） | 是 | 情绪/风格 | 可选，不垫付 |

桌面端默认只用本地音色；Edge/云只作为“对比/兜底”，不参与核心链路。

### 8.2 本地 voice 表字段

| 字段 | 类型 | 说明 |
|---|---|---|
| voice_id | string | 本地唯一 |
| name | string | 展示名 |
| type | enum | quick / trained |
| status | enum | draft / training / ready / failed / deleted |
| base_model_version | string | v2 / v2Pro / v2ProPlus / v3 / v4 / v5；与底模、采样率绑定 |
| current_version_id | string | 当前模型版本 |
| emotion_mode | enum | none / reference_audio |
| supported_emotions | json | 已绑定情绪 |
| param_ranges | json | speed 等范围 |
| created_at / updated_at | timestamp | |

### 8.3 情绪 preset

| key | 中文 | 本地支持 | 说明 |
|---|---|---|---|
| neutral | 中性 | ✅ | 默认参考音频 |
| happy | 开心 | ✅ | 绑定参考 |
| sad | 悲伤 | ✅ | 绑定参考 |
| angry | 愤怒 | ✅ | 绑定参考 |
| tense | 紧张 | ✅ | 绑定参考 |
| gentle | 温柔 | ✅ | 绑定参考 |
| serious | 严肃 | ✅ | 绑定参考 |
| excited | 兴奋 | ✅ | 绑定参考 |

- 本地音色的情绪**只通过参考音频切换**；没有绑定就返回 `emotion_effective=false`。
- **强度不支持**：本地 GPT-SoVITS 没有情绪强度参数；UI 置灰，文案“该音色仅支持情绪切换”。
- 云预置（V1）才支持 parametric 强度；映射到 Provider 的 style/degree。

### 8.4 能力回执

```json
{
  "voice": {"requested": "my_voice_001", "actual": "my_voice_001", "substituted": false},
  "emotion": {"requested": "tense", "effective": true, "mode": "reference_audio", "reason": null},
  "speed": {"requested": 0.85, "effective": 0.85, "state": "effective"},
  "volume": {"requested": 110, "effective": 100, "state": "clipped", "reason": "max is 100"},
  "ssml": {"state": "approximated", "reason": "provider does not support <break>"}
}
```

状态：`effective`、`clipped`、`unsupported`、`approximated`。前端逐项展示，不合并成“成功”。

### 8.5 降级与失败

- 本地音色失败：只重试/提示换模型；**不静默换音色**。
- 可选 Edge/云音色失败：可切回本地/提示；如发生替换，回执 `voice_substituted=true`，必须展示。
- 模型损坏：sha256 拒绝；提示重下/回滚版本。
- 模型版本不兼容：拒绝加载，提示换 `base_model_version`。

## 9. 推理

### 9.1 本地推理

**版本与采样率**（以模型 config 为准）：

| 版本 | 原生采样率 | 特点 | 建议 |
|---|---|---|---|
| V2 | 32k（以 config 为准） | 稳定、硬件低 | 6GB 可试 |
| V2Pro / V2ProPlus | 32k（以 config 为准） | 音质/速度平衡，显存略高 | 兼容档 |
| V3 | 24k | 更像、情感丰富 | 需超分缓解闷 |
| V4 | 48k | 修复金属音、原生 48k | **默认推荐** |
| V5 | 以 config 为准（V4 系 48k） | 零样本相似度更高、cuda_graph/flash_attention | 以分支/commit 为准 |

默认 V4；模型版本与底模/配置绑定，不混用；V2Pro 保留为显存/速度兼容档。

- 每进程加载一个音色；V2 系显存 1.6–3.2GB；V3/V4/V5 更高，以实测为准。
- 6GB 显卡：1 个推理进程；12GB：可 2 个；24GB：可 3–4 个。
- 模型从本地磁盘加载；首次加载慢，之后进程内复用。
- 切换音色时卸载旧模型/加载新模型；频繁切换用 LRU 缓存（磁盘级）。
- 推理参数：`text_split_method`、`speed_factor`、`batch_size`、`top_k/top_p/temperature`、`seed`、`sample_steps`、`super_sampling`、`use_cuda_graph`、`use_flash_attention`、`cache_dit`、`streaming_mode`；参考音频/参考文本必填。
- **不把 temperature 包装成“情绪强度”**；它只影响随机性。

### 9.2 单条与长文

- 试听 ≤50 字：同步，30 秒内返回（6GB 基线）。
- 正式合成：全部后台任务；800 字约 60–90 秒 GPU 时间。
- 任务状态：`queued → running → succeeded/failed/cancelled`。
- 进度按段推进；ETA 按历史 RTF 估算。
- 取消：终止 worker 进程树，5 秒内释放显存。
- 失败：保留错误码、段号、日志；半成品不交付。

### 9.3 批量

- 输入：多行文本 / CSV（text, voice, emotion, speed）。
- 逐条执行；单条失败不阻塞；末尾汇总。
- 支持只重跑失败项；批量报告导出 CSV/JSON。
- 批量任务优先级低于交互任务；可暂停。

### 9.4 参数与预设

- 语速 0.5–2.0；音量 0–100（后处理增益）；情绪；seed。
- 预设保存：名称、音色、参数、参考音频；可复用/导出。
- A/B 对比（V1）：同文本、同参数、两个音色/版本，等响度，同步播放。

### 9.5 导出

- WAV 按模型原生采样率（V3 24k / V4 48k / V2 系以 config 为准）单声道；可选重采样 44.1/48kHz；MP3 192kbps。
- LUFS -16，true peak -1 dBTP；可关闭。
- 文件名：`{voice}-{yyyymmdd-hhmm}-{jobid8}.wav`。
- 元数据：音色、模型版本、参数快照、生成时间（本地文件，不上传）。

## 10. 训练

### 10.1 硬件门槛

| 显存 | 推理 | 训练 | 说明 |
|---|---|---|---|
| 6GB | ✅ | ❌ | 可零样本/微调模型推理；训练入口置灰 |
| 8GB | ✅ | ⚠️ | 仅小数据/低 batch，可能 OOM |
| 12GB | ✅ | ✅ | 推荐最低训练档 |
| 16–24GB | ✅ | ✅ | 推荐；可并行更多推理 |

CPU：可推理，RTF 明显升高；不可训练。UI 明确标注。

### 10.2 数据与 QC

- 格式 wav/mp3/flac；1–10 分钟；单说话人；16kHz+。
- 指标：总时长、单条时长、采样率、声道、静音比、削波、SNR、BGM。
- 通过线：静音 ≤20%、削波 <0.1%、SNR ≥20dB、无 BGM。
- 不通过：阻断并给修复建议（重采样/重切/降噪/换素材）。

### 10.3 阶段

| 阶段 | 操作 | 产出 | 断点 |
|---|---|---|---|
| T0 | UVR5 人声分离 | 干净人声 | ✅ |
| T1 | 切片 3–15 秒 | 片段 | ✅ |
| T2 | ASR + 转写校对 | 片段↔文本 | ✅ |
| T3 | 重采样到目标模型采样率（V3 24k/V4 48k；V2 系以 config 为准）/响度/特征 | 训练清单 | ✅ |
| T4 | S1（GPT）微调 | GPT 权重 | ✅ |
| T5 | S2（SoVITS）微调 | SoVITS 权重 | ✅ |
| T6 | 发布/登记/预热 | 可用音色 | ✅ |

- 复用 GPT-SoVITS 的 `prepare_datasets` 与 S1/S2 训练脚本；数据集 `.list` 格式为 `vocal_path|speaker_name|language|text`，语言支持 `zh/ja/en/ko/yue`。
- 每阶段写 `manifest.json` 与 sha256；失败保留已完成阶段。
- 冒烟：100 步；检查 loss 有限、checkpoint 落盘、可 resume。
- 长训：步数、耗时、loss 曲线、峰值显存、参数快照写入报告。
- OOM：batch_size 降 50% 重试一次；再失败建议降 duration/换卡。
- 取消：保留最近完整 checkpoint；5 秒内进程树退出。

### 10.4 参考音频与情绪

- 3–10 秒；单说话人；SNR ≥20dB；无混响；转写准确。
- 绑定：`voice_id, emotion_key, ref_audio_uri, ref_text`。
- 质检失败拒绝绑定，不影响主模型。
- 删除参考音频时同步删除绑定与缓存。

### 10.5 模型发布与版本

- 发布物：GPT/SoVITS 权重、config、参考音频、转写、版本号、sha256、训练报告。
- `voice_versions` 保留每次训练；`current_version_id` 指向当前。
- 发布后可选“立即预热”；失败不影响登记。
- 回滚：切回上一版本；旧版本保留 7 天。
- 模型与 config 绑定 `base_model_version`，不混用。

## 11. 桌面 UX

### 11.1 信息架构

| 页面 | 内容 |
|---|---|
| 首页/工作台 | 最近项目、快速新建、环境状态 |
| 配音编辑器 | 文本、分段预览、音色、参数、试听、提交 |
| 音色库 | 本地音色、快速音色、训练音色、情绪绑定、删除 |
| 训练 | 上传、QC、转写校对、阶段进度、报告 |
| 模型库 | 版本、大小、占用、压缩/导出、删除 |
| 任务中心 | 队列、进度、ETA、取消、重试、日志 |
| 历史 | 搜索、重跑、导出、删除 |
| 设置 | 路径、显存、线程、主题、更新检查、数据目录 |
| Doctor | 八项检查、修复指引、诊断包 |

### 11.2 交互原则

- 主线程只做渲染；所有耗时操作进 sidecar/worker。
- 引擎状态条：启动中/就绪/崩溃重启；端口/token 仅内存；未就绪时禁用合成/训练入口。
- 长任务可最小化到托盘；关闭窗口二次确认，不误杀。
- 训练/推理满载时 UI 仍可操作；列表虚拟化。
- 每个错误给“现象/原因/下一步”，不显示裸异常堆栈。
- 首次启动展示使用规约；不做强制勾选阻断。
- 默认中文；深色/浅色主题。

### 11.3 错误码

| 错误码 | 中文现象 | 下一步 |
|---|---|---|
| ENGINE_START_FAILED | 引擎启动失败 | 查看 sidecar 日志/重启 |
| TORCH_CUDA_MISMATCH | torch 与 CUDA 不匹配 | 按 doctor 修复 |
| GPU_NOT_FOUND | 未检测到 GPU | 检查驱动/换 CPU 模式 |
| VRAM_INSUFFICIENT | 显存不足 | 降 batch/换小模型/关其他程序 |
| FFMPEG_MISSING | ffmpeg 缺失 | 按指引安装/修复 |
| MODEL_MISSING | 模型缺失 | 资产中心下载/导入 |
| MODEL_CORRUPT | 模型损坏 | 重下/替换 |
| AUDIO_INVALID | 音频无法解码 | 转码/换文件 |
| CONFIG_INVALID | 配置非法 | 恢复默认/按提示修改 |
| ENGINE_CRASHED | 引擎/任务进程崩溃 | 自动重启；查看日志/重试 |
| DISK_FULL | 磁盘不足 | 清理/换目录 |
| PATH_UNSUPPORTED | 路径含特殊字符/过长 | 换短路径 |

## 12. 架构

### 12.1 分层

```text
Tauri 2 (Rust)  ──  WebView2  ──  Vue 3 + TypeScript + Vite
     │  Tauri commands / events（文件对话框、reveal、engine info）
     │  spawn + supervise
Python sidecar（FastAPI + Uvicorn，127.0.0.1 随机端口，per-launch token）
     │  HTTP + SSE
Job worker 子进程（GPT-SoVITS 推理/训练/预处理）
     │
SQLite + 本地文件（模型/音频/日志）
```

- **Tauri 壳**：窗口、托盘、单实例、原生文件对话框、更新检查（默认关闭）、sidecar 生命周期、崩溃重启。
- **前端**：Vue 3 + TypeScript + Vite + Pinia + Vue Router；通过本地 HTTP/SSE 访问 sidecar；通过 `invoke` 调原生能力。
- **Sidecar**：FastAPI + Uvicorn，只绑定 `127.0.0.1` 随机端口；每次启动生成 bearer token；只接受本机请求。
- **Worker**：每个推理/训练/预处理任务独立子进程；崩溃只影响该任务；取消终止进程树。
- **存储**：Python 侧 SQLite（WAL）+ 本地文件；Rust 只存窗口/主题等轻量设置。

### 12.2 为什么是 Tauri

- 壳小、内存低，Windows 用系统 WebView2；比 Electron 轻。
- Vue 3 生态适合复杂编辑器、参数面板、任务中心与波形/试听组件。
- Rust 负责进程监管、文件对话框、单实例、更新与崩溃恢复，比纯 Python 壳稳。
- 代价：三套工具链（Rust/Node/Python）、WebView2 依赖、sidecar 打包复杂；用 ADR 与 spike 兜底。

### 12.3 ADR

| ADR | 决策 | 备选与否决理由 |
|---|---|---|
| ADR-001 | Tauri 2 + Vue 3 + TS | PySide6 UI 迭代慢；Electron 体积/内存大；Tauri 壳小、WebView2 系统自带 |
| ADR-002 | Python sidecar + 本地 HTTP/SSE | stdio JSON-RPC 做流式/文件传输麻烦；本地回环 + token 足够安全 |
| ADR-003 | SQLite 归 Python；Rust 只存轻量设置 | 领域数据与任务在 sidecar；避免双写 |
| ADR-004 | Tauri bundler NSIS + PyInstaller onedir sidecar | 单 exe 解压慢；onedir 便于 DLL/模型分离 |
| ADR-005 | 模型资产不内置 | 体积/许可/版本灵活；首次下载或离线导入 |
| ADR-006 | WebView2 offlineInstaller | 离线安装要求；体积换可靠性 |

### 12.4 目录布局

```text
%LOCALAPPDATA%\VoiceSmith\
  app\                 # Tauri 可执行 + 前端资源
  sidecar\             # Python sidecar + 运行时
  models\              # GPT/SoVITS/Hubert/RMVPE/NSF
  voices\              # 用户音色与版本
  datasets\            # 训练数据与中间产物
  outputs\             # 合成音频
  logs\                # Rust/Python/worker 日志
  cache\               # 临时/缓存
  voice_smith.db       # SQLite（Python 侧）
```

用户可在设置中更改数据目录；路径支持中文与空格；避免超长路径。

### 12.5 启动与 sidecar 生命周期

1. Rust 选空闲端口，生成随机 token。
2. 启动 `sidecar/python-sidecar.exe --port <p> --token <t> --data-dir <dir>`。
3. 轮询 `/health`，就绪后通知前端；UI 显示“引擎启动中”。
4. 前端通过 `get_engine_info` 拿到端口/token（仅内存，不落盘）。
5. sidecar 崩溃：Rust 指数退避重启；连续失败弹诊断。
6. 退出：先 `POST /shutdown`，超时杀进程树；确保 worker 一并退出。

### 12.6 GPT-SoVITS 集成契约

- **引擎固定**：源码 vendor 在 `vendor/GPT-SoVITS`，锁定快照（`VENDOR_MANIFEST.json`）；权重放 `<data>/assets`，运行时挂载；升级走 ADR，不在运行时拉 `main`。
- **环境**：Python 3.10–3.12；PyTorch 2.5.1–2.8；CUDA 12.4/12.8；`numpy<2.0`、`pydantic<=2.10.6`、`transformers<5` 等按 `requirements.txt` 锁定。
- **资产路径**：
  - `GPT_SoVITS/pretrained_models/`（V2/V2Pro/V3/V4/V5 底模）
  - `GPT_SoVITS/text/G2PWModel/`
  - `tools/uvr5/uvr5_weights/`
  - `tools/asr/models/`
  - 根目录 `ffmpeg.exe` / `ffprobe.exe`
- **训练**：复用 `prepare_datasets` + S1/S2 训练脚本；数据集 `.list` 格式 `vocal_path|speaker_name|language|text`，语言 `zh/ja/en/ko/yue`。
- **推理**：复用 `GPT_SoVITS.TTS_infer_pack.TTS`（`TTS_Config` + `TTS.run`），与 `api_v2.py` 同源；sidecar 不另写模型加载。
- **参数**：`text/text_lang/ref_audio_path/aux_ref_audio_paths/prompt_text/prompt_lang/top_k/top_p/temperature/text_split_method/batch_size/speed_factor/seed/parallel_infer/sample_steps/super_sampling/streaming_mode/use_cuda_graph/use_flash_attention/cache_dit`。
- **模型切换**：`init_t2s_weights` / `init_vits_weights` / `set_ref_audio`，对应 `api_v2` 的 `/set_gpt_weights`、`/set_sovits_weights`、`/set_refer_audio`。
- **版本**：默认 V4（48k）；V2Pro 作为显存/速度兼容档；V5 以分支/commit 为准。官方 README 仍将“增强的情感控制”列为未完成，情绪只走参考音频。
- **详细清单**：见 `docs/GPT-SoVITS-integration.md`。

## 13. 非功能需求

| 类别 | 要求 |
|---|---|
| 性能 | 试听 ≤30s（6GB，50 字）；10s 输入 RTF ≤2.0；800 字后台 ≤3 分钟 |
| UI 响应 | 训练满载 P95 <200ms；列表虚拟化；不阻塞主线程 |
| 崩溃隔离 | sidecar/worker 崩溃 UI 存活；引擎自动重启；任务标记 failed 可重试 |
| 离线 | 安装后推理/训练可断网；更新检查默认关闭 |
| 安装体积 | 安装包 ≤3.0GB（含 WebView2 offline，不含模型）；模型另计 |
| 启动 | UI 可交互 ≤3s；引擎就绪 ≤10s（SSD） |
| 磁盘 | 安装后预留 20GB；训练数据另计 |
| 安全 | 本地回环 + token；不上传；日志脱敏；依赖扫描 |
| 隐私 | 默认零遥测；数据仅本地；删除可传播 |
| 兼容 | Win10 22H2/Win11 x64；WebView2；NVIDIA 驱动 535+；CPU 兜底 |
| 可访问 | 键盘操作、对比度、表单标签、错误可读 |

## 14. 数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| projects | id, name, path, created_at | 项目 |
| voices | id, name, type, status, base_model_version, current_version_id, emotion_mode | 音色 |
| voice_versions | id, voice_id, version, model_uri, config_uri, sha256, status | 模型版本 |
| emotion_bindings | id, voice_id, emotion_key, ref_audio_uri, ref_text, status | 情绪参考 |
| jobs | id, project_id, voice_id, voice_version_id, text, params_json, status, progress, audio_uri, receipt_json, error_code, created_at, finished_at | 合成任务 |
| job_segments | id, job_id, idx, text, status, audio_uri, duration_ms, error_code | 分段 |
| training_jobs | id, voice_id, status, stage, progress, dataset_uri, config_json, report_json, error_code | 训练 |
| training_stages | id, job_id, stage, status, artifact_uri, log_uri, started_at, finished_at | 阶段 |
| assets | id, kind, uri, sha256, bytes, status | 模型/文件 |
| presets | id, name, voice_id, params_json | 参数预设 |
| settings | key, value | 设置 |
| audit_events | id, actor, action, target, meta_json, created_at | 审计 |

- SQLite WAL；写入事务；大文件不进 DB。
- 临时文件 + 原子改名；崩溃后可恢复。
- 备份：每日复制 DB 到 `backups/`，保留 7 天。
- 删除：DB 记录 + 文件 + 缓存；用户可选择“只删记录/连文件一起删”。

## 15. 本地接口（HTTP + SSE + Tauri commands）

### 15.1 约定

- sidecar 只绑定 `127.0.0.1` 随机端口；每次启动生成 bearer token。
- 前端请求带 `Authorization: Bearer <token>`；token 只存内存，不落盘。
- SSE `/api/v1/events` 推送 `progress`、`log`、`state`。
- Tauri commands：`pick_file`、`pick_folder`、`reveal_path`、`get_engine_info`、`restart_engine`、`open_logs`。
- CORS 只允许 Tauri 前端 origin；拒绝外部网页。
- 错误：`{ "error": { "code": "...", "message": "...", "trace_id": "..." } }`。

### 15.2 端点

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/health` | sidecar 健康 |
| POST | `/api/v1/doctor/run` | 八项检查 |
| GET/POST | `/api/v1/assets` / `/assets/import` / `/assets/verify` | 模型资产 |
| GET/POST/DELETE | `/api/v1/voices` | 音色 |
| POST | `/api/v1/voices/quick` | 快速音色 |
| POST/DELETE | `/api/v1/voices/{id}/references` | 情绪参考 |
| POST | `/api/v1/syntheses` | 创建合成任务（202） |
| GET | `/api/v1/syntheses/{id}` | 状态/回执/音频 |
| GET | `/api/v1/events` | SSE 进度/日志 |
| POST | `/api/v1/syntheses/{id}/cancel` | 取消 |
| POST | `/api/v1/training/jobs` | 创建训练 |
| GET | `/api/v1/training/jobs/{id}` | 训练状态/报告 |
| POST | `/api/v1/training/jobs/{id}/cancel` | 取消训练 |
| GET | `/api/v1/jobs` | 统一任务列表 |
| POST | `/api/v1/export` | 导出音频 |
| GET/PUT | `/api/v1/settings` | 设置 |
| POST | `/api/v1/diagnostics/export` | 诊断包 |
| POST | `/shutdown` | 退出（Rust 调用） |

### 15.3 示例

```ts
const info = await invoke<EngineInfo>('get_engine_info')
const res = await fetch(`http://127.0.0.1:${info.port}/api/v1/syntheses`, {
  method: 'POST',
  headers: {
    'content-type': 'application/json',
    authorization: `Bearer ${info.token}`,
  },
  body: JSON.stringify({
    text: '这是一段测试文本。',
    voice_id: 'my_voice_001',
    params: { emotion: 'tense', speed: 0.85, volume: 110 },
    request_id: 'req_01JABCDEF',
  }),
})
```

```text
event: progress
data: {"job_id":"job_01JABCDEF","percent":33,"stage":"segment 2/6"}

event: state
data: {"job_id":"job_01JABCDEF","status":"succeeded","audio_uri":"outputs/..."}
```

### 15.4 安全边界

- 只监听 loopback；token 每次启动轮换；不接受外部网页 CORS。
- CSP 限制 `connect-src` 到 `http://127.0.0.1:*`；不加载远程脚本。
- 文件选择走 Tauri 原生对话框；路径由 Python 再校验。
- 默认零遥测；sidecar 不主动外联（模型下载由用户触发）。

## 16. 打包与发布

### 16.1 打包

- 构建顺序：Python sidecar（PyInstaller onedir）→ 前端（Vite build）→ Tauri bundle（NSIS）。
- sidecar 作为 Tauri resources 打包；Rust 启动 `sidecar/python-sidecar.exe`。
- WebView2：`offlineInstaller`（离线安装）或 `embedBootstrapper`；安装器检测并引导。
- 校验 torch/CUDA/cuDNN DLL 完整性；缺失则发布门禁阻断。
- 模型资产不内置：首次运行下载或离线导入；安装包 ≤3.0GB（不含模型）。
- 代码签名（可选）：减少 SmartScreen 警告；没有签名要在文档说明。
- 产物：安装包、sha256、SBOM、第三方许可证、release notes、回滚包。

### 16.2 干净机验证

- 干净 Win10/Win11 VM，无 Python/Node/Rust、无 CUDA 工具包；WebView2 由安装器处理。
- 安装 → 首启 → 引擎就绪 → doctor → 离线导入 → 10s 推理 → 100 步训练冒烟 → 卸载。
- 强杀 sidecar/worker，验证引擎自动重启与 UI 存活。
- 安装前后文件系统/注册表快照 diff；卸载后残留为 0。
- 断网跑通推理与训练；更新检查默认关闭。

### 16.3 更新与回滚

- 更新检查默认关闭；用户手动开启后只请求版本号，不上传数据。
- 保留上一版本安装包；降级后数据可读。
- 数据库迁移向前兼容；迁移前自动备份。

## 17. 成本与可持续性

- **服务器成本为 0。** 没有云端 GPU、数据库、对象存储、带宽账单。
- 用户承担自己的硬件与电费；应用不收费、不投广告、不做内购。
- 开发成本：人力 + 代码签名证书（可选）+ 域名/下载站（可选）。
- 可持续方式：捐赠、赞助、社区贡献；不接受与产品绑定的广告。
- 没有配额、没有计费、没有账号；唯一限制是用户自己的硬件。
- 支持：文档 + issue 模板 + 诊断包；不承诺 SLA。

## 18. 里程碑

以 1 名全职工程师估算，单位为周：

| 阶段 | 周期 | 交付 |
|---|---|---|
| M0 spike | 1–2 周 | Tauri 2 窗口 + Vue3 + Python sidecar 调 GPT-SoVITS 推理 1 条 10s 音频；RTF/显存数据 |
| M1 外壳 | 3–5 周 | Tauri shell、sidecar 监管、doctor、模型资产、SQLite、任务框架 |
| M2 推理 | 6–8 周 | 零样本、试听、800 字后台、导出、历史 |
| M3 训练 | 9–12 周 | UVR5/切片/ASR、S1/S2、断点、OOM、模型库 |
| M4 打包 | 13–15 周 | Tauri bundle/NSIS + PyInstaller sidecar + WebView2、干净机、SBOM、卸载 |
| M5 内测到发布 | 16–18 周 | 20 人内测、崩溃/性能修复、正式包 |

## 19. 风险与开放问题

### 19.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 显卡/驱动碎片化 | 部分用户跑不起来 | doctor 精确诊断；CPU 兜底；硬件分层 |
| 模型许可不清 | 不能分发 | 资产单独下载；来源/许可提示；不内置 |
| 安装包过大 | 下载/安装失败 | Tauri 壳小，大头是 Python/torch；模型分离；WebView2 offline 按需 |
| Windows Defender 误报 | 安装受阻 | 代码签名；提交误报；文档说明 |
| 训练时间超预期 | 用户流失 | 预估 ETA；冒烟；断点；硬件门槛 |
| 长路径/中文路径 | 读写失败 | 路径校验；短目录；UTF-8 |
| 无遥测导致问题难定位 | 支持成本高 | 诊断包；日志导出；用户主动提供 |
| Tauri/WebView2/三工具链 | 开发受阻 | spike 验证；锁定版本；CI 矩阵；备选 PySide6 |
| sidecar 生命周期/端口/token | 引擎起不来/连不上 | Rust 监管、健康检查、随机端口、token 轮换、重启退避 |

### 19.2 开放问题

1. WebView2 最低版本与离线安装体积？是否内置 fixed runtime？
2. 模型资产：首次下载、离线导入，还是提供“完整离线包”？
3. 是否做代码签名？预算与证书。
4. 更新通道：手动下载还是内置更新器？
5. 8GB 显卡是否开放训练（低 batch）？
6. 是否内置 Edge TTS 作为可选预览？涉及 ToS 与联网。
7. macOS/Linux 何时做？
8. 模型压缩/ONNX 是否进 V1？

### 19.3 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-11-18 | 形态改为 Windows 桌面端 | 零服务器成本、离线、数据不出机 |
| 2026-11-18 | 本地优先，不做云端服务 | 避免 GPU 账单与 abuse 运营 |
| 2026-11-18 | Tauri 2 + Vue 3 + Python sidecar | 壳小、UI 生态好；Rust 监管进程；Python 跑模型 |
| 2026-11-18 | sidecar 本地 HTTP/SSE + token | 流式/文件传输简单；loopback + token 足够 |
| 2026-11-18 | 模型资产不内置 | 体积/许可/版本灵活 |
| 2026-11-18 | 默认零遥测 | 隐私优先；支持靠诊断包 |
| 2026-11-18 | 6GB 推理、12GB 训练 | 硬件分层写清楚 |

## 20. 验收标准

| 组 | 验收点 | 阻断 |
|---|---|---|
| A 安装/范围/许可 | A1 干净机安装（含 WebView2）；A2 许可证/SBOM（Tauri/Vue/Python）；A3 TTS 不是 SVC；A4 使用规约 | A1、A2、A3 |
| B 环境与资产 | B1 doctor 八项；B2 断网导入；B3 sha256 篡改；B4 资产修复；B5 诊断包 | B1、B2 |
| C 数据集/QC | C1 结构校验；C2 QC 指标；C3 切片；C4 采样率/声道；C5 阈值；C6 低数据量豁免 | C5 |
| D 预处理 | D1 全链；D2 计数；D3 配置；D4 断点幂等 | 否 |
| E 训练 | E1 参数推荐；E2 100 步冒烟；E3 长训；E4 断点续训；E5 取消；E6 OOM；E7 模型登记 | E2、E4 |
| F 推理 | F1 单条；F2 音频质量；F3 RTF；F4 参数；F5 零样本；F6 情绪；F7 批量；F8 可复现 | F1、F3 |
| G 桌面体验 | G1 UI 延迟；G2 12 错误码；G3 sidecar/worker 崩溃隔离；G4 关闭不误杀；G5 24h 浸泡；G6 中文路径 | G1 |
| H 打包 | H1 干净机全流程（含 WebView2）；H2 离线全流程；H3 DLL 扫描；H4 卸载干净；H5 体积/启动（≤3GB、UI≤3s）；H6 回滚 | H1、H2、H4 |
| I 追溯 | I1 矩阵覆盖；I2 verification/review | 否 |

**阻断项**：A1、A2、A3、B1、B2、C5、E2、E4、F1、F3、G1、H1、H2、H4。

证据存 `docs/requests/intent_7c4a9e2b6d1f8053/evidence/<编号>/`；每条附命令、输出、截图或录屏。

**完成定义**：

- 干净 Windows 安装即用，无需 Python；
- 断网可完成导入 → 推理 → 100 步训练冒烟；
- 10s 输入在 6GB 基线 RTF ≤2.0；
- 训练可断点、可取消、OOM 可自愈；
- 默认零遥测；卸载无残留；
- 许可证/SBOM/回滚材料齐全。

## 21. 附录

### 21.1 术语

| 术语 | 含义 |
|---|---|
| TTS | 文本转语音 |
| SVC | 歌声转换；本产品不做 |
| 零样本 | 几秒参考音频直接合成，不训练 |
| 微调 | 1–10 分钟数据训练 GPT/SoVITS |
| 参考音频 | 决定音色/情绪的那段音频 |
| 能力回执 | 哪些参数真正生效 |
| RTF | 合成耗时/音频时长 |
| Worker | 独立任务子进程 |
| Doctor | 环境自检 |

### 21.2 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 壳 | Tauri 2.x + Rust stable + WebView2 | 窗口/托盘/对话框/单实例/sidecar 监管 |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router | 复杂编辑器、参数面板、任务中心 |
| 样式 | Tailwind CSS 或 UnoCSS | 设计令牌统一；暗色/浅色 |
| 通信 | 本地 HTTP + SSE + Tauri commands | 127.0.0.1 随机端口 + token |
| Sidecar | Python 3.10–3.12 + FastAPI + Uvicorn | 业务 API、任务队列、SQLite |
| 数据 | SQLAlchemy 2 + SQLite（WAL） | 领域数据；Rust 只存轻量设置 |
| ML | PyTorch 2.5.1–2.8 + torchaudio + GPT-SoVITS 锁定版本 | CUDA 12.4/12.8 实测矩阵；推理/训练 |
| 打包 | PyInstaller onedir + Tauri bundler NSIS | sidecar 作为 resources；WebView2 offline |
| 测试 | Vitest + Playwright + pytest + cargo test | 前端/端到端/Python/Rust |

版本以锁定矩阵为准；Tauri 2 需要 Rust 工具链，CI 用 Windows runner 构建。

### 21.3 硬件矩阵

| GPU | 显存 | 推理 | 训练 | 备注 |
|---|---|---|---|---|
| GTX 1660 | 6GB | ✅ | ❌ | 最低推理档 |
| RTX 3060 | 12GB | ✅ | ✅ | 推荐最低训练档 |
| RTX 3090 | 24GB | ✅ | ✅ | 推荐 |
| RTX 4090 | 24GB | ✅ | ✅ | 推荐 |
| CPU | — | ⚠️ | ❌ | 仅兜底，RTF 高 |

### 21.4 参考

- GPT-SoVITS：https://github.com/RVC-Boss/GPT-SoVITS
- 集成契约：`docs/GPT-SoVITS-integration.md`
- 工作台场景：`~/.dsh/.dsh_workbench_data/scenes/scene_fe6e1464459d4794/workflow.yaml`
- 场景验收：`~/.dsh/.dsh_workbench_data/scenes/scene_fe6e1464459d4794/acceptance.md`

### 21.5 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v3.0 | 2026-11-18 | 技术栈改为 Tauri 2 + Vue 3 + Rust + Python sidecar；本地 HTTP/SSE；WebView2；安装包 ≤3GB |
| v2.0 | 2026-11-18 | 产品形态改为 Windows 桌面端；本地推理/训练；零服务器成本；PySide6 + worker（已被 v3.0 取代） |
| v1.0 | 2026-11-18 | 云端免费公开服务方案（已废弃） |


