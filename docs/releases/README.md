# Release Notes 规范

每个版本创建 `docs/releases/v<version>.md`，Release body 只列安装包：

- Windows x64：NSIS 安装器
- macOS Intel：DMG
- macOS Apple Silicon：DMG

不要列 runtime、assets、manifest 或分卷链接。安装完成后由软件首次启动自动下载对应平台运行时和离线资产。

```markdown
# VoiceSmith x.y.z

## Windows 10/11 x64
- [下载 Windows NSIS 安装器](https://github.com/wisdomWindy/voice-smith/releases/download/vy.z.z/VoiceSmith-x.y.z-windows-x64-setup.exe)

## macOS Intel
- [下载 macOS Intel DMG](https://github.com/wisdomWindy/voice-smith/releases/download/vx.y.z/VoiceSmith-x.y.z-macos-intel.dmg)

## macOS Apple Silicon
- [下载 macOS Apple Silicon DMG](https://github.com/wisdomWindy/voice-smith/releases/download/vx.y.z/VoiceSmith-x.y.z-macos-apple-silicon.dmg)

## 说明
- 安装后首次启动会自动下载对应平台的运行时与离线资产。
- macOS 未签名，首次打开需手动允许。
```
