# ADR-002：Python sidecar + 本地 HTTP/SSE

## 决策

Python 引擎以 sidecar 进程运行，FastAPI + Uvicorn 绑定 `127.0.0.1` 随机端口；每次启动生成 bearer token；前端用 HTTP + SSE。

## 备选

- stdio JSON-RPC：无端口，但流式音频/日志/文件传输实现复杂。
- 把 Python 嵌入 Rust：打包/崩溃隔离/依赖管理更难。

## 理由

- SSE 适合进度/日志；HTTP 适合预览音频与文件下载。
- loopback + token + CORS 限制足够桌面场景。
- sidecar 崩溃可由 Rust 监管重启，UI 不受影响。

## 代价

端口/token 生命周期、防火墙误报、sidecar 打包需额外工作。
