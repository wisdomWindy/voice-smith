#define MyAppName "VoiceSmith"
#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "VoiceSmith"
#define MyAppExeName "voice-smith.exe"
#ifndef ReleaseDir
#define ReleaseDir "C:\Users\yangjianlin\.voicesmith\tauri-target\release"
#endif
#ifndef OutputDir
#define OutputDir "C:\Users\yangjianlin\.voicesmith\inno-output"
#endif

[Setup]
AppId={{6E2A7D2A-6E42-4F7B-9A9D-2B8F1E0A4C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\VoiceSmith
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=VoiceSmith-{#MyAppVersion}-Setup
SetupIconFile=..\src-tauri\icons\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: checkedonce

[Files]
Source: "{#ReleaseDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\sidecar\7zr.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\release\SBOM.json"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\docs\release\THIRD_PARTY_NOTICES.md"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
