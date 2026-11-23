<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import { checkForUpdate, installUpdate, openReleasePage } from '../lib/updater'

const engine = useEngineStore()
const exporting = ref(false)
const message = ref('')
const updateMessage = ref('')
const updateVersion = ref('')
const updateAvailable = ref(false)
const updateUrl = ref('')
const updating = ref(false)
const updateProgress = ref(0)

async function checkUpdate() {
  updateMessage.value = '检查中…'
  try {
    const result = await checkForUpdate()
    updateAvailable.value = result.available
    updateVersion.value = result.version ?? ''
    updateUrl.value = result.downloadUrl ?? ''
    updateMessage.value = result.message
  } catch (err) {
    updateMessage.value = err instanceof Error ? err.message : String(err)
  }
}

async function install() {
  if (updateUrl.value) {
    try {
      await openReleasePage(updateUrl.value)
      updateMessage.value = '已打开发布页，请下载对应安装包'
    } catch (err) {
      updateMessage.value = err instanceof Error ? err.message : String(err)
    }
    return
  }
  updating.value = true
  updateProgress.value = 0
  updateMessage.value = '下载中…'
  try {
    await installUpdate((percent) => {
      updateProgress.value = percent
      updateMessage.value = `下载中 ${percent}%`
    })
    updateMessage.value = '安装完成，正在重启…'
  } catch (err) {
    updateMessage.value = err instanceof Error ? err.message : String(err)
    updating.value = false
  }
}

onMounted(() => {
  void checkUpdate()
})

async function exportDiagnostics() {
  if (!engine.client) return
  exporting.value = true
  message.value = ''
  try {
    const blob = await engine.client.diagnostics()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'voicesmith-diagnostics.zip'
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    message.value = '诊断包已导出（不含音频/模型）。'
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>设置</h2>
          <p class="muted small">M0 只读展示引擎信息；数据目录、更新检查与模型资产在后续迭代。</p>
        </div>
        <button class="button ghost" :disabled="updating" @click="checkUpdate">
          {{ updating ? '检查中…' : '检查更新' }}
        </button>
        <button class="button ghost" :disabled="exporting" @click="exportDiagnostics">
          {{ exporting ? '导出中…' : '导出诊断包' }}
        </button>
        <button class="button ghost" :disabled="engine.status === 'starting'" @click="engine.restart()">
          重启引擎
        </button>
      </div>

      <div class="kv wide">
        <span>引擎状态</span><strong>{{ engine.status }}</strong>
        <span>引擎版本</span><strong>{{ engine.health?.version ?? '—' }}</strong>
        <span>引擎模式</span><strong>{{ engine.health?.engine ?? '—' }}</strong>
        <span>Python</span><strong>{{ engine.health?.python ?? '—' }}</strong>
        <span>数据目录</span><strong class="ellipsis">{{ engine.health?.data_dir ?? '—' }}</strong>
        <span>更新检查</span><strong>{{ updateMessage || '自动检查' }}</strong>
      </div>

      <div v-if="updateAvailable" class="row gap" style="margin-top:12px">
        <button class="button primary" :disabled="updating" @click="install">
          {{ updating ? `更新中 ${updateProgress}%` : updateUrl ? `前往下载 ${updateVersion}` : `安装 ${updateVersion}` }}
        </button>
      </div>
      <progress v-if="updating" :value="updateProgress" max="100" style="width:100%;margin-top:8px"></progress>

      <div class="divider" />
      <p v-if="message" class="muted small">{{ message }}</p>
      <p class="muted small">
        安全边界：sidecar 只绑定 127.0.0.1，随机端口 + 每次启动 token；前端通过 Tauri
        获取端口/token，不落盘。
      </p>
    </div>
  </section>
</template>
