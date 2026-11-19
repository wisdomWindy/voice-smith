# ADR-001：Tauri 2 + Vue 3

## 决策

桌面壳用 Tauri 2（Rust + WebView2），前端用 Vue 3 + TypeScript + Vite。

## 备选

- PySide6：与 Python 同栈，但 UI 迭代慢、复杂编辑器/波形组件生态弱。
- Electron：生态成熟，但体积/内存大，打包更重。

## 理由

- Tauri 壳小、内存低，Windows 复用系统 WebView2。
- Vue 3 适合编辑器、参数面板、任务中心与试听组件。
- Rust 负责进程监管、文件对话框、单实例与崩溃恢复。

## 代价

三套工具链（Rust/Node/Python）、WebView2 依赖、sidecar 打包复杂；用 spike 与 ADR-004 兜底。
