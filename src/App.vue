<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useEngineStore } from './stores/engine'
import type { AssetPackStatus } from './lib/engine'
import { platformTag } from './lib/engine'
import { APP_VERSION, assetsManifest, runtimeManifest } from './lib/release'

const engine = useEngineStore()
const platform = ref('windows-x64')
const showTerms = ref(false)
const accepting = ref(false)
const showAssets = ref(false)
const pack = ref<AssetPackStatus | null>(null)
const packBusy = ref(false)
let packTimer: number | undefined
const showRuntime = ref(true)
const showDonate = ref(false)
const donateTab = ref<'alipay' | 'wechat'>('alipay')
const runtimeChecking = ref(true)
const runtimeBusy = ref(false)
const runtimeError = ref('')
const runtimeProgress = ref(0)
const runtimeStage = ref('')
let runtimeUnlisten: (() => void) | undefined

async function installRuntimePack() {
  runtimeBusy.value = true
  runtimeError.value = ''
  runtimeProgress.value = 0
  runtimeStage.value = '准备下载'
  try {
    const ok = await engine.installRuntimePack(runtimeManifest(platform.value))
    if (ok) {
      runtimeProgress.value = 100
      runtimeStage.value = '安装完成'
      runtimeChecking.value = false
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
    showAssets.value = !report.ready && !state.installed
  } catch {
    showAssets.value = false
  }
}

async function startPack() {
  if (!engine.client) return
  packBusy.value = true
  try {
    pack.value = await engine.client.installAssetPack(assetsManifest(platform.value))
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
      runtimeChecking.value = false
      showAssets.value = false
      return
    }
    if (status === 'error' && !engine.info) {
      showRuntime.value = true
      runtimeChecking.value = false
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
onUnmounted(() => runtimeUnlisten?.())

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

onMounted(async () => {
  try {
    const { listen } = await import('@tauri-apps/api/event')
    runtimeUnlisten = await listen<{ percent: number; stage: string }>('runtime-progress', (event) => {
      runtimeProgress.value = Math.max(0, Math.min(100, event.payload.percent))
      runtimeStage.value = event.payload.stage
    })
  } catch {
    // Browser preview has no Tauri event bridge.
  }
  try {
    platform.value = await platformTag()
  } catch {
    platform.value = 'windows-x64'
  }
  try {
    const state = await engine.runtime()
    runtimeChecking.value = false
    if (!state.installed) {
      showRuntime.value = true
      return
    }
    showRuntime.value = false
  } catch {
    runtimeChecking.value = false
    showRuntime.value = true
    return
  }
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
  <div v-if="!showRuntime" class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">VS</div>
        <div>
          <div class="brand-title">VoiceSmith</div>
          <div class="brand-sub">GPT-SoVITS 桌面工坊</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink to="/projects" class="nav-item">项目</RouterLink>
        <RouterLink to="/datasets" class="nav-item">数据集</RouterLink>
        <RouterLink to="/preprocess" class="nav-item">预处理</RouterLink>
        <RouterLink to="/training" class="nav-item">训练</RouterLink>
        <RouterLink to="/" class="nav-item">推理</RouterLink>
        <RouterLink to="/tasks" class="nav-item">任务</RouterLink>
      </nav>

      <div class="sidebar-foot">
        <button class="button ghost small" style="width:100%;margin-bottom:8px" @click="showDonate = true">
          支持 VoiceSmith
        </button>
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
        <RouterLink to="/settings" class="nav-item" style="margin-bottom:8px">设置</RouterLink>
        <div class="muted tiny">v{{ APP_VERSION }} · 本地优先 · 数据不出机</div>
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

  <div v-if="showDonate" class="modal-mask" @click.self="showDonate = false">
    <div class="modal">
      <h2>支持 VoiceSmith</h2>
      <p class="muted small">如果这个工具帮到了你，可以扫码请作者喝杯咖啡。捐赠完全自愿，不影响任何功能。</p>
      <div class="row gap" style="margin:10px 0">
        <button class="button" :class="donateTab === 'alipay' ? 'primary' : 'ghost'" @click="donateTab = 'alipay'">支付宝</button>
        <button class="button" :class="donateTab === 'wechat' ? 'primary' : 'ghost'" @click="donateTab = 'wechat'">微信支付</button>
      </div>
      <div style="text-align:center">
        <img
          v-if="donateTab === 'alipay'"
          src="/donate/alipay.jpg"
          alt="支付宝收款码"
          style="max-width:300px;width:100%;border-radius:12px;background:#fff;padding:8px"
        />
        <img
          v-else
          src="/donate/wechat.png"
          alt="微信支付收款码"
          style="max-width:300px;width:100%;border-radius:12px;background:#fff;padding:8px"
        />
      </div>
      <button class="button ghost" style="margin-top:12px" @click="showDonate = false">关闭</button>
    </div>
  </div>

  <div v-if="showRuntime" class="modal-mask">
    <div class="modal">
      <h2>安装运行时</h2>
      <p class="muted">
        首次使用需要下载 VoiceSmith 运行时（Python + PyTorch/CUDA，约 2–3GB 压缩包）。安装后还需下载离线资产包。
      </p>
      <p v-if="runtimeChecking" class="muted">Checking runtime...</p>
      <div v-if="runtimeBusy" class="job-block">
        <div class="row space-between">
          <span>{{ runtimeStage || '下载安装中…' }}</span>
          <strong>{{ runtimeProgress }}%</strong>
        </div>
        <progress :value="runtimeProgress" max="100" style="width:100%"></progress>
      </div>
      <div v-if="runtimeError" class="inline-error">{{ runtimeError }}</div>
      <button v-if="!runtimeChecking" class="button primary" :disabled="runtimeBusy" @click="installRuntimePack">
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
        <li>音频、模型、日志只保存在本机，数据不出机。</li>
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
      <p class="muted small">下载地址固定，无需填写。</p>
      <div v-if="pack && pack.installing" class="job-block">
        <div class="row space-between">
          <span>{{ pack.message || pack.stage }}</span>
          <strong>{{ Math.round(pack.progress * 100) }}%</strong>
        </div>
        <progress :value="pack.progress" max="1" style="width:100%"></progress>
      </div>
      <div v-if="pack?.error" class="inline-error">{{ pack.error }}</div>
      <div class="row gap">
        <button class="button primary" :disabled="packBusy" @click="startPack">
          {{ packBusy ? (pack?.installing ? '安装中…' : '启动中…') : '下载并安装离线资产' }}
        </button>
        <button class="button ghost" :disabled="packBusy" @click="showAssets = false">稍后</button>
      </div>
    </div>
  </div>
</template>

