export const RELEASE_TAG = 'v0.1.4'
export const RELEASE_BASE = `https://github.com/wisdomWindy/voice-smith/releases/download/${RELEASE_TAG}`

export const RUNTIME_MANIFESTS: Record<string, string> = {
  'windows-x64': `${RELEASE_BASE}/runtime-windows-x64-manifest.json`,
  'macos-intel': `${RELEASE_BASE}/runtime-macos-intel-manifest.json`,
  'macos-arm64': `${RELEASE_BASE}/runtime-macos-arm64-manifest.json`,
}

export const ASSETS_MANIFESTS: Record<string, string> = {
  'windows-x64': `${RELEASE_BASE}/assets-windows-x64-manifest.json`,
  'macos-intel': `${RELEASE_BASE}/assets-macos-intel-manifest.json`,
  'macos-arm64': `${RELEASE_BASE}/assets-macos-arm64-manifest.json`,
}

export function runtimeManifest(platform: string): string {
  return RUNTIME_MANIFESTS[platform] ?? RUNTIME_MANIFESTS['windows-x64']
}

export function assetsManifest(platform: string): string {
  return ASSETS_MANIFESTS[platform] ?? ASSETS_MANIFESTS['windows-x64']
}
