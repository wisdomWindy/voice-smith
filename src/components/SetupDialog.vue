<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { AssetPackStatus } from '../lib/engine'
import { assetsManifest, runtimeManifest } from '../lib/release'

/**
 * One dialog for everything the app needs on first launch: the Python runtime,
 * the offline asset pack (model weights + tools) and the usage terms. A single
 * confirmation installs them in order; the dialog only asks again after a
 * failure or when the user chooses to install later.
 */

type Phase = 'checking' | 'confirm' | 'running' | 'error' | 'done'
type StepKey = 'runtime' | 'assets' | 'terms'
type Tone = '' | 'pass' | 'warn' | 'fail'

type Row = {
  key: StepKey
  title: string
  detail: string
  size: string
  status: string
  tone: Tone
}

const props = defineProps<{ open: boolean; platform: string }>()
const emit = defineEmits<{ done: []; close: [] }>()

const engine = useEngineStore()

const phase = ref<Phase>('checking')
const runtimeInstalled = ref(false)
const termsAccepted = ref(false)
const assetsReady = ref(false)
const forceRuntime = ref(false)
const overall = ref(0)
const stage = ref('')
const error = ref('')
const pack = ref<AssetPackStatus | null>(null)
const runtimePercent = ref(0)
const activeStep = ref<StepKey | ''>('')
let unlisten: (() => void) | undefined

const COMPONENT_LABELS: Record<string, string> = {
  base: '基础运行时',
  core: '核心依赖',
  torch: 'PyTorch 依赖',
}

const PACK_STAGE_LABELS: Record<string, string> = {
  queued: '排队中',
  downloading: '下载离线资产',
  verifying: '校验 sha256',
  extracting: '解压离线资产',
  installing: '安装模型权重与工具',
  done: '离线资产安装完成',
  failed: '离线资产安装失败',
}

const sleeping = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const platform = computed(() => props.platform || 'windows-x64')
const running = computed(() => phase.value === 'running')
const needsRuntime = computed(() => forceRuntime.value || !runtimeInstalled.value)
const needsAssets = computed(() => !assetsReady.value)
const needsTerms = computed(() => !termsAccepted.value)
const canDefer = computed(() => runtimeInstalled.value && !running.value)

const runtimeState = computed<'done' | 'active' | 'todo' | 'failed'>(() => {
  if (!needsRuntime.value) return 'done'
  if (running.value && activeStep.value === 'runtime') return 'active'
  if (phase.value === 'error' && activeStep.value === 'runtime') return 'failed'
  return 'todo'
})

const assetsState = computed<'done' | 'active' | 'todo' | 'failed'>(() => {
  if (!needsAssets.value) return 'done'
  if (running.value && activeStep.value === 'assets') return 'active'
  if (phase.value === 'error' && activeStep.value === 'assets') return 'failed'
  return 'todo'
})

const termsState = computed<'done' | 'todo'>(() => (termsAccepted.value ? 'done' : 'todo'))

function rowStatus(state: 'done' | 'active' | 'todo' | 'failed', doneText: string, todoText: string): { status: string; tone: Tone } {
  if (state === 'done') return { status: doneText, tone: 'pass' }
  if (state === 'failed') return { status: '失败', tone: 'fail' }
  if (state === 'active') {
    const percent = activeStep.value === 'runtime' ? Math.round(runtimePercent.value) : Math.round((pack.value?.progress ?? 0) * 100)
    return { status: `${percent}%`, tone: 'warn' }
  }
  return { status: todoText, tone: '' }
}

const rows = computed<Row[]>(() => {
  const runtime = rowStatus(runtimeState.value, '已安装', '待安装')
  const assets = rowStatus(assetsState.value, '已安装', '待安装')
  const terms = rowStatus(termsState.value, '已同意', '随本次安装同意')
  return [
    {
      key: 'runtime',
      title: '运行时',
      detail: '嵌入式 Python 3.11 + PyTorch/CUDA 依赖',
      size: '约 3.4 GB',
      status: runtime.status,
      tone: runtime.tone,
    },
    {
      key: 'assets',
      title: '离线资产包（模型与工具）',
      detail: 'GPT-SoVITS 模型权重、编码器/声码器、ASR 与 UVR5 工具',
      size: '约 5.5 GB',
      status: assets.status,
      tone: assets.tone,
    },
    {
      key: 'terms',
      title: '使用规约',
      detail: '一次同意，之后不再单独弹窗',
      size: '',
      status: terms.status,
      tone: terms.tone,
    },
  ]
})

const totalSize = computed(() => {
  if (needsRuntime.value && needsAssets.value) return '约 8.9 GB'
  if (needsRuntime.value) return '约 3.4 GB'
  if (needsAssets.value) return '约 5.5 GB'
  return ''
})

const showTerms = computed(() => !termsAccepted.value && phase.value !== 'checking')

