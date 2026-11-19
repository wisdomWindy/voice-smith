<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useEngineStore } from './stores/engine'
import type { AssetPackStatus } from './lib/engine'

const engine = useEngineStore()
const showTerms = ref(false)
const accepting = ref(false)
const showAssets = ref(false)
const pack = ref<AssetPackStatus | null>(null)
const packUrl = ref('')
const packBusy = ref(false)
let packTimer: number | undefined
const showRuntime = ref(false)
const runtimeUrl = ref('')
const runtimeSha = ref('')
const runtimeBusy = ref(false)
const runtimeError = ref('')

async function installRuntimePack() {
  if (!runtimeUrl.value.trim()) return
  runtimeBusy.value = true
  runtimeError.value = ''
  try {
    const ok = await engine.installRuntimePack(runtimeUrl.value.trim(), runtimeSha.value.trim())
    if (ok) {
      showRuntime.value = false
      await checkAssets()
    } else {
      runtimeError.value = engine.error || '运行时安装失败'
    }
  } finally {
    runtimeBusy.value = false
  }
}

async function checkAssets() {
  if (!engine.client || engine.status !== 'ready') return
  try {
    const report = await engine.client.assets()
    const state = await engine.client.assetPack()
    pack.value = state
    if (!packUrl.value && state.url) packUrl.value = state.url
    showAssets.value = !report.ready && !state.installed
  } catch {
    showAssets.value = false
  }
}

async function startPack() {
  if (!engine.client || !packUrl.value.trim()) return
  packBusy.value = true
  try {
    pack.value = await engine.client.installAssetPack(packUrl.value.trim())
    window.clearInterval(packTimer)
    packTimer = window.setInterval(async () => {
      if (!engine.client) return
      const state = await engine.client.assetPack()
      pack.value = state
      if (!state.installing) {
        window.clearInterval(packTimer)
        packBusy.value = false
        if (state.installed) {
          showAssets.value = false
          await engine.restart()
        }
      }
    }, 2000)
  } catch {
    packBusy.value = false
  }
}

watch(
  () => engine.status,
  async (status) => {
    if (status === 'runtime_missing') {
      showRuntime.value = true
      showAssets.value = false
      return
    }
    if (status !== 'ready' || !engine.client) return
    showRuntime.value = false
    try {
      showTerms.value = !(await engine.client.terms())
    } catch {
      showTerms.value = false
    }
    if (!showTerms.value) await checkAssets()
  },
  { immediate: true },
)

onUnmounted(() => window.clearInterval(packTimer))

async function acceptTerms() {
  if (!engine.client) return
  accepting.value = true
  try {
    await engine.client.acceptTerms()
    showTerms.value = false
    await checkAssets()
  } finally {
    accepting.value = false
  }
}

onMounted(() => {
  if (engine.status === 'starting' && !engine.info) void engine.init()
})

const statusText = computed(() => {
  if (engine.status === 'ready') return '引擎就绪'
  if (engine.status === 'error') return '引擎异常'
  return '引擎启动中'
})

