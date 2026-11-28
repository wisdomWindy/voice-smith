<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useEngineStore } from './stores/engine'
import { isTauri, platformTag } from './lib/engine'
import { APP_VERSION } from './lib/release'
import SetupDialog from './components/SetupDialog.vue'
import AppIcon from './components/AppIcon.vue'
import { startTaskWatcher } from './lib/taskWatcher'

const engine = useEngineStore()
const route = useRoute()
const platform = ref('windows-x64')
const booted = ref(false)
const setupOpen = ref(false)
const setupPending = ref(true)
const setupChecked = ref(false)
const runtimeInstalled = ref(false)
const showDonate = ref(false)
const donateTab = ref<'alipay' | 'wechat'>('alipay')

const NAV_ITEMS = [
  { to: '/projects', label: '项目', icon: 'projects', hint: '工作区' },
  { to: '/datasets', label: '数据集', icon: 'datasets', hint: '导入 / 切片' },
  { to: '/preprocess', label: '预处理', icon: 'preprocess', hint: '特征提取' },
  { to: '/training', label: '训练', icon: 'training', hint: '冒烟 / 长训' },
  { to: '/', label: '推理', icon: 'inference', hint: '试听 / 导出' },
  { to: '/tasks', label: '任务', icon: 'tasks', hint: '队列 / 日志' },
  { to: '/settings', label: '设置', icon: 'settings', hint: '环境 / 更新' },
]

const PIPELINE = [
  { to: '/projects', label: '项目' },
  { to: '/datasets', label: '数据集' },
  { to: '/preprocess', label: '预处理' },
  { to: '/training', label: '训练' },
  { to: '/', label: '推理' },
]

const shellVisible = computed(() => booted.value && (!setupOpen.value || runtimeInstalled.value))
const pageTitle = computed(() => String(route.meta.title ?? '配音工作台'))
const pageDesc = computed(() => String(route.meta.desc ?? 'GPT-SoVITS 本地配音工作流'))
const dataDir = computed(() => engine.health?.data_dir ?? '—')
const runtimeLine = computed(() =>
  engine.health ? `${engine.health.engine} · Python ${engine.health.python}` : '本地引擎',
)

function isNavActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  return route.path === to || route.path.startsWith(`${to}/`)
}

function isPipelineActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  return route.path === to || route.path.startsWith(`${to}/`)
}

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
  startTaskWatcher()
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
</script>

<template>
  <div v-if="shellVisible" class="shell">
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-mark" src="/app-icon.png" alt="VoiceSmith" draggable="false" />
        <div>
          <div class="brand-title">VoiceSmith</div>
          <div class="brand-sub">v{{ APP_VERSION }}</div>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <RouterLink v-for="item in NAV_ITEMS" :key="item.to" :to="item.to" class="nav-item" :class="{ 'nav-active': isNavActive(item.to) }">
          <AppIcon :name="item.icon" class="nav-icon" />
          <span class="nav-label">{{ item.label }}</span>
          <span class="nav-hint">{{ item.hint }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <button class="support-link" type="button" @click="showDonate = true">
          <AppIcon name="heart" style="width: 14px; height: 14px; color: var(--accent)" />
          <span>支持作者</span>
        </button>
        <div class="foot-status">
          <div class="engine-row">
            <span class="dot" :class="engine.status"></span>
            <span>{{ statusText }}</span>
          </div>
          <div class="foot-line ellipsis" :title="dataDir">数据目录：{{ dataDir }}</div>
          <div class="foot-line ellipsis" :title="runtimeLine">运行时：{{ runtimeLine }}</div>
          <button
            class="button ghost small foot-restart"
            :disabled="engine.status === 'starting'"
            @click="engine.restart()"
          >
            重启引擎
          </button>
        </div>
      </div>
    </aside>

    <div class="main">
      <div class="pipeline">
        <template v-for="(step, index) in PIPELINE" :key="step.to">
          <RouterLink :to="step.to" class="pipeline-step" :class="{ active: isPipelineActive(step.to) }">
            <span class="step-no">{{ index + 1 }}</span>
            <span>{{ step.label }}</span>
          </RouterLink>
          <span v-if="index < PIPELINE.length - 1" class="pipeline-sep">·</span>
        </template>
      </div>

      <div class="main-scroll">
        <header class="page-head">
          <div>
            <h1>{{ pageTitle }}</h1>
            <p>{{ pageDesc }}</p>
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
      </div>
    </div>
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
