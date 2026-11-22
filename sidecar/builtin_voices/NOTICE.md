# Built-in voice references

The reference recordings in this directory come from the AISHELL-3 corpus:

- AISHELL-3, OpenSLR SLR93, Beijing Shell Shell Technology Co., Ltd.
- Source: https://openslr.org/93
- License: Apache License 2.0 (see `LICENSE-APACHE-2.0.txt`)
- Files used unchanged:
  - `female_aishell3.wav` — `SSB00050005.wav`
  - `male_aishell3.wav` — `SSB13650001.wav`

VoiceSmith copies these references into the local data directory and uses them
only for zero-shot timbre reference. They are not used to identify or represent
the original speakers.
