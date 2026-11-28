<script setup lang="ts">
import { computed, ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import { datasets, updateDataset } from '../lib/datasets'
import { selectedProject } from '../lib/projects'

const engine = useEngineStore()
const selectedId = ref(datasets.value[0]?.id || '')
const busy = ref(false)
const step = ref('')
const error = ref('')
const message = ref('')

const visibleDatasets = computed(() => datasets.value.filter((item) => item.projectId === selectedProject.value?.id))
const selected = computed(() => visibleDatasets.value.find((item) => item.id === selectedId.value))
const canRun = computed(() => Boolean(selected.value && engine.client && !busy.value))

async function run() {
  if (!engine.client || !selected.value) return
  if (!selected.value.rawAudios.length) {
    error.value = '数据集没有原始音频'
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    step.value = `UVR5 人声分离 · 切片 · ASR（${selected.value.rawAudios.length} 个音频）`
    const result = await engine.client.preprocessDataset(selected.value.rawAudios)
    updateDataset(selected.value.id, {
      status: 'preprocessed',
      listPath: result.list_path,
      slicesDir: result.slices_dir,
    })
    const skipped = result.skipped.length ? `，跳过 ${result.skipped.length} 个` : ''
    message.value = `预处理完成：${result.count} 条 · ${result.total_duration.toFixed(1)} 秒${skipped}`
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
    step.value = ''
  }
}

</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>预处理配置</h2>
          <p class="muted small">选择数据集，自动执行 V5 预处理：人声分离、切片、ASR、训练清单。</p>
        </div>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner success">{{ message }}</div>
      <label class="field">
        <span>数据集</span>
        <select v-model="selectedId" class="input">
          <option v-for="item in visibleDatasets" :key="item.id" :value="item.id">
            {{ item.name }} · {{ item.rawAudios.length }} 个音频 · {{ item.status === 'raw' ? '待预处理' : '已预处理' }}
          </option>
        </select>
      </label>
      <div v-if="busy" class="job-block">
        <div class="row space-between"><span>{{ step }}</span><strong>处理中</strong></div>
        <progress max="1" style="width:100%"></progress>
      </div>
      <button class="button primary" :disabled="!canRun" @click="run">{{ busy ? '预处理中…' : '开始预处理' }}</button>
    </div>
  </section>
</template>
