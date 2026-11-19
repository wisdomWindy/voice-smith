<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import { isTauri, type DatasetQC, type Training } from '../lib/engine'

const engine = useEngineStore()
const items = ref<Training[]>([])
const activeId = ref('')
const log = ref('')
const error = ref('')
const starting = ref(false)
const qc = ref<DatasetQC | null>(null)
const qcBusy = ref(false)
const audioDir = ref('')
const asrBusy = ref(false)
const asrMessage = ref('')
const uvrFile = ref('')
const uvrBusy = ref(false)
const uvrMessage = ref('')
const sliceFile = ref('')
const sliceBusy = ref(false)
const sliceMessage = ref('')
const datasetList = ref('')
const expName = ref('my_voice')
const s1Epochs = ref(5)
const s2Epochs = ref(2)
const batchSize = ref(2)
const force = ref(false)
let timer: number | undefined

const active = computed(() => items.value.find((item) => item.id === activeId.value) || items.value[0])
const busy = computed(() => active.value && ['queued', 'running', 'cancelling'].includes(active.value.status))

async function load() {
  if (!engine.client) return
  try {
    items.value = await engine.client.trainings()
    if (!activeId.value && items.value.length) activeId.value = items.value[0].id
    if (active.value) log.value = await engine.client.trainingLog(active.value.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function runQc() {
  if (!engine.client || !datasetList.value.trim()) return
  qcBusy.value = true
  error.value = ''
  try {
    qc.value = await engine.client.datasetQc(datasetList.value.trim())
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    qcBusy.value = false
  }
}

async function runAsr() {
  if (!engine.client || !audioDir.value.trim()) return
  asrBusy.value = true
  asrMessage.value = ''
  error.value = ''
  try {
    const result = await engine.client.transcribeFolder(audioDir.value.trim())
    datasetList.value = result.list_path
    asrMessage.value = `ASR 完成：${result.count} 条 / ${result.total_duration.toFixed(1)} 秒 → ${result.list_path}`
    await runQc()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    asrBusy.value = false
  }
}

async function runUvr() {
  if (!engine.client || !uvrFile.value.trim()) return
  uvrBusy.value = true
  uvrMessage.value = ''
  error.value = ''
  try {
    const result = await engine.client.uvr5(uvrFile.value.trim())
    uvrMessage.value = `人声：${result.vocal_path}`
    audioDir.value = result.vocal_path.replace(/[\\/][^\\/]+$/, '')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    uvrBusy.value = false
  }
}

async function runSlice() {
  if (!engine.client || !sliceFile.value.trim()) return
  sliceBusy.value = true
  sliceMessage.value = ''
  error.value = ''
  try {
    const result = await engine.client.sliceAudio(sliceFile.value.trim())
    sliceMessage.value = `切片完成：${result.count} 段 → ${result.output_dir}`
    audioDir.value = result.output_dir
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    sliceBusy.value = false
  }
}

async function start() {
  if (!engine.client) return
  starting.value = true
  error.value = ''
  try {
    const job = await engine.client.createTraining({
      dataset_list: datasetList.value.trim(),
      exp_name: expName.value.trim() || 'my_voice',
      s1_epochs: s1Epochs.value,
      s2_epochs: s2Epochs.value,
      batch_size: batchSize.value,
      force: force.value,
    })
    activeId.value = job.id
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    starting.value = false
  }
}

async function cancel() {
  if (!engine.client || !active.value) return
  await engine.client.cancelTraining(active.value.id)
  await load()
}

async function browse() {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  const path = await invoke<string | null>('pick_training_file')
  if (path) datasetList.value = path
}

function pick(item: Training) {
  activeId.value = item.id
  void load()
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void load()
  },
  { immediate: true },
)

onMounted(() => {
  timer = window.setInterval(() => {
    if (busy.value) void load()
  }, 2000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>训练工坊</h2>
          <p class="muted small">准备清单 → BERT/HuBERT/SV/语义 → S1 → S2。数据集至少 1 分钟；训练期间可取消。</p>
        </div>
        <span class="tag">M3</span>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div class="form-grid">
        <label class="field" style="grid-column: span 2">
          <span>数据集清单（.list：路径|说话人|语言|文本）</span>
          <div class="row gap">
            <input v-model="datasetList" class="input" style="flex:1" placeholder="C:\audio\dataset.list" />
            <button v-if="isTauri()" class="button ghost" type="button" @click="browse">选择文件</button>
          </div>
        </label>
        <label class="field">
          <span>实验名</span>
          <input v-model="expName" class="input" />
        </label>
        <label class="field">
          <span>S1 epochs</span>
          <input v-model.number="s1Epochs" class="input" type="number" min="1" max="50" />
        </label>
        <label class="field">
          <span>S2 epochs</span>
          <input v-model.number="s2Epochs" class="input" type="number" min="1" max="50" />
        </label>
        <label class="field">
          <span>batch</span>
          <input v-model.number="batchSize" class="input" type="number" min="1" max="8" />
        </label>
        <label class="check">
          <input v-model="force" type="checkbox" />
          <span>不足 1 分钟也强制训练</span>
        </label>
      </div>
      <div class="divider" />
      <label class="field">
        <span>长音频切片（5–15s，48k 单声道）</span>
        <div class="row gap">
          <input v-model="sliceFile" class="input" style="flex:1" placeholder="C:\audio\long.wav" />
          <button class="button ghost" :disabled="sliceBusy || !sliceFile.trim()" @click="runSlice">
            {{ sliceBusy ? '切片中…' : '开始切片' }}
          </button>
        </div>
      </label>
      <div v-if="sliceMessage" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ sliceMessage }}</div>
      <label class="field">
        <span>UVR5 人声分离（HP2 模型，可选）</span>
        <div class="row gap">
          <input v-model="uvrFile" class="input" style="flex:1" placeholder="C:\audio\mix.wav" />
          <button class="button ghost" :disabled="uvrBusy || !uvrFile.trim()" @click="runUvr">
            {{ uvrBusy ? '分离中…' : 'UVR5 分离' }}
          </button>
        </div>
      </label>
      <div v-if="uvrMessage" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ uvrMessage }}</div>
      <label class="field">
        <span>从文件夹 ASR 生成数据集清单（faster-whisper small，本机）</span>
        <div class="row gap">
          <input v-model="audioDir" class="input" style="flex:1" placeholder="C:\audio\clips" />
          <button class="button ghost" :disabled="asrBusy || !audioDir.trim()" @click="runAsr">
            {{ asrBusy ? '转写中…' : 'ASR 生成清单' }}
          </button>
        </div>
      </label>
      <div v-if="asrMessage" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ asrMessage }}</div>
      <div class="row gap">
        <button class="button primary" :disabled="starting || !datasetList.trim()" @click="start">
          {{ starting ? '提交中…' : '开始训练' }}
        </button>
        <button class="button ghost" :disabled="qcBusy || !datasetList.trim()" @click="runQc">
          {{ qcBusy ? '检查中…' : '检查数据集' }}
        </button>
      </div>
      <div v-if="qc" class="job-block">
        <div class="row space-between">
          <strong>数据集检查</strong>
          <span class="tag" :class="qc.ok ? 'succeeded' : 'failed'">{{ qc.ok ? '通过' : '阻断' }}</span>
        </div>
        <div class="muted small">
          {{ qc.count }} 条 · {{ qc.total_duration.toFixed(1) }} 秒 · errors {{ qc.errors.length }} · blocking {{ qc.blocking.length }}
        </div>
        <div v-if="qc.blocking.length" class="inline-error">{{ qc.blocking.slice(0, 5).join('；') }}</div>
        <div class="table-wrap" style="max-height:220px">
          <table class="table">
            <thead><tr><th>#</th><th>时长</th><th>采样率</th><th>声道</th><th>静音</th><th>削波</th><th>问题</th></tr></thead>
            <tbody>
              <tr v-for="item in qc.items" :key="item.path">
                <td>{{ item.line }}</td>
                <td>{{ item.duration?.toFixed(2) ?? '—' }}</td>
                <td>{{ item.samplerate ?? '—' }}</td>
                <td>{{ item.channels ?? '—' }}</td>
                <td>{{ item.silence_ratio != null ? `${(item.silence_ratio * 100).toFixed(1)}%` : '—' }}</td>
                <td>{{ item.clipping_ratio != null ? `${(item.clipping_ratio * 100).toFixed(2)}%` : '—' }}</td>
                <td class="muted small">{{ item.issues.join(', ') || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="active" class="card">
      <div class="card-head">
        <div>
          <h2>{{ active.exp_name }}</h2>
          <p class="muted small">{{ active.id }} · {{ active.stage }} · {{ active.detail }}</p>
        </div>
        <span class="tag" :class="{ ok: active.status === 'succeeded', bad: active.status === 'failed' }">{{ active.status }}</span>
      </div>
      <div class="progress"><div class="progress-fill" :style="{ width: `${active.progress}%` }" /></div>
      <div class="row" style="justify-content:space-between">
        <span class="muted small">{{ active.progress }}%</span>
        <button v-if="busy" class="button danger small" @click="cancel">取消训练</button>
      </div>
      <div v-if="active.status === 'succeeded'" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">
        训练完成，音色已自动发布到 <RouterLink to="/voices">音色库</RouterLink>；可在工作台直接选用。
      </div>
      <div v-if="active.output_dir" class="muted small" style="margin-top:12px">
        输出：{{ active.output_dir }}<br />
        S1：{{ active.s1_model || '—' }}<br />
        S2：{{ active.s2_model || '—' }}
      </div>
      <details style="margin-top:12px">
        <summary class="muted small">训练日志</summary>
        <pre class="log">{{ log || '暂无日志' }}</pre>
      </details>
    </div>

    <div class="card">
      <div class="card-head"><h2>训练历史</h2></div>
      <table class="table">
        <thead><tr><th>实验</th><th>状态</th><th>阶段</th><th>进度</th><th>创建</th><th></th></tr></thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.exp_name }}</td>
            <td>{{ item.status }}</td>
            <td>{{ item.stage }}</td>
            <td>{{ item.progress }}%</td>
            <td class="muted small">{{ item.created_at.slice(0, 19).replace('T', ' ') }}</td>
            <td><button class="button ghost small" @click="pick(item)">查看</button></td>
          </tr>
          <tr v-if="!items.length"><td colspan="6" class="muted">还没有训练任务。</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
