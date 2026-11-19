# ADR-003：SQLite 归 Python

## 决策

领域数据（音色/任务/模型/训练）由 Python sidecar 用 SQLite（WAL）管理；Rust 只存窗口/主题等轻量设置。

## 备选

- Rust 用 `tauri-plugin-sql` 管全部数据：Rust/Python 双写，迁移复杂。
- 服务端数据库：桌面单用户不需要。

## 理由

- 任务/模型生命周期都在 Python 侧，单写者避免一致性问题。
- SQLite 足够单用户；WAL 支持 UI 读与 worker 写。
- 文件大产物放本地目录，DB 只存路径与元数据。

## 代价

备份/迁移需 Python 侧负责；Rust 读数据需经 sidecar API。
