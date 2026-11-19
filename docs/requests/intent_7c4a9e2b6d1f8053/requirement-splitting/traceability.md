# 需求-验收追溯

| 需求 | 验收项（场景 acceptance.md） | 当前状态 |
|---|---|---|
| FR-01 doctor | B1/B2/B3/B4/B5 | 开发中（M1） |
| FR-02 资产 | B2/B3/B4/B5 | 开发中（M1） |
| FR-03 试听 | F1/F2/F3 | 开发中（M0 mock） |
| FR-04 快速音色 | F5/D4 | 待 M2 |
| FR-05 训练 | E2/E4/E5/E6/E7 | 待 M3 |
| FR-06 情绪 | F6/D4 | 待 M2 |
| FR-07 参数 | F4 | 开发中（M0） |
| FR-08 批量 | F7 | 待 M2 |
| FR-09 历史/导出 | F1/F2/A5 | 待 M2 |
| FR-10 任务/错误 | G2/G3 | 开发中（M0） |
| FR-11 隐私 | A1/A4/A5 | 开发中（M1） |
| FR-12 打包 | H1/H2/H4/H5 | 待 M4 |

## 阻断项

`A1、A2、A3、B1、B2、C5、E2、E4、F1、F3、G1、H1、H2、H4`

## 备注

M0 使用 mock 合成先打通 Tauri → Vue → sidecar → job → SSE 链路；M1 接入 doctor/资产；M2 接入 GPT-SoVITS 推理；M3 接入训练；M4 打包。
