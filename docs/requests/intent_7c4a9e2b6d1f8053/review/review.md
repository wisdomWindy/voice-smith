# Review · VoiceSmith 0.1.0

日期：2026-11-19  
结论：**不通过（不可发布）**  
说明：功能主链已打通，但干净机/离线、资产完整性、性能与长稳验收未完成，不能宣告完成。

## 已通过（有证据）

| 项 | 证据 |
|---|---|
| Tauri 2 + Vue 3 + FastAPI sidecar 启动 | `verification.md` §1 |
| doctor 8/8（Python/torch/CUDA/GPU/ffmpeg/磁盘/文本前端/权重） | `verification.md` §2 |
| V2Pro 真实推理 | `verification.md` §3，16–18 秒 |
| S1/S2 训练、自动发布、微调推理 | `verification.md` §4 |
| 批量/导出/历史 | `verification.md` §5 |
| Inno 2.15GB 安装器、无 Python/PATH 启动 | `verification.md` §6 |
| 情绪参考 | `verification.md` §7 |
| 模型库 19 files | `verification.md` §9 |
| ASR 16 files / 132.49s | `verification.md` §10 |
| UVR5 人声分离 | `verification.md` §11 |
| 使用规约、诊断包 | `verification.md` §12 |
| 资产 sha256 与篡改模拟 | `verification.md` §13 |
| 3 分钟切片 18 段/32k/单声道 | `verification.md` §14 |
| V4 默认推理/训练/48k | `verification.md` §15 |
| 离线资产包 3.02GiB + 下载安装 | `verification.md` §16 |
| S1 断点恢复、训练取消 0.6s | `verification.md` §4 |
| SBOM 548 components | `docs/release/SBOM.json` |

## 未通过（阻断）

1. **A1/H1 干净 VM**：只在当前机器用“空 PATH + 无环境变量”验证；未在无 Python/Node/Rust 的干净 Win10/11 VM 走安装→首启→doctor→导入→推理→训练。
2. **B2 离线导入**：引擎/权重来自手动复制；资产中心没有完整断网导入/修复/sha256 拒绝用例。
3. **B2/B4 离线导入与修复**：未做断网完整导入；损坏资产重下/替换未走通。B3 已用 sha256 期望值篡改模拟验证 `bad_hash`，但未对真实权重做 1 字节修改。
4. **C4/C6 重采样与低数据量豁免**：切片已统一 48k 单声道；低数据量显式豁免流程未做。
5. **D1–D4 全链与幂等**：UVR5/ASR/训练是分散入口，未串成一次任务；无 preprocess_manifest 与取消重跑幂等。
6. **E1/E3/E6**：无 6GB/12GB batch 推荐；无 2000 步长训；OOM 自愈未真实触发成功。
7. **F1–F8**：缺 10s 样本 RTF 表、削波/峰值统计、同参重跑 diff、6GB 基线。
8. **G1/G5/G6**：无训练满载 UI P95、24h 浸泡、中文/空格路径训练。
9. **H2/H3/H6**：无断网全流程、DLL 扫描、上一版本降级。
10. **I1**：需求-验收矩阵覆盖率未计算。
11. **Release 下载全链未完整验证**：v0.1.0 已发布 2 个 runtime part + 2 个 assets part，但一次 GitHub 实际下载在 1.13GB 处中断，需重试完整安装。

12. **macOS 运行时/资产未发布**：macOS Intel/Apple Silicon DMG 已构建，但 runtime/assets 仍是 Windows-only。

13. **A2 安装包内许可证**：SBOM/Notice 已加入安装器，但未逐项核对 Tauri/Vue/Python 许可证文本。

## 交付物现状

- 安装器：`C:\Users\yangjianlin\.voicesmith\inno-output\VoiceSmith-0.1.0-Setup.exe`（2.15GB）
- 安装后：`licenses/SBOM.json`、`licenses/THIRD_PARTY_NOTICES.md`
- 无 Python/PATH：doctor 8/8、推理 18.4s、诊断包 3 文件、卸载目录为 0
- 未完成：干净 VM、断网导入、性能/长稳、回滚、矩阵

## 裁决

- 不进入 `complete`。
- 优先回滚/补做：B2/B3/B4（资产）→ F3（RTF）→ G1（UI 延迟）→ H1/H2（干净机/离线）→ I1（矩阵）。
