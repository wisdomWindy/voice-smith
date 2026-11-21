# ADR-004：引擎源码 vendor 进仓库，权重下沉到 data/assets

- 状态：已接受
- 日期：2026-11-21
- 取代：原先「单体 `v5-engine` 离线资产包同时提供引擎源码与权重」的做法

## 背景

VoiceSmith 早期把 GPT-SoVITS 源码和权重一起打进一个离线资产包（3.02GiB），
通过 `v5-engine` Release 的 manifest 分发。问题：

1. 引擎版本被外部 Release 绑架：仓库里没有源码，`cargo check`/CI 无法验证路径契约，
   升级/回滚只能整包替换。
2. 源码与权重同包，导致每次改一行 sidecar 都要重新下载/校验数 GiB。
3. 干净机上的安装顺序强耦合：没有资产包就无法判断引擎是否存在，doctor 语义模糊。
4. 参考项目 `voice-generator` 已经采用 `vendor/<engine>` + `<data>/pretrain` 的分层，
   证明该模式可维护。

## 决策

1. **源码 vendor 进仓库**：`vendor/GPT-SoVITS` 只含源码（排除 runtime、`.venv`、
   `pretrained_models`、旧版本权重、缓存、CUDA DLL、BigVGAN 演示数据）。
   `VENDORED.md` 记录来源/排除项，`VENDOR_MANIFEST.json` 记录逐文件 sha256。
2. **权重与工具下沉**：离线资产包只含权重/工具，安装到 `<data>/assets`：
   `assets/gpt-sovits/...`（引擎同构路径）与 `assets/bin`（ffmpeg）。
3. **挂载而非复制**：`sidecar/engine_paths.py` 在引擎树内为 6 个路径创建
   junction/symlink（`pretrained_models`、`text/G2PWModel`、`uvr5_weights`、
   `asr/models`、`24kto48k`、`runtime`），以零改上游源码的方式满足其相对路径查找。
   目标已存在为普通目录时保持原样（`unmanaged`），绝不删除用户文件。
4. **安装包携带源码**：`pnpm stage:engine` 把 vendor 源码复制到
   `src-tauri/resources/upstream`，Tauri/Inno 随安装包分发；Rust 解析
   `VOICE_SMITH_ENGINE` → 开发态 vendor → `resources/upstream` → 旧 `<install>/engine`。
5. **兼容旧数据**：旧单体资产包仍可安装，但只导入其中权重目录与 ffmpeg，忽略旧源码；
   旧 `<install>/engine/GPT-SoVITS`（含源码+权重）仍可被解析，已存在的就地权重目录不会
   被挂载覆盖。

## 后果

正面：

- 引擎版本与源码可 review、可测试、可回滚；CI 能跑 `pnpm stage:engine` 与路径自检。
- 升级 sidecar 不再触发数 GiB 资产重下；权重与源码生命周期解耦。
- 安装包可离线自证引擎存在；`doctor`/资产页能区分「源码缺失」和「权重缺失」。

代价：

- 安装包体积从 ~3.5MB 增至 ~55MB（源码约 49MB，主要是日语词典与 cmudict 数据）。
- 引擎树需要可写以创建挂载；只读场景（macOS `.app`）增加一次性源码复制兜底。
- junction 对杀软/备份工具不透明，需要在文档中说明（权重仍在 `data/assets`）。
- `release-all.yml` 不再发布资产 manifest，改由 `release-packs.yml`（带权重的
  self-hosted runner）发布。

## 验证

- `cargo check` / `cargo test --lib`：引擎解析候选顺序（vendor、upstream、legacy）。
- `python -m compileall sidecar` 与 `scripts/engine_paths_selfcheck.py`：挂载/幂等/不删文件/
  ffmpeg/资产页 ready。
- `pnpm build` + `pnpm stage:engine`：前端与 staged 资源、无权重泄漏。
- 文档：`docs/packaging.md`、`docs/GPT-SoVITS-integration.md`、`docs/release/*`。
