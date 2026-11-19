# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, copy_metadata, collect_data_files

metadata_datas = []
for package in (
    "transformers",
    "torch",
    "torchaudio",
    "gradio",
    "pandas",
    "peft",
    "torchmetrics",
    "librosa",
    "soundfile",
    "pytorch-lightning",
    "numpy",
    "scipy",
    "numba",
    "resampy",
):
    try:
        metadata_datas += copy_metadata(package)
    except Exception:
        pass

for package in ("budoux", "jieba", "jieba_fast", "pyopenjtalk", "ToJyutping", "g2p_en", "split_lang", "fast_langdetect", "safehttpx", "gradio", "faster_whisper"):
    try:
        metadata_datas += collect_data_files(package)
    except Exception:
        pass

hiddenimports = [
    "assets",
    "gpt_worker",
    "real_engine",
    "training",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "fastapi",
    "pydantic",
    "soundfile",
    "yaml",
    "numpy",
    "torch",
    "torchaudio",
    "transformers",
    "librosa",
    "resampy",
    "peft",
    "torchmetrics",
    "x_transformers",
    "ffmpeg",
    "pytorch_lightning",
    "pytorch_lightning.__about__",
    "lightning_fabric.__about__",
    "tensorboard",
    "gradio",
    "pandas",
    "matplotlib",
    "jieba",
    "jieba_fast",
    "pyopenjtalk",
    "g2p_en",
    "cn2an",
    "pypinyin",
    "split_lang",
    "fast_langdetect",
    "wordsegment",
    "rotary_embedding_torch",
    "ToJyutping",
    "g2pk2",
    "ko_pron",
    "opencc",
    "sentencepiece",
    "modelscope",
    "funasr",
    "ctranslate2",
    "onnxruntime",
    "nltk",
    "scipy",
    "sklearn",
    "hydra",
    "omegaconf",
    "torch_complex",
    "einops",
    "einx",
    "kaldiio",
    "pydub",
    "audioread",
    "soxr",
    "pooch",
    "inflect",
    "typeguard",
    "frozendict",
    "jaconv",
    "jamo",
    "proces",
    "torch_einops_utils",
    "faster_whisper",
    "ctranslate2",
    "av",
    "tokenizers",
]
hiddenimports += collect_submodules("uvicorn")
for package in (
    "jieba_fast",
    "jieba",
    "pyopenjtalk",
    "g2p_en",
    "split_lang",
    "fast_langdetect",
    "ToJyutping",
    "g2pk2",
    "ko_pron",
    "opencc",
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

a = Analysis(
    ["entry.py"],
    pathex=["."],
    binaries=[],
    datas=metadata_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "IPython", "notebook", "pytest"],
    noarchive=False,
    module_collection_mode={"x_transformers": "py"},
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voicesmith-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="voicesmith-engine",
)
