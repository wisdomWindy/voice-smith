export type EngineInfo = {
  port: number
  token: string
  status: string
  pid?: number | null
  error?: string | null
}

export type RuntimeStatus = {
  installed: boolean
  path: string
}

export type Health = {
  status: string
  version: string
  engine: string
  model: string
  mock: boolean
  assets_ready: boolean
  python: string
  data_dir: string
}

export type AssetStatus = {
  id: string
  name: string
  path: string
  required: boolean
  kind: 'file' | 'dir'
  note: string
  present: boolean
  size: number
  sha256?: string
  hash_path?: string
  actual_sha256?: string
  hash_ok?: boolean | null
}

export type AssetReport = {
  engine_root: string
  model_root: string
  items: AssetStatus[]
  missing: string[]
  bad_hash?: string[]
  ready: boolean
}

export type DoctorCheck = {
  id: string
  name: string
  status: 'pass' | 'warn' | 'fail'
  detail: string
  fix: string
}

export type Voice = {
  id: string
  name: string
  type: string
  status: string
  created_at: string
  ref_audio_path?: string | null
  ref_text?: string | null
  prompt_lang?: string | null
  text_lang?: string | null
  model_version?: string | null
  engine?: string | null
  s1_model?: string | null
  s2_model?: string | null
}

export type Emotion = {
  id: string
  voice_id: string
  name: string
  ref_audio_path: string
  ref_text: string
  created_at: string
}

export type Training = {
  id: string
  request_id?: string | null
  exp_name: string
  dataset_list: string
  status: string
  stage: string
  progress: number
  detail: string
  log_url: string
  output_dir?: string | null
  s1_model?: string | null
  s2_model?: string | null
  created_at: string
  finished_at?: string | null
}

export type TrainingInput = {
  dataset_list: string
  exp_name: string
  s1_epochs?: number
  s2_epochs?: number
  batch_size?: number
  num_workers?: number
  force?: boolean
}

export type Batch = {
  batch_id: string
  jobs: Job[]
  total: number
  done: number
  progress: number
  status: string
}

export type DatasetQCItem = {
  line: number
  path: string
  duration?: number
  samplerate?: number
  channels?: number
  peak?: number
  clipping_ratio?: number
  silence_ratio?: number
  issues: string[]
}

export type DatasetQC = {
  count: number
  total_duration: number
  items: DatasetQCItem[]
  errors: string[]
  blocking: string[]
  warnings: string[]
  ok: boolean
}

export type ModelFile = {
  id: string
  name: string
  experiment: string
  kind: string
  size: number
  modified_at: string
  path: string
}

export type AssetPackStatus = {
  installing: boolean
  progress: number
  stage: string
  error: string
  message: string
  url: string
  expected_sha256: string
  installed: boolean
}

export type Job = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
  audio_url?: string | null
  audio_path?: string | null
  error?: string | null
  text?: string
  voice_id?: string
  created_at?: string
  finished_at?: string | null
}

export const isTauri = (): boolean =>
  typeof window !== 'undefined' && Boolean((window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__)

export async function getEngineInfo(): Promise<EngineInfo> {
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core')
    return await invoke<EngineInfo>('get_engine_info')
  }
  return {
    port: Number(import.meta.env.VITE_ENGINE_PORT ?? 8765),
    token: String(import.meta.env.VITE_ENGINE_TOKEN ?? 'dev-token'),
    status: 'ready',
  }
}

export async function restartEngine(): Promise<EngineInfo> {
  if (!isTauri()) return getEngineInfo()
  const { invoke } = await import('@tauri-apps/api/core')
  return await invoke<EngineInfo>('restart_engine')
}

export async function runtimeStatus(): Promise<RuntimeStatus> {
  if (!isTauri()) return { installed: true, path: '' }
  const { invoke } = await import('@tauri-apps/api/core')
  return await invoke<RuntimeStatus>('runtime_status')
}

export async function platformTag(): Promise<string> {
  if (!isTauri()) return 'windows-x64'
  const { invoke } = await import('@tauri-apps/api/core')
  return await invoke<string>('platform_tag')
}

