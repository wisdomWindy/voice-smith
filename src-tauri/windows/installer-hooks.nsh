; VoiceSmith NSIS installer hooks (Tauri v2 hook macros).

; Updates must never reuse the previous Python runtime or vendored engine
; sources: the runtime pack carries the sidecar code, so a stale copy can
; silently keep old behaviour. Remove both before the new files are copied.
; User data (data/, projects/) is deliberately preserved.
!macro NSIS_HOOK_PREINSTALL
  DetailPrint "VoiceSmith: removing previous runtime and engine files"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\upstream"
!macroend

; Force VoiceSmith shortcuts to use the bundled application icon.
!macro NSIS_HOOK_POSTINSTALL
  ${If} ${FileExists} "$DESKTOP\${PRODUCTNAME}.lnk"
    CreateShortCut "$DESKTOP\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe" "" "$INSTDIR\icon.ico" 0
  ${EndIf}
  ${If} ${FileExists} "$SMPROGRAMS\${PRODUCTNAME}.lnk"
    CreateShortCut "$SMPROGRAMS\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe" "" "$INSTDIR\icon.ico" 0
  ${EndIf}
!macroend