const primaryLabel = computed(() => {
  if (phase.value === 'checking') return '检查本机环境…'
  if (running.value) return '安装中…'
  if (phase.value === 'error') return '重试'
  if (!needsRuntime.value && !needsAssets.value && !needsTerms.value) return '完成'
  return needsTerms.value ? '同意并一键安装' : '一键安装'
})

function translateRuntimeStage(raw: string): string {
  if (!raw) return ''
  if (raw.startsWith('Preparing')) return '准备安装运行时'
  if (raw.startsWith('Reading')) return '读取运行时清单'
  if (raw.startsWith('Downloading')) {
    const name = /Downloading\s+(\S+)/i.exec(raw)?.[1]?.toLowerCase() ?? ''
    const part = /\((\d+)\/(\d+)\)/.exec(raw)
    const label = COMPONENT_LABELS[name]
    if (label) return part ? `下载${label}（${part[1]}/${part[2]}）` : `下载${label}`
    return '下载运行时组件'
  }
  if (raw.startsWith('Verifying')) return '校验下载文件 sha256'
  if (raw.startsWith('Installing runtime base')) return '解压 Python 运行时'
  if (raw.startsWith('Installing core')) return '解压核心依赖'
  if (raw.startsWith('Installing torch')) return '解压 PyTorch 依赖'
  if (raw.startsWith('Installing Python')) return '离线安装 Python 依赖（约数分钟）'
  if (raw.startsWith('Starting engine')) return '启动本地引擎'
  if (raw.startsWith('Runtime installed')) return '运行时安装完成'
  return raw
}

function translatePackStage(state: AssetPackStatus): string {
  return state.message || PACK_STAGE_LABELS[state.stage] || state.stage || ''
}

function currentClient() {
  if (!engine.client) throw new Error('引擎未就绪，请重试')
  return engine.client
}

async function ensureEngine(): Promise<void> {
  if (engine.client && engine.status === 'ready') return
  if (engine.status === 'error') {
    // The sidecar exited (or a previous install failed); restart before retrying.
    await engine.restart()
  } else if (!engine.client) {
    await engine.init()
  }
  const started = Date.now()
  while (!engine.client || engine.status !== 'ready') {
    if (engine.status === 'error') throw new Error(engine.error || '引擎启动失败，请重试')
    if (engine.status === 'runtime_missing') throw new Error('运行时未安装完成，请重新安装')
    if (Date.now() - started > 180_000) throw new Error('引擎启动超时，请重试')
    await sleeping(400)
  }
}

async function check(): Promise<void> {
  phase.value = 'checking'
  error.value = ''
  stage.value = '正在检查本机环境'
  activeStep.value = ''
  overall.value = 0
  forceRuntime.value = false
  try {
    runtimeInstalled.value = (await engine.runtime()).installed
  } catch {
    runtimeInstalled.value = false
  }
  if (!runtimeInstalled.value) {
    termsAccepted.value = false
    assetsReady.value = false
    phase.value = 'confirm'
    return
  }
  try {
    await ensureEngine()
    const client = currentClient()
    try {
      termsAccepted.value = await client.terms()
    } catch {
      termsAccepted.value = false
    }
    try {
      const [report, state] = await Promise.all([client.assets(), client.assetPack()])
      pack.value = state
      assetsReady.value = report.ready || state.installed
    } catch {
      assetsReady.value = false
    }
  } catch (err) {
    phase.value = 'error'
    error.value = err instanceof Error ? err.message : String(err)
    return
  }
  phase.value = 'confirm'
  if (!needsRuntime.value && !needsAssets.value && !needsTerms.value) emit('done')
}

async function waitForPack(started: boolean): Promise<void> {
  for (let attempt = 0; attempt < 3600; attempt += 1) {
    await sleeping(2000)
    const state = await currentClient().assetPack()
    pack.value = state
    if (state.installing) {
      started = true
      continue
    }
    if (state.error) throw new Error(state.error)
    if (state.installed) return
    // The worker thread may need a moment to report `installing`; don't treat
    // that first poll as a failure.
    if (!started && attempt < 3) continue
    throw new Error(state.message || '离线资产未安装完成')
  }
  throw new Error('离线资产安装超时（2 小时），重试可断点续传')
}

