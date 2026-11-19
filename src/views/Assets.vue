<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { AssetReport } from '../lib/engine'

const engine = useEngineStore()
const report = ref<AssetReport | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref('')
const sourcePath = ref('')
const message = ref('')

const missingNames = computed(() =>
  (report.value?.missing ?? []).map((id) => report.value?.items.find((item) => item.id === id)?.name ?? id),
)

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

async function load(verify = false) {
  if (!engine.client) return
  loading.value = true
  error.value = ''
  try {
    report.value = verify ? await engine.client.verifyAssets() : await engine.client.assets()
    if (!selected.value) selected.value = report.value.items[0]?.id ?? ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function importAsset() {
  if (!engine.client || !selected.value || !sourcePath.value.trim()) return
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const item = await engine.client.importAsset(selected.value, sourcePath.value.trim())
    message.value = `已导入 ${item.name}（${formatBytes(item.size)}）`
    await load(true)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void load()
  },
  { immediate: true },
)
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>模型资产</h2>
          <p class="muted small">
            路径以 GPT-SoVITS 引擎为根：pretrained_models、G2PWModel、uvr5_weights、asr/models。
          </p>
        </div>
        <div class="row gap">
          <button class="button ghost" :disabled="loading" @click="load(true)">重新校验</button>
        </div>
      </div>

      <div class="row gap">
        <span class="tag" :class="report?.ready ? 'pass' : 'warn'">
          {{ report?.ready ? '推理资产就绪' : '缺少必需资产' }}
        </span>
        <span class="tag">{{ report?.items.filter((i) => i.present).length ?? 0 }} / {{ report?.items.length ?? 0 }}</span>
        <span v-if="missingNames.length" class="muted small">缺少：{{ missingNames.join('、') }}</span>
      </div>

      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ message }}</div>

      <div class="table-wrap" style="margin-top:14px">
        <table class="table">
          <thead>
            <tr><th>资产</th><th>状态</th><th>路径</th><th>大小</th><th>说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in report?.items ?? []" :key="item.id">
              <td>{{ item.name }}<span v-if="item.required" class="muted tiny"> *</span></td>
              <td><span class="tag" :class="item.present ? 'pass' : item.required ? 'fail' : 'warn'">{{ item.present ? 'present' : 'missing' }}</span><span v-if="item.hash_ok === false" class="tag fail" style="margin-left:6px">hash</span></td>
              <td class="muted small ellipsis" style="max-width:420px">{{ item.path }}</td>
              <td class="muted small">{{ item.present ? formatBytes(item.size) : '—' }}</td>
              <td class="muted small">{{ item.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>离线导入</h2>
      <p class="muted small">选中资产，填入本地文件/目录路径；导入后自动校验。模型体积较大，建议放 C 盘。</p>
      <div class="form-grid">
        <label class="field">
          <span>资产</span>
          <select v-model="selected" class="input">
            <option v-for="item in report?.items ?? []" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label class="field" style="grid-column: span 2">
          <span>本地路径</span>
          <input v-model="sourcePath" class="input" placeholder="例如 C:\models\chinese-hubert-base" />
        </label>
      </div>
      <button class="button primary" :disabled="loading || !sourcePath.trim()" @click="importAsset">导入并校验</button>
    </div>
  </section>
</template>
