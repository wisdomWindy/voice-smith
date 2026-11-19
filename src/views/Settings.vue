<script setup lang="ts">
import { ref } from 'vue'
import { useEngineStore } from '../stores/engine'

const engine = useEngineStore()
const exporting = ref(false)
const message = ref('')

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
        <span>遥测</span><strong>关闭</strong>
        <span>更新检查</span><strong>默认关闭</strong>
      </div>

      <div class="divider" />
      <p v-if="message" class="muted small">{{ message }}</p>
      <p class="muted small">
        安全边界：sidecar 只绑定 127.0.0.1，随机端口 + 每次启动 token；前端通过 Tauri
        获取端口/token，不落盘。
      </p>
    </div>
  </section>
</template>
