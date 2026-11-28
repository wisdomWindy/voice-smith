<script setup lang="ts">
import { ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { DoctorCheck } from '../lib/engine'

const engine = useEngineStore()
const checks = ref<DoctorCheck[]>([])
const summary = ref<Record<string, number>>({})
const loading = ref(false)
const error = ref('')

async function run() {
  if (!engine.client) return
  loading.value = true
  error.value = ''
  try {
    const result = await engine.client.doctor()
    checks.value = result.checks
    summary.value = result.summary
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>检查项</h2>
          <p class="muted small">八项检查：Python、PyTorch、CUDA、GPU、ffmpeg、磁盘、文本前端、GPT/SoVITS/SV 权重。</p>
        </div>
        <button class="button primary" :disabled="!engine.ready || loading" @click="run">
          {{ loading ? '检查中…' : '运行 doctor' }}
        </button>
      </div>

      <div class="row gap">
        <span class="tag pass">pass {{ summary.pass ?? 0 }}</span>
        <span class="tag warn">warn {{ summary.warn ?? 0 }}</span>
        <span class="tag fail">fail {{ summary.fail ?? 0 }}</span>
      </div>

      <div v-if="error" class="inline-error">{{ error }}</div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr><th>检查</th><th>状态</th><th>详情</th><th>修复</th></tr>
          </thead>
          <tbody>
            <tr v-for="check in checks" :key="check.id">
              <td>{{ check.name }}</td>
              <td><span class="tag" :class="check.status">{{ check.status }}</span></td>
              <td>{{ check.detail }}</td>
              <td class="muted">{{ check.fix || '—' }}</td>
            </tr>
            <tr v-if="!checks.length">
              <td colspan="4" class="muted">尚未运行。M0 中 PyTorch/GPU 可能显示 fail，这是预期。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