export async function installRuntime(url: string, sha256 = ''): Promise<EngineInfo> {
  if (!isTauri()) return getEngineInfo()
  const { invoke } = await import('@tauri-apps/api/core')
  return await invoke<EngineInfo>('install_runtime', { url, sha256 })
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export class EngineClient {
  readonly base: string
  readonly token: string

  constructor(port: number, token: string) {
    this.base = `http://127.0.0.1:${port}`
    this.token = token
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return { authorization: `Bearer ${this.token}`, ...extra }
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = this.headers(init.body ? { 'content-type': 'application/json' } : {})
    const response = await fetch(`${this.base}${path}`, { ...init, headers: { ...headers, ...(init.headers ?? {}) } })
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`
      try {
        const body = await response.json()
        detail = body.detail ?? body.message ?? detail
      } catch {
        // keep status text
      }
      throw new Error(detail)
    }
    return response
  }

  async health(): Promise<Health> {
    const response = await this.request('/health')
    return (await response.json()) as Health
  }

  async doctor(): Promise<{ checks: DoctorCheck[]; summary: Record<string, number>; ok: boolean }> {
    const response = await this.request('/api/v1/doctor/run', { method: 'POST' })
    return await response.json()
  }

  async voices(): Promise<Voice[]> {
    const response = await this.request('/api/v1/voices')
    const data = (await response.json()) as { items: Voice[] }
    return data.items
  }

  async deleteVoice(voiceId: string): Promise<void> {
    await this.request(`/api/v1/voices/${voiceId}`, { method: 'DELETE' })
  }

  async emotions(voiceId: string): Promise<Emotion[]> {
    const response = await this.request(`/api/v1/voices/${voiceId}/emotions`)
    const data = (await response.json()) as { items: Emotion[] }
    return data.items
  }

  async createEmotion(voiceId: string, name: string, refAudioPath: string, refText: string): Promise<Emotion> {
    const response = await this.request(`/api/v1/voices/${voiceId}/emotions`, {
      method: 'POST',
      body: JSON.stringify({ name, ref_audio_path: refAudioPath, ref_text: refText }),
    })
    return (await response.json()) as Emotion
  }

  async deleteEmotion(emotionId: string): Promise<void> {
    await this.request(`/api/v1/emotions/${emotionId}`, { method: 'DELETE' })
  }

  async trainings(): Promise<Training[]> {
    const response = await this.request('/api/v1/trainings')
    const data = (await response.json()) as { items: Training[] }
    return data.items
  }

  async datasetQc(datasetList: string): Promise<DatasetQC> {
    const response = await this.request('/api/v1/datasets/qc', {
      method: 'POST',
      body: JSON.stringify({ dataset_list: datasetList }),
    })
    return (await response.json()) as DatasetQC
  }

  async asr(audioPath: string, language = 'zh'): Promise<string> {
    const response = await this.request('/api/v1/asr', {
      method: 'POST',
      body: JSON.stringify({ audio_path: audioPath, language }),
    })
    const data = (await response.json()) as { text: string }
    return data.text
  }

  async transcribeFolder(audioDir: string, language = 'zh', speaker = 'speaker'): Promise<{ list_path: string; count: number; total_duration: number }> {
    const response = await this.request('/api/v1/datasets/transcribe', {
      method: 'POST',
      body: JSON.stringify({ audio_dir: audioDir, language, speaker }),
    })
    return await response.json()
  }

  async uvr5(audioPath: string): Promise<{ vocal_path: string; instrumental_path: string | null }> {
    const response = await this.request('/api/v1/uvr5', {
      method: 'POST',
      body: JSON.stringify({ audio_path: audioPath }),
    })
    return await response.json()
  }

  async sliceAudio(audioPath: string, minSec = 5, maxSec = 15): Promise<{ output_dir: string; count: number; items: { path: string; duration: number }[] }> {
    const response = await this.request('/api/v1/datasets/slice', {
      method: 'POST',
      body: JSON.stringify({ audio_path: audioPath, min_sec: minSec, max_sec: maxSec }),
    })
    return await response.json()
  }

  async models(): Promise<ModelFile[]> {
    const response = await this.request('/api/v1/models')
    const data = (await response.json()) as { items: ModelFile[] }
    return data.items
  }

  async terms(): Promise<boolean> {
    const response = await this.request('/api/v1/terms')
    const data = (await response.json()) as { accepted: boolean }
    return data.accepted
  }

  async acceptTerms(): Promise<void> {
    await this.request('/api/v1/terms/accept', { method: 'POST' })
  }

  async diagnostics(): Promise<Blob> {
    const response = await this.request('/api/v1/diagnostics')
    return await response.blob()
  }

  async deleteModel(path: string): Promise<void> {
    await this.request(`/api/v1/models?path=${encodeURIComponent(path)}`, { method: 'DELETE' })
  }

  async createTraining(input: TrainingInput): Promise<Training> {
    const response = await this.request('/api/v1/trainings', {
      method: 'POST',
      body: JSON.stringify(input),
    })
    return (await response.json()) as Training
  }

  async training(id: string): Promise<Training> {
    const response = await this.request(`/api/v1/trainings/${id}`)
    return (await response.json()) as Training
  }

  async trainingLog(id: string): Promise<string> {
    const response = await this.request(`/api/v1/trainings/${id}/log`)
    const data = (await response.json()) as { log: string }
    return data.log
  }

  async cancelTraining(id: string): Promise<Training> {
    const response = await this.request(`/api/v1/trainings/${id}/cancel`, { method: 'POST' })
    return (await response.json()) as Training
  }

  async assets(): Promise<AssetReport> {
    const response = await this.request('/api/v1/assets')
    return (await response.json()) as AssetReport
  }

  async assetPack(): Promise<AssetPackStatus> {
    const response = await this.request('/api/v1/assets/asset-pack')
    return (await response.json()) as AssetPackStatus
  }

  async installAssetPack(url: string, sha256 = ''): Promise<AssetPackStatus> {
    const response = await this.request('/api/v1/assets/asset-pack/install', {
      method: 'POST',
      body: JSON.stringify({ url, sha256 }),
    })
    return (await response.json()) as AssetPackStatus
  }

  async verifyAssets(): Promise<AssetReport> {
    const response = await this.request('/api/v1/assets/verify', { method: 'POST' })
    return (await response.json()) as AssetReport
  }

  async importAsset(assetId: string, sourcePath: string): Promise<AssetStatus> {
    const response = await this.request('/api/v1/assets/import', {
      method: 'POST',
      body: JSON.stringify({ asset_id: assetId, source_path: sourcePath }),
    })
    return (await response.json()) as AssetStatus
  }

  async preview(text: string, voiceId: string, params: Record<string, unknown>): Promise<Blob> {
    const response = await this.request('/api/v1/previews', {
      method: 'POST',
      body: JSON.stringify({ text, voice_id: voiceId, params }),
    })
    return await response.blob()
  }

  async createSynthesis(
    text: string,
    voiceId: string,
    params: Record<string, unknown>,
    requestId?: string,
  ): Promise<{ job_id: string; status: string }> {
    const response = await this.request('/api/v1/syntheses', {
      method: 'POST',
      body: JSON.stringify({ text, voice_id: voiceId, params, request_id: requestId }),
    })
    return await response.json()
  }

  async getJob(jobId: string): Promise<Job> {
    const response = await this.request(`/api/v1/syntheses/${jobId}`)
    return await response.json()
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.request(`/api/v1/syntheses/${jobId}/cancel`, { method: 'POST' })
  }

  async audioBlob(jobId: string): Promise<Blob> {
    const response = await this.request(`/api/v1/syntheses/${jobId}/audio`)
    return await response.blob()
  }

  async exportBlob(jobId: string, format: 'wav' | 'mp3' = 'mp3'): Promise<Blob> {
    const response = await this.request(`/api/v1/syntheses/${jobId}/export?format=${format}`)
    return await response.blob()
  }

  async createBatch(
    texts: string[],
    voiceId: string,
    params: Record<string, unknown>,
    requestId?: string,
  ): Promise<{ batch_id: string; jobs: Job[] }> {
    const response = await this.request('/api/v1/syntheses/batch', {
      method: 'POST',
      body: JSON.stringify({ texts, voice_id: voiceId, params, request_id: requestId }),
    })
    return (await response.json()) as { batch_id: string; jobs: Job[] }
  }

  async getBatch(batchId: string): Promise<Batch> {
    const response = await this.request(`/api/v1/syntheses/batch/${batchId}`)
    return (await response.json()) as Batch
  }

  async batchZip(batchId: string): Promise<Blob> {
    const response = await this.request(`/api/v1/syntheses/batch/${batchId}/zip`)
    return await response.blob()
  }

  async cancelBatch(batchId: string): Promise<void> {
    await this.request(`/api/v1/syntheses/batch/${batchId}/cancel`, { method: 'POST' })
  }

  async jobs(): Promise<Job[]> {
    const response = await this.request('/api/v1/jobs')
    const data = (await response.json()) as { items: Job[] }
    return data.items
  }

  async waitUntilReady(timeoutMs = 15000): Promise<Health> {
    const started = Date.now()
    let lastError: unknown = null
    while (Date.now() - started < timeoutMs) {
      try {
        return await this.health()
      } catch (error) {
        lastError = error
        await sleep(400)
      }
    }
    throw lastError instanceof Error ? lastError : new Error('engine did not become ready')
  }
}