async function start(): Promise<void> {
  if (running.value) return
  if (!needsRuntime.value && !needsAssets.value && !needsTerms.value) {
    emit('done')
    return
  }
  error.value = ''
  phase.value = 'running'
  overall.value = 0
  stage.value = '准备安装'
  activeStep.value = ''
  try {
    if (needsRuntime.value) {
      activeStep.value = 'runtime'
      runtimePercent.value = 0
      stage.value = '准备下载运行时'
      const ok = await engine.installRuntimePack(runtimeManifest(platform.value))
      if (!ok) throw new Error(engine.error || '运行时安装失败')
      runtimeInstalled.value = true
      forceRuntime.value = false
      overall.value = Math.max(overall.value, 40)
    }
    await ensureEngine()
    const client = currentClient()
    if (needsTerms.value) {
      activeStep.value = 'terms'
      stage.value = '记录使用规约'
      await client.acceptTerms()
      termsAccepted.value = true
      activeStep.value = ''
      overall.value = Math.max(overall.value, 44)
    }
    if (needsAssets.value) {
      activeStep.value = 'assets'
      stage.value = '启动离线资产下载'
      const initial = await client.installAssetPack(assetsManifest(platform.value))
      pack.value = initial
      await waitForPack(initial.installing)
      assetsReady.value = true
      stage.value = '重启引擎并挂载模型'
      overall.value = Math.max(overall.value, 94)
      await engine.restart()
      if (engine.status !== 'ready') throw new Error(engine.error || '引擎重启失败')
    }
    activeStep.value = ''
    overall.value = 100
    stage.value = '安装完成'
    phase.value = 'done'
    emit('done')
  } catch (err) {
    phase.value = 'error'
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function defer(): void {
  if (!canDefer.value || running.value) return
  emit('close')
}

function reinstallRuntime(): void {
  if (running.value) return
  forceRuntime.value = true
  void start()
}

watch(
  () => props.open,
  (open) => {
    if (open) void check()
  },
)

watch(pack, (state) => {
  if (!state || activeStep.value !== 'assets') return
  overall.value = Math.max(overall.value, 44 + Math.min(1, state.progress) * 50)
  stage.value = translatePackStage(state) || stage.value
})

onMounted(async () => {
  if (props.open) void check()
  try {
    const { listen } = await import('@tauri-apps/api/event')
    unlisten = await listen<{ percent: number; stage: string }>('runtime-progress', (event) => {
      runtimePercent.value = Math.max(0, Math.min(100, event.payload.percent))
      if (activeStep.value !== 'runtime') return
      overall.value = Math.max(overall.value, runtimePercent.value * 0.4)
      stage.value = translateRuntimeStage(event.payload.stage) || stage.value
    })
  } catch {
    // Browser preview has no Tauri event bridge.
  }
})

onBeforeUnmount(() => unlisten?.())
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-mask">
      <div class="modal setup-modal" role="dialog" aria-modal="true" aria-label="首次设置">
        <h2>首次设置</h2>
        <p class="muted small">
          运行时、离线资产包、模型权重和使用规约都在这一个窗口确认。点一次按钮后按顺序自动安装，中途不需要再次点击。
        </p>

        <ul class="setup-steps">
          <li v-for="row in rows" :key="row.key" class="setup-step">
            <div class="setup-step-main">
              <div class="setup-step-title">
                {{ row.title }}
                <span v-if="row.size" class="muted tiny">{{ row.size }}</span>
              </div>
              <div class="muted tiny">{{ row.detail }}</div>
            </div>
            <span class="tag" :class="row.tone">{{ row.status }}</span>
          </li>
        </ul>

        <div v-if="showTerms" class="setup-terms">
          <div class="setup-terms-title">使用规约（点击下方安装按钮即表示同意）</div>
          <ul class="muted tiny">
            <li>生成的音频仅用于合法用途；禁止伪造他人声音、诈骗、侵权或违法用途。</li>
            <li>音频、模型与日志只保存在本机，数据不出机。</li>
            <li>模型权重与训练数据由你自行提供，需确保授权合法；本软件不做内容审核。</li>
          </ul>
        </div>

        <div v-if="running || phase === 'done' || (phase === 'error' && overall > 0)" class="job-block">
          <div class="row space-between">
            <span>{{ stage || '准备中…' }}</span>
            <strong>{{ Math.round(overall) }}%</strong>
          </div>
          <progress :value="overall" max="100" style="width:100%"></progress>
        </div>

        <div v-if="error" class="inline-error">{{ error }}</div>

        <p v-if="!running && totalSize" class="muted tiny">
          本次需下载 {{ totalSize }}；安装后约占用 9 GB，建议预留 15 GB 以上磁盘空间。
        </p>

        <div class="row gap">
          <button class="button primary" :disabled="running || phase === 'checking'" @click="start">
            {{ primaryLabel }}
          </button>
          <button v-if="canDefer" class="button ghost" :disabled="running" @click="defer">稍后安装</button>
          <button
            v-if="phase === 'error' && runtimeInstalled"
            class="button ghost"
            :disabled="running"
            @click="reinstallRuntime"
          >
            重新安装运行时
          </button>
        </div>
        <p v-if="canDefer" class="muted tiny">选择「稍后安装」后，可随时点主界面顶部的「继续安装」回到这里。</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.setup-modal {
  width: min(600px, 100%);
}
.setup-steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}
.setup-step {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 9px;
  background: #0f141d;
}
.setup-step-main {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.setup-step-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}
.setup-terms {
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 9px;
  background: #0f141d;
  display: grid;
  gap: 6px;
}
.setup-terms-title {
  font-size: 12px;
  font-weight: 600;
}
.setup-terms ul {
  margin: 0;
  padding-left: 16px;
  display: grid;
  gap: 4px;
  line-height: 1.6;
}
</style>
