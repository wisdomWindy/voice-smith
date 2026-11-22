<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { Batch, Emotion, Job, Voice } from '../lib/engine'

const engine = useEngineStore()
const text = ref('先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。')
const voices = ref<Voice[]>([])
const emotions = ref<Emotion[]>([])
const voiceId = ref('builtin_female')
const emotionId = ref('')
const speed = ref(1)
const volume = ref(80)
const previewUrl = ref('')
const audio = ref<HTMLAudioElement | null>(null)
const job = ref<Job | null>(null)
const busy = ref(false)
const previewing = ref(false)
const error = ref('')
const mode = ref<'single' | 'batch'>('single')
const batch = ref<Batch | null>(null)
const batchBusy = ref(false)
let pollToken = 0

const charCount = computed(() => text.value.length)
const estimate = computed(() => Math.max(1, Math.round(text.value.length / 4.5)))
const batchLines = computed(() => text.value.split('\n').map((line) => line.trim()).filter(Boolean))
const selectableVoices = computed(() =>
  voices.value.filter((voice) => engine.health?.mock || voice.id !== 'demo_edge'),
)
const canSubmit = computed(
  () =>
    engine.ready &&
    Boolean(voiceId.value) &&
    text.value.trim().length > 0 &&
    !busy.value &&
    !batchBusy.value,
)
const batchRunning = computed(() => !!batch.value && batch.value.jobs.some((item) => ['queued', 'running'].includes(item.status)))

function isNetworkError(err: unknown): boolean {
  return err instanceof TypeError || /failed to fetch|load failed|networkerror/i.test(String(err))
}

async function loadVoices(allowRetry = true) {
  if (!engine.ready || !engine.client) {
    await engine.init()
  }
  if (!engine.client) return
  try {
    voices.value = await engine.client.voices()
    if (!selectableVoices.value.some((voice) => voice.id === voiceId.value)) {
      voiceId.value = selectableVoices.value[0]?.id ?? ''
    }
    await loadEmotions()
    error.value = ''
  } catch (err) {
    // The sidecar can restart on a new port; refresh the client and retry once.
    if (allowRetry && isNetworkError(err)) {
      await engine.init()
      if (engine.ready) return loadVoices(false)
    }
    error.value = err instanceof Error ? err.message : String(err)
  }
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void loadVoices()
  },
  { immediate: true },
)

async function loadEmotions() {
  if (!engine.client || !voiceId.value) {
    emotions.value = []
    emotionId.value = ''
    return
  }
  try {
    emotions.value = await engine.client.emotions(voiceId.value)
    if (!emotions.value.some((item) => item.id === emotionId.value)) emotionId.value = ''
  } catch {
    emotions.value = []
    emotionId.value = ''
  }
}

watch(voiceId, () => {
  emotionId.value = ''
  void loadEmotions()
})

function revoke(url: string) {
  if (url) URL.revokeObjectURL(url)
}

async function preview() {
  if (!engine.client || !text.value.trim()) return
  previewing.value = true
  error.value = ''
  try {
    const blob = await engine.client.preview(text.value.trim(), voiceId.value, {
      speed: speed.value,
      volume: volume.value,
      emotion_id: emotionId.value || undefined,
    })
    revoke(previewUrl.value)
    previewUrl.value = URL.createObjectURL(blob)
    await nextTick()
    await audio.value?.play()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    previewing.value = false
  }
}

