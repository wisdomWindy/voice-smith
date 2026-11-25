# VoiceSmith Offline Assets（权重与工具包）

从 0.3 起，资产包**只包含权重与工具**；GPT-SoVITS 引擎源码随安装包分发
（`resources/upstream/GPT-SoVITS`），不再有 `v5-engine` 单体 Release 依赖。

## Artifact

- 文件：`dist-assets/VoiceSmith-Offline-Assets.7z`
- 分卷产物：`assets.partNN` + `assets-<platform>-manifest.json`
- 体积参考：约 5.5GB（V5 所需权重 + FunASR + UVR5 + ffmpeg）

Contents:

```text
gpt-sovits/GPT_SoVITS/pretrained_models/
  chinese-roberta-wwm-ext-large/     BERT
  chinese-hubert-base/               HuBERT
  s1v3.ckpt                          GPT
  gsv-v5-pretrained/                 s2Gv5turbo.pth + vocoder.pth
  sv/                                ERes2NetV2 说话人向量
  fast_langdetect/lid.176.bin        语种识别
gpt-sovits/GPT_SoVITS/text/G2PWModel/    g2pW.onnx 等
gpt-sovits/tools/uvr5/uvr5_weights/      UVR5 分离权重
gpt-sovits/tools/asr/models/             FunASR paraformer/vad/punc
gpt-sovits/tools/AP_BWE_main/24kto48k/   超分（可选）
bin/ffmpeg.exe, bin/ffprobe.exe
manifest.json                        每个文件的 size + sha256
```

**不含**：引擎源码、Python 运行时、torch wheel、用户数据。

## 生成

```powershell
# 需要一份带权重的 GPT-SoVITS 目录（默认读 VOICE_SMITH_WEIGHTS_SRC，
# 否则 D:\program\GPT-SoVITS-v5，再否则旧的 APPDATA engine 目录）
scripts\build-assets-pack.ps1 -WeightsRoot D:\program\GPT-SoVITS-v5

# 分卷 + manifest（同时生成 runtime-bundle.json）
scripts\split-release-assets.ps1 -Version 0.3.0
```

构建脚本只拷贝白名单目录，因此旧目录里的 `runtime/`、`.venv/`、源码不会进入资产包。

## Hosting

把 `assets.partNN` 与 `assets-<platform>-manifest.json` 上传到 Release（`release-packs.yml`
在带权重的 self-hosted runner 上完成），或放到任意 HTTPS 静态站点。然后：

- 首启「首次设置」弹窗使用 `src/lib/release.ts` 里的 manifest URL；
- 或设置 `VOICE_SMITH_ASSETS_URL=<manifest-or-7z-url>`；
- 或设置 `VOICE_SMITH_ASSETS_SHA256=<sha256>` 强制校验。

## Install flow

1. Thin installer：`VoiceSmith-<version>-Setup.exe`（含引擎源码，见 `thin-distribution.md`）。
2. 首启只弹一个「首次设置」弹窗（运行时 + 离线资产包 + 使用规约），确认一次后自动按顺序
   安装；运行时装完后同一个弹窗继续下载离线资产，不再分步确认。
3. Sidecar 下载 manifest/分卷到 `<data>/asset-pack.7z`，校验 sha256，用 `7zr.exe` 解压。
4. 按布局导入：`gpt-sovits/` → `<data>/assets/gpt-sovits`，`bin/` → `<data>/assets/bin`；
   旧包（`engine/GPT-SoVITS/`）只导入权重目录与 `runtime/ffmpeg*.exe`。
5. 调用 `sidecar/engine_paths.py` 建立引擎挂载，校验 `s1v3.ckpt` / `s2Gv5turbo.pth` /
   `vocoder.pth` 存在，然后重启 sidecar。

## Verified

`scripts/engine_paths_selfcheck.py` 覆盖：挂载创建/幂等、上游相对路径可见、旧就地权重
目录不被删除、ffmpeg 解析、资产页 `ready` 判定。CI 在 `frontend-and-python` job 中执行。
