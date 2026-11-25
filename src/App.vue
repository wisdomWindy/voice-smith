<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useEngineStore } from './stores/engine'
import { isTauri, platformTag } from './lib/engine'
import { APP_VERSION } from './lib/release'
import SetupDialog from './components/SetupDialog.vue'

const engine = useEngineStore()
const platform = ref('windows-x64')
const booted = ref(false)
const setupOpen = ref(false)
const setupPending = ref(true)
const setupChecked = ref(false)
const runtimeInstalled = ref(false)
const showDonate = ref(false)
const donateTab = ref<'alipay' | 'wechat'>('alipay')

const shellVisible = computed(() => booted.value && (!setupOpen.value || runtimeInstalled.value))

async function checkSetup() {
  try {
    if (!engine.client || engine.status !== 'ready') {
      setupPending.value = true
      setupOpen.value = true
      return
    }
    const [termsOk, report, pack] = await Promise.all([
      engine.client.terms(),
      engine.client.assets(),
      engine.client.assetPack(),
    ])
    setupPending.value = !(termsOk && (report.ready || pack.installed))
    setupOpen.value = setupPending.value
  } catch {
    setupPending.value = true
    setupOpen.value = true
  } finally {
    setupChecked.value = true
  }
}

function openSetup() {
  setupOpen.value = true
}

function onSetupDone() {
  setupOpen.value = false
  setupPending.value = false
  setupChecked.value = true
  runtimeInstalled.value = true
}

function onSetupClose() {
  setupOpen.value = false
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'runtime_missing') {
      runtimeInstalled.value = false
      setupPending.value = true
      setupOpen.value = true
    }
  },
)

onMounted(async () => {
  try {
    platform.value = await platformTag()
  } catch {
    platform.value = 'windows-x64'
  }
  try {
    runtimeInstalled.value = (await engine.runtime()).installed
  } catch {
    runtimeInstalled.value = false
  }
  booted.value = true
  if (!isTauri()) {
    // Browser preview talks to a dev sidecar; there is nothing to install here.
    setupPending.value = false
    setupChecked.value = true
    void engine.init()
    return
  }
  if (!runtimeInstalled.value) {
    setupOpen.value = true
    return
  }
  await engine.init()
  await checkSetup()
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
  <div v-if="shellVisible" class="shell">
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
        <RouterLink to="/settings" class="nav-item">设置</RouterLink>
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

      <div v-if="setupChecked && setupPending && !setupOpen" class="notice">
        <span><strong>首次设置未完成：</strong>离线资产（模型权重）或使用规约还未确认，推理与训练暂不可用。</span>
        <button class="button ghost small" @click="openSetup">继续安装</button>
      </div>

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

  <SetupDialog :open="setupOpen" :platform="platform" @done="onSetupDone" @close="onSetupClose" />
</template>
