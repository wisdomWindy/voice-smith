# GPT-SoVITS 集成契约

> 状态：v1.0 · 2026-11-18  
> 用途：约定桌面工坊如何把 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 当作训练与推理引擎使用。  
> 原则：**引擎只引用，不重写**；训练/推理复用官方实现，桌面端只做编排、资产、任务与 UI。

## 1. 版本锁定

- 引擎放在 `engine/GPT-SoVITS`（git submodule 或 vendor），**锁定 commit**。
- 不在运行时 `git pull main`；升级必须走 ADR + 回归（音质、RTF、显存、模型兼容）。
- 记录字段：`engine_commit`、`python_version`、`torch_version`、`cuda_version`、`model_version`。
- 许可证：MIT；再分发保留 `LICENSE` 与版权声明。

## 2. 环境矩阵

官方 README 测试过的组合（节选）：

| Python | PyTorch | CUDA | 备注 |
|---|---|---|---|
| 3.10 | 2.5.1 | 12.4 | 推荐稳定 |
| 3.11 | 2.5.1 | 12.4 | 推荐稳定 |
| 3.11 | 2.7.0 | 12.8 | 新卡 |
| 3.12 | 2.7.1 | 11.8/12.8 | 可用 |
| 3.9 | 2.2.2 | CPU | 仅兜底 |

桌面端建议：**Python 3.10/3.11 + PyTorch 2.5.1 + CUDA 12.4** 作为默认锁定矩阵；其他组合作为可选。

关键依赖约束（以 `requirements.txt` 为准）：

- `numpy<2.0`
- `pydantic<=2.10.6`
- `transformers>=4.51,<5`
- `librosa==0.10.2`
- `fastapi[standard]>=0.115.2`
- `funasr>=1.3.7`、`ctranslate2>=4.0,<5`
- `torchaudio`、`pytorch-lightning>=2.4`

## 3. 模型版本与采样率

| 版本 | 原生采样率 | 特点 | 桌面建议 |
|---|---|---|---|
| V2 | 32k（以 config 为准） | 稳定、硬件低 | 6GB 可试 |
| V2Pro / V2ProPlus | 32k（以 config 为准） | 音质/速度平衡，显存略高 | 兼容档 |
| V3 | 24k | 更像、情感丰富 | 可配超分缓解闷 |
| V4 | 48k | 修复金属音、原生 48k | **默认推荐** |
| V5 | 以 config 为准（V4 系 48k） | 零样本相似度更高、cuda_graph/flash_attention | 以分支/commit 为准 |

- 模型版本必须与底模、config、采样率绑定，不可混用。
- 导出默认模型原生采样率；可选重采样到 44.1/48kHz。
- 官方 README 仍把“增强的 TTS 情感控制”列为未完成；情绪只能靠参考音频切换。

## 4. 资产清单

| 资产 | 目标路径 | 来源 | 备注 |
|---|---|---|---|
| GPT/SoVITS 底模 | `GPT_SoVITS/pretrained_models/` | HuggingFace `lj1995/GPT-SoVITS` | 按版本子目录放置 |
| G2PWModel | `GPT_SoVITS/text/G2PWModel/` | HuggingFace `XXXXRT/GPT-SoVITS-Pretrained` / ModelScope | 中文 TTS 需要 |
| UVR5 权重 | `tools/uvr5/uvr5_weights/` | HuggingFace `lj1995/VoiceConversionWebUI` | 人声分离 |
| ASR 模型 | `tools/asr/models/` | FunASR/ModelScope、Faster-Whisper | 可选离线预置 |
| ffmpeg | 仓库根目录 `ffmpeg.exe` / `ffprobe.exe` | 官方整合包 | 也可用系统 ffmpeg |
| V2 底模 | `pretrained_models/gsv-v2final-pretrained/` | HuggingFace | V2 |
| V3 底模 | `s1v3.ckpt`、`s2Gv3.pth`、BigVGAN 24k | HuggingFace | V3 |
| V4 底模 | `gsv-v4-pretrained/s2Gv4.pth`、`vocoder.pth` | HuggingFace | V4 |
| V2Pro 底模 | `v2Pro/s2Dv2Pro.pth`、`s2Gv2Pro.pth`、`s2Dv2ProPlus.pth`、`s2Gv2ProPlus.pth`、`sv/pretrained_eres2netv2w24s4ep4.ckpt` | HuggingFace | V2Pro |
| V5 底模 | `gsv-v5-pretrained/` | HuggingFace | 以分支/commit 为准 |

资产中心要求：sha256、大小、来源、版本、许可提示；支持下载、离线导入、损坏修复。

## 5. 数据集格式

官方 `.list`：

```text
vocal_path|speaker_name|language|text
```

示例：

```text
D:\data\voice\001.wav|my_voice|zh|这是一段测试文本。
```

语言字典：`zh` 中文、`ja` 日语、`en` 英语、`ko` 韩语、`yue` 粤语。

桌面端要求：

- 单说话人、1–10 分钟、16kHz+；
- 切片 3–15 秒；
- ASR 后必须允许人工校对；
- 训练前做静音/削波/SNR/BGM 检查。

## 6. 训练管线

