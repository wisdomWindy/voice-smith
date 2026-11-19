# Spec · M0/M1 可运行骨架

## 1. 目标

交付可运行的桌面骨架：

- Tauri 2 窗口加载 Vue 3 界面；
- Rust 启动/监管 Python sidecar；
- sidecar 提供 health/doctor/voices/preview/synthesis/job；
- 前端展示引擎状态、doctor 结果、试听 mock、异步任务进度；
- 建立 SQLite 与任务状态机的最小实现。

M0 不加载真实 GPT-SoVITS 权重；用 mock 合成验证链路。M1 起接入真实引擎。

## 2. 架构

```text
Tauri 2 (Rust) ── WebView2 ── Vue 3 + TS + Vite
      │ invoke/get_engine_info        │ HTTP + SSE
      │ spawn/supervise               │
Python sidecar (FastAPI, 127.0.0.1:random, token)
      │
SQLite + local files
```

## 3. 进程与端口

- Rust 选择空闲端口，生成 32 字节随机 token。
- 启动 `python sidecar/app.py --port <p> --token <t> --data-dir <dir>`。
- 轮询 `/health`；就绪后前端可请求。
- sidecar 退出/崩溃：Rust 指数退避重启，最多 3 次。
- 退出：POST `/shutdown`，超时杀进程树。

## 4. API

- `GET /health` → `{status, version, engine, model}`
- `POST /api/v1/doctor/run` → `{checks:[{id,status,detail,fix}]}`
- `GET /api/v1/voices` → `{items:[...]}`
- `POST /api/v1/previews` `{text, voice_id, params}` → `audio/wav`（M0 mock）
- `POST /api/v1/syntheses` `{text, voice_id, params, request_id}` → `202 {job_id}`
- `GET /api/v1/syntheses/{id}` → 状态/进度/音频 URL
- `GET /api/v1/events` → SSE `progress/log/state`
- `POST /api/v1/syntheses/{id}/cancel`
- `POST /shutdown`

鉴权：`Authorization: Bearer <token>`（`/health` 也校验，便于早期发现错连）。

## 5. 数据

SQLite（WAL）：

- `voices(id, name, type, status, created_at)`
- `jobs(id, text, voice_id, params_json, status, progress, audio_path, error, created_at, finished_at)`
- `settings(key, value)`

M0 只建这三张表；后续迁移加 `voice_versions/emotion_bindings/training_*`。

## 6. 前端

- 引擎状态条：starting/ready/error；未就绪禁用合成。
- 页面：工作台（文本、音色、参数、试听、提交、任务）、Doctor、设置。
- 任务：SSE 优先，轮询兜底；进度条/取消/错误码。
- 默认中文；暗色主题。

## 7. 错误码

`ENGINE_START_FAILED`、`TORCH_CUDA_MISMATCH`、`GPU_NOT_FOUND`、`VRAM_INSUFFICIENT`、`FFMPEG_MISSING`、`MODEL_MISSING`、`MODEL_CORRUPT`、`AUDIO_INVALID`、`CONFIG_INVALID`、`ENGINE_CRASHED`、`DISK_FULL`、`PATH_UNSUPPORTED`。

## 8. 非目标（本 spec）

真实 GPT-SoVITS 推理、训练、打包安装器、WebView2 离线包。M0/M1 只交付可开发、可验证的骨架。

## V4 迁移（2026-11-19）

- 默认底模从 V2Pro 切换为 V4：`gsv-v4-pretrained/s2Gv4.pth` + `vocoder.pth`。
- 推理原生 48k；S1 仍用 `s1v3.ckpt`；S2 使用 `s2_train_v3.py` + `s2v4.json`。
- V2Pro 仅保留为显存/速度兼容档，不再作为默认。
- 验收采样率改为 48k；安装器/资产哈希/doctor 同步 V4。
