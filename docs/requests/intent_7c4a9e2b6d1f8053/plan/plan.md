# Plan · M0/M1

## 当前迭代（本会话）

1. 创建 Tauri 2 + Vue 3 + TS 工程骨架。
2. Python sidecar：FastAPI + SQLite + health/doctor/voices/preview/synthesis/SSE。
3. Rust：选端口、生成 token、启动 sidecar、`get_engine_info`、重启/退出。
4. Vue：引擎状态、doctor、编辑器、试听、异步任务、错误提示。
5. 验证：sidecar API 测试、前端 build、Tauri cargo check。
6. 文档：开发运行说明、下一步接入 GPT-SoVITS。

## 里程碑

| 阶段 | 内容 |
|---|---|
| M0 | Tauri/Vue/sidecar 打通；mock 合成；doctor 雏形 |
| M1 | doctor 八项；资产中心；SQLite 完整表；任务中心 |
| M2 | 接 `GPT_SoVITS.TTS_infer_pack.TTS`；零样本；导出 |
| M3 | 训练管线；断点；模型库 |
| M4 | PyInstaller sidecar + Tauri NSIS + WebView2 |
| M5 | 内测/修复/发布 |

## 风险

- 本机 Python 3.13 与 GPT-SoVITS 支持的 3.10–3.12 不一致：sidecar 用 uv 建 3.11 venv；M2 前必须切换。
- MSVC 在 `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`，PATH 未包含，cargo 构建需 vcvars 或显式 PATH。
- 真实模型/权重未下载；M0 用 mock，避免把“骨架可跑”误判为“引擎可用”。

## 验收（本迭代）

- `pnpm build` 通过。
- `python sidecar/app.py` 启动，`/health` 200。
- `POST /api/v1/syntheses` 创建任务，SSE/轮询到 succeeded，返回 wav。
- `cargo check` 通过（或记录缺失工具链）。

## V4 迁移步骤

1. 下载 V4 s2Gv4/vocoder 并加入资产清单与 sha256。
2. gpt_worker/gpt_tts 默认 version=v4、vits=s2Gv4。
3. 训练 S2 改 s2_train_v3 + s2v4.json；单卡用 gloo 进程组包装。
4. 微调权重写 V4 header，保证 init_vits_weights 识别。
5. 重跑推理/训练/安装器验收，更新 verification/review。