const statusDetail = computed(() => {
  if (engine.status === 'ready') {
    return engine.health ? `${engine.health.engine} · Python ${engine.health.python}` : '本地引擎'
  }
  if (engine.status === 'error') return engine.error || 'sidecar 未启动'
  return '正在连接本地 sidecar…'
})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">VS</div>
        <div>
          <div class="brand-title">VoiceSmith</div>
          <div class="brand-sub">GPT-SoVITS 桌面工坊</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink to="/" class="nav-item">工作台</RouterLink>
        <RouterLink to="/doctor" class="nav-item">环境自检</RouterLink>
        <RouterLink to="/voices" class="nav-item">音色库</RouterLink>
        <RouterLink to="/training" class="nav-item">训练</RouterLink>
        <RouterLink to="/history" class="nav-item">历史</RouterLink>
        <RouterLink to="/models" class="nav-item">模型</RouterLink>
        <RouterLink to="/assets" class="nav-item">模型资产</RouterLink>
        <RouterLink to="/settings" class="nav-item">设置</RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="engine-card">
          <div class="engine-row">
            <span class="dot" :class="engine.status"></span>
            <span>{{ statusText }}</span>
          </div>
          <p class="muted small">{{ statusDetail }}</p>
          <button class="button ghost small" :disabled="engine.status === 'starting'" @click="engine.restart()">
            重启引擎
          </button>
        </div>
        <div class="muted tiny">v0.1.0 · 本地优先 · 零遥测</div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h1>配音工作台</h1>
          <p class="muted small">文本 → 音色 → 参数 → 试听 → 导出</p>
        </div>
        <div class="status-pill" :class="engine.status">
          <span class="dot" :class="engine.status"></span>
          {{ statusText }}
        </div>
      </header>

      <div v-if="engine.error" class="banner">
        <strong>引擎未就绪：</strong>{{ engine.error }}
        <button class="button ghost small" @click="engine.restart()">重试</button>
      </div>

      <RouterView />
    </main>
  </div>

  <div v-if="showRuntime" class="modal-mask">
    <div class="modal">
      <h2>安装运行时</h2>
      <p class="muted">
        首次使用需要下载 VoiceSmith 运行时（Python + PyTorch/CUDA，约 2–3GB 压缩包）。安装后还需下载离线资产包。
      </p>
      <label class="field">
        <span>运行时包地址</span>
        <input v-model="runtimeUrl" class="input" placeholder="https://github.com/wisdomWindy/voice-smith/releases/download/v0.1.0/VoiceSmith-Runtime.7z" />
      </label>
      <label class="field">
        <span>SHA256（可选）</span>
        <input v-model="runtimeSha" class="input" placeholder="运行时包 sha256" />
      </label>
      <div v-if="runtimeError" class="inline-error">{{ runtimeError }}</div>
      <button class="button primary" :disabled="runtimeBusy || !runtimeUrl.trim()" @click="installRuntimePack">
        {{ runtimeBusy ? '下载安装中…' : '下载并安装运行时' }}
      </button>
    </div>
  </div>

  <div v-if="showTerms" class="modal-mask">
    <div class="modal">
      <h2>使用规约</h2>
      <p class="muted">
        VoiceSmith 是本地 TTS 工具。你对生成的音频用途负责；禁止伪造他人声音、诈骗、侵权或违法用途。
      </p>
      <ul class="muted small">
        <li>音频、模型、日志只保存在本机；默认零遥测。</li>
        <li>模型权重与训练数据由你自行提供，需确保授权合法。</li>
        <li>本软件不提供内容审核或授权审核。</li>
      </ul>
      <button class="button primary" :disabled="accepting" @click="acceptTerms">
        {{ accepting ? '保存中…' : '同意并继续' }}
      </button>
    </div>
  </div>

  <div v-if="showAssets && !showTerms" class="modal-mask">
    <div class="modal">
      <h2>安装离线资产</h2>
      <p class="muted">
        首次使用需要 GPT-SoVITS 引擎、编码器、声码器与预训练权重。下载离线资产包后会自动校验 sha256 并安装。
      </p>
      <label class="field">
        <span>资产包地址</span>
        <input v-model="packUrl" class="input" placeholder="https://github.com/wisdomWindy/voice-smith/releases/download/v0.1.0/VoiceSmith-Offline-Assets.7z" />
      </label>
      <div v-if="pack && pack.installing" class="job-block">
        <div class="row space-between">
          <span>{{ pack.message || pack.stage }}</span>
          <strong>{{ Math.round(pack.progress * 100) }}%</strong>
        </div>
        <progress :value="pack.progress" max="1" style="width:100%"></progress>
      </div>
      <div v-if="pack?.error" class="inline-error">{{ pack.error }}</div>
      <div class="row gap">
        <button class="button primary" :disabled="packBusy || !packUrl.trim()" @click="startPack">
          {{ packBusy ? (pack?.installing ? '安装中…' : '启动中…') : '下载并安装离线资产' }}
        </button>
        <button class="button ghost" :disabled="packBusy" @click="showAssets = false">稍后</button>
      </div>
    </div>
  </div>
</template>