官方 WebUI 的流程：填音频路径 → 切割 → 降噪（可选）→ ASR → 校对标注 → 训练。桌面端复用同一套模块，拆成可断点阶段：

| 阶段 | 官方入口 | 桌面端封装 |
|---|---|---|
| T0 人声分离 | `tools/uvr5`（WebUI/CLI） | 可选；输出干净人声 |
| T1 切片 | `python audio_slicer.py --input_path ... --output_root ...` | 参数化；超长/超短清单 |
| T2 ASR | `python tools/asr/funasr_asr.py -i <in> -o <out> -l zh` 或 `fasterwhisper_asr.py` | 生成标注；可编辑 |
| T3 预处理 | `GPT_SoVITS/prepare_datasets/*` | 生成训练清单/特征 |
| T4 S1 | `s1_train.py`（以锁定 commit 路径为准） | GPT 微调；断点 |
| T5 S2 | `s2_train.py`（以锁定 commit 路径为准） | SoVITS 微调；断点 |
| T6 发布 | 权重 + config + 参考音频 | 登记、预热、回滚 |

注意：

- 脚本路径/参数随版本变化，**必须以锁定 commit 为准**；不要把命令硬编码在 UI 层。
- 训练节点与推理节点在桌面端是同一台机器；训练时推理排队，避免显存争抢。
- 100 步冒烟通过后再跑完整步数；OOM 先降 batch，再降 duration。

## 7. 推理集成

### 7.1 官方 API

`api_v2.py` 启动：

```bash
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

端点：

- `GET/POST /tts`：合成，返回 wav/raw/ogg/aac 流；
- `GET /set_gpt_weights?weights_path=...`
- `GET /set_sovits_weights?weights_path=...`
- `GET /set_refer_audio?refer_audio_path=...`
- `GET /control?command=restart|exit`

`/tts` 关键参数：

`text`、`text_lang`、`ref_audio_path`、`aux_ref_audio_paths`、`prompt_text`、`prompt_lang`、`top_k`、`top_p`、`temperature`、`text_split_method`、`batch_size`、`batch_threshold`、`split_bucket`、`speed_factor`、`fragment_interval`、`seed`、`media_type`、`streaming_mode`、`parallel_infer`、`use_cuda_graph`、`repetition_penalty`、`sample_steps`、`super_sampling`、`overlap_length`、`min_chunk_length`、`cache_dit`、`gpt_streaming`、`use_flash_attention`。

### 7.2 桌面端推荐

- sidecar 直接复用 `GPT_SoVITS.TTS_infer_pack.TTS`（`TTS_Config` + `TTS.run`），与 `api_v2` 同源；避免再跑一个 HTTP 推理服务。
- 如果希望进程隔离/热重启，可在 worker 内启动 `api_v2.py` 的等价逻辑；但 UI 不直接访问它。
- 模型切换：`init_t2s_weights` / `init_vits_weights` / `set_ref_audio`。
- 流式：`streaming_mode=1/2/3`；`gpt_streaming` 仅 V2ProPlus/V5 系，按官方校验。
- 加速：`use_cuda_graph`、`use_flash_attention`、`cache_dit` 作为高级开关；默认保守（先关 cuda_graph，按实测开）。

### 7.3 我们的业务 API 与官方 API 的边界

- 官方 API 只负责“模型 + 参考音频 + 文本 → 音频”。
- 我们的 sidecar API 负责：任务、分段、拼接、响度、缓存、配额、能力回执、历史。
- 不要把业务字段（情绪 preset、音量、任务状态）塞进官方 `/tts`；在 sidecar 层翻译成 `ref_audio_path`、`speed_factor` 等。

## 8. 打包注意

- `api_v2.py` 使用 `tools.portable_runtime` 与 `FFMPEG_EXE`；打包时保留该运行时/路径逻辑。
- PyInstaller 需要收集 GPT-SoVITS 的配置、文本前端、G2PW、BigVGAN、vocoder 等数据文件；用 `--collect-data`/hook。
- 模型不内置；首次运行下载/离线导入。
- `numpy<2.0`、`pydantic<=2.10.6` 等约束必须在 sidecar 环境中锁定，避免 Tauri/前端依赖污染。
- 训练/推理脚本路径以锁定 commit 为准；升级时跑回归。

## 9. 已知约束

1. **无原生情绪参数**：官方 README 仍把“增强情感控制”列为未完成；情绪只走参考音频。
2. **版本差异大**：V3 24k、V4 48k、V2 系 32k（以 config 为准）；模型与底模不可混用。
3. **显存**：V2 系推理约 1.6–3.2GB；V3/V4/V5 更高；6GB 仅建议 V2/V2Pro 低配，12GB 起训练更稳。
4. **依赖敏感**：`numpy<2.0`、`transformers<5`、`pydantic<=2.10.6`；升级需回归。
5. **模型许可**：代码 MIT，权重/训练数据许可以资产页为准；不内置。
6. **V5**：可能位于 `cuda_graph_accel_v5` 分支；以实际引入的 commit 为准。

## 10. 参考

- 中文 README：https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/cn/README.md
- API 文档：`api_v2.py` 头部注释
- 依赖：`requirements.txt`
- 模型：https://huggingface.co/lj1995/GPT-SoVITS
