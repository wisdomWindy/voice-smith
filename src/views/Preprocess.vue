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
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    step.value = '人声分离（UVR5）'
    const uvr = await engine.client.uvr5(selected.value.rawAudio)
    step.value = '切片为 5–15 秒 48k 单声道'
    const sliced = await engine.client.sliceAudio(uvr.vocal_path)
    step.value = 'ASR 转写并生成训练清单'
    const asr = await engine.client.transcribeFolder(sliced.output_dir)
    updateDataset(selected.value.id, {
      status: 'preprocessed',
      listPath: asr.list_path,
      slicesDir: sliced.output_dir,
    })
    message.value = `预处理完成：${asr.count} 条，清单 ${asr.list_path}`
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
          <h2>预处理</h2>
          <p class="muted small">选择数据集，自动执行 V5 预处理：人声分离、切片、ASR、训练清单。</p>
        </div>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ message }}</div>
      <label class="field">
        <span>数据集</span>
        <select v-model="selectedId" class="input">
          <option v-for="item in visibleDatasets" :key="item.id" :value="item.id">
            {{ item.name }} · {{ item.status === 'raw' ? '待预处理' : '已预处理' }}
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
