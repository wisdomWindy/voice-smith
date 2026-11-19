import { isTauri } from './engine'

export type UpdateStatus = {
  available: boolean
  version?: string
  body?: string
  message: string
}

export async function checkForUpdate(): Promise<UpdateStatus> {
  if (!isTauri()) return { available: false, message: '仅桌面端支持更新检查' }
  const { check } = await import('@tauri-apps/plugin-updater')
  const update = await check()
  if (!update) return { available: false, message: '当前已是最新版本' }
  return {
    available: true,
    version: update.version,
    body: update.body ?? '',
    message: `发现新版本 ${update.version}`,
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
