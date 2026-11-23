import { APP_VERSION } from './release'
import { isTauri } from './engine'

const REPO = 'wisdomWindy/voice-smith'
const RELEASES = `https://github.com/${REPO}/releases`

export type UpdateStatus = {
  available: boolean
  version?: string
  body?: string
  message: string
  downloadUrl?: string
}

function parts(version: string): number[] {
  return version.replace(/^v/, '').split('.').map((value) => Number.parseInt(value, 10) || 0)
}

function isNewer(remote: string, local: string): boolean {
  const a = parts(remote)
  const b = parts(local)
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const left = a[i] ?? 0
    const right = b[i] ?? 0
    if (left !== right) return left > right
  }
  return false
}

async function checkGithub(): Promise<UpdateStatus> {
  const response = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
    headers: { accept: 'application/vnd.github+json' },
  })
  if (!response.ok) throw new Error(`GitHub 返回 ${response.status}`)
  const release = (await response.json()) as {
    tag_name?: string
    body?: string
    html_url?: string
    draft?: boolean
    prerelease?: boolean
  }
  if (release.draft || release.prerelease || !release.tag_name) {
    return { available: false, message: '当前已是最新版本' }
  }
  const version = release.tag_name.replace(/^v/, '')
  if (!isNewer(version, APP_VERSION)) {
    return { available: false, message: '当前已是最新版本' }
  }
  return {
    available: true,
    version,
    body: release.body ?? '',
    message: `发现新版本 ${version}`,
    downloadUrl: release.html_url || `${RELEASES}/tag/v${version}`,
  }
}

export async function checkForUpdate(): Promise<UpdateStatus> {
  if (!isTauri()) return { available: false, message: '仅桌面端支持更新检查' }
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = await check()
    if (!update) return { available: false, message: '当前已是最新版本' }
    return {
      available: true,
      version: update.version,
      body: update.body ?? '',
      message: `发现新版本 ${update.version}`,
    }
  } catch {
    // Releases before 0.2.25 have no latest.json; fall back to the GitHub API
    // and send the user to the release page instead of failing the check.
    return checkGithub()
  }
}

export async function installUpdate(onProgress?: (percent: number) => void): Promise<void> {
  const { check } = await import('@tauri-apps/plugin-updater')
  const update = await check()
  if (!update) throw new Error('当前已是最新版本')
  let downloaded = 0
  let total = 0
  await update.downloadAndInstall((event) => {
    if (event.event === 'Started') total = event.data.contentLength ?? 0
    if (event.event === 'Progress') {
      downloaded += event.data.chunkLength
      if (total > 0 && onProgress) onProgress(Math.min(100, Math.round((downloaded / total) * 100)))
    }
    if (event.event === 'Finished' && onProgress) onProgress(100)
  })
  const { relaunch } = await import('@tauri-apps/plugin-process')
  await relaunch()
}

export async function openReleasePage(url: string): Promise<void> {
  const { openUrl } = await import('@tauri-apps/plugin-opener')
  await openUrl(url)
}