async function submit() {
  if (!engine.client || !canSubmit.value) return
  busy.value = true
  error.value = ''
  job.value = null
  const token = ++pollToken
  try {
    const created = await engine.client.createSynthesis(
      text.value.trim(),
      voiceId.value,
      { speed: speed.value, volume: volume.value, emotion_id: emotionId.value || undefined },
      crypto.randomUUID(),
    )
    while (token === pollToken) {
      const current = await engine.client.getJob(created.job_id)
      job.value = current
      if (['succeeded', 'failed', 'cancelled'].includes(current.status)) break
      await new Promise((resolve) => setTimeout(resolve, 600))
    }
    if (job.value?.status === 'failed') {
      error.value = job.value.error || '合成失败'
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function cancel() {
  if (!engine.client || !job.value) return
  try {
    await engine.client.cancelJob(job.value.id)
    pollToken += 1
    job.value = { ...job.value, status: 'cancelled' }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function submitBatch() {
  if (!engine.client || !batchLines.value.length) return
  batchBusy.value = true
  error.value = ''
  batch.value = null
  const token = ++pollToken
  try {
    const created = await engine.client.createBatch(
      batchLines.value,
      voiceId.value,
      { speed: speed.value, volume: volume.value, emotion_id: emotionId.value || undefined },
      crypto.randomUUID(),
    )
    while (token === pollToken) {
      const snapshot = await engine.client.getBatch(created.batch_id)
      batch.value = snapshot
      if (!snapshot.jobs.some((item) => ['queued', 'running'].includes(item.status))) break
      await new Promise((resolve) => setTimeout(resolve, 800))
    }
    const failed = batch.value?.jobs.filter((item) => item.status === 'failed') ?? []
    if (failed.length) error.value = `${failed.length} 条失败；其余可下载。`
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    batchBusy.value = false
  }
}

async function cancelBatchRun() {
  if (!engine.client || !batch.value) return
  try {
    await engine.client.cancelBatch(batch.value.batch_id)
    pollToken += 1
    batch.value = { ...batch.value, jobs: batch.value.jobs.map((item) => (['queued', 'running'].includes(item.status) ? { ...item, status: 'cancelled' as const } : item)) }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function switchMode(next: 'single' | 'batch') {
  mode.value = next
  error.value = ''
}

onBeforeUnmount(() => {
  pollToken += 1
  revoke(previewUrl.value)
})
</script>

<template>
  <section class="page">
    <div class="page-grid">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>文本</h2>
          </div>
          <span class="tag">{{ mode === 'single' ? `${charCount} 字 · 约 ${estimate} 秒` : `${batchLines.length} 条` }}</span>
        </div>
        <div class="row gap" style="margin-bottom:10px">
          <button class="button small" :class="mode === 'single' ? 'primary' : 'ghost'" @click="switchMode('single')">单条</button>
          <button class="button small" :class="mode === 'batch' ? 'primary' : 'ghost'" @click="switchMode('batch')">批量</button>
        </div>
        <textarea
          v-model="text"
          class="textarea"
          maxlength="10000"
          :placeholder="mode === 'single' ? '输入要合成的文本，支持中文、英文与标点。' : '每行一条文本，最多 50 条。'"
        />
        <div class="row space-between">
          <span class="muted small">
            {{ mode === 'single' ? '单任务上限 10,000 字' : '每行一条，最多 50 条；失败单条不影响其余' }} ·
            {{ engine.health?.mock ? 'mock 输出' : 'GPT-SoVITS 输出' }}
          </span>
          <span class="muted small">{{ mode === 'single' ? `${charCount} / 10000` : `${batchLines.length} / 50` }}</span>
        </div>

        <div class="divider" />

        <div class="form-grid">
          <label class="field">
            <span>音色</span>
            <select v-model="voiceId" class="input">
              <option v-if="!selectableVoices.length" value="" disabled>没有可用音色</option>
              <option v-for="voice in selectableVoices" :key="voice.id" :value="voice.id">
                {{ voice.name }} · {{ voice.type }}
              </option>
            </select>
          </label>
          <label v-if="emotions.length" class="field">
            <span>情绪参考</span>
            <select v-model="emotionId" class="input">
              <option value="">默认（使用音色参考）</option>
              <option v-for="item in emotions" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
          <label class="field">
            <span>语速 {{ speed.toFixed(2) }}×</span>
            <input v-model.number="speed" class="range" type="range" min="0.5" max="2" step="0.05" />
          </label>
          <label class="field">
            <span>音量 {{ volume }}</span>
            <input v-model.number="volume" class="range" type="range" min="0" max="100" step="1" />
          </label>
        </div>

        <div class="row gap">
          <button v-if="mode === 'single'" class="button primary" :disabled="!canSubmit" @click="submit">
            {{ busy ? '合成中…' : '提交合成' }}
          </button>
          <button v-else class="button primary" :disabled="!canSubmit || !batchLines.length" @click="submitBatch">
            {{ batchBusy ? '批量合成中…' : '开始批量合成' }}
          </button>
          <button class="button ghost" :disabled="previewing || !engine.ready || !text.trim()" @click="preview">
            {{ previewing ? '生成试听…' : '试听 50 字' }}
          </button>
          <button v-if="mode === 'single' && job && ['queued', 'running'].includes(job.status)" class="button danger" @click="cancel">
            取消
          </button>
          <button v-if="mode === 'batch' && batchRunning" class="button danger" @click="cancelBatchRun">
            取消批量
          </button>
        </div>

        <div v-if="error" class="inline-error">{{ error }}</div>

        <div v-if="previewUrl" class="audio-block">
          <div class="muted small">{{ engine.health?.mock ? '试听（mock）' : '试听' }}</div>
          <audio ref="audio" :src="previewUrl" controls />
        </div>

        <div v-if="mode === 'single' && job" class="job-block">
          <div class="row space-between">
            <strong>任务 {{ job.id }}</strong>
            <span class="tag" :class="job.status">{{ job.status }}</span>
          </div>
          <div class="progress">
            <div class="progress-bar" :style="{ width: `${job.progress}%` }" />
          </div>
          <div class="row space-between muted small">
            <span>{{ job.progress }}%</span>
            <span>{{ job.status === 'succeeded' ? '已完成' : '处理中' }}</span>
          </div>
          <p v-if="job.status === 'succeeded'" class="muted small">
            音频已保存，到 <RouterLink to="/tasks">任务</RouterLink> 页点「打开文件夹」查看。
          </p>
        </div>

        <div v-if="mode === 'batch' && batch" class="job-block">
          <div class="row space-between">
            <strong>批量 {{ batch.batch_id }}</strong>
            <span class="tag">{{ batch.done }} / {{ batch.total }}</span>
          </div>
          <div class="progress">
            <div class="progress-bar" :style="{ width: `${batch.progress}%` }" />
          </div>
          <ol class="batch-list">
            <li v-for="item in batch.jobs" :key="item.id">
              <span class="ellipsis">{{ item.text }}</span>
              <span class="tag" :class="item.status">{{ item.status }}</span>
            </li>
          </ol>
          <p v-if="batch.done === batch.total" class="muted small">
            音频已保存，到 <RouterLink to="/tasks">任务</RouterLink> 页点「打开文件夹」查看。
          </p>
        </div>
      </div>

      <aside class="card side-card">
        <h2>本机引擎</h2>
        <div class="kv">
          <span>状态</span><strong>{{ engine.status }}</strong>
          <span>Python</span><strong>{{ engine.health?.python ?? '—' }}</strong>
          <span>数据目录</span><strong class="ellipsis">{{ engine.health?.data_dir ?? '—' }}</strong>
        </div>
        <button class="button ghost" @click="engine.restart()" :disabled="engine.status === 'starting'">
          重启引擎
        </button>
      </aside>
    </div>
  </section>
</template>
