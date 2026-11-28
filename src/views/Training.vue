<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { Training } from '../lib/engine'
import { datasets } from '../lib/datasets'
import { selectedProject } from '../lib/projects'

const engine = useEngineStore()
const items = ref<Training[]>([])
const error = ref('')
const starting = ref(false)
const cancelling = ref(false)
const selectedDatasetId = ref('')
const expName = ref('my_voice')
const s1Epochs = ref(5)
const s2Epochs = ref(2)
const batchSize = ref(2)
const dataWorkers = ref(2)
const force = ref(false)
let timer: number | undefined

const readyDatasets = computed(() => datasets.value.filter((item) => item.projectId === selectedProject.value?.id && item.status === 'preprocessed' && item.listPath))
const selectedDataset = computed(() => readyDatasets.value.find((item) => item.id === selectedDatasetId.value))
const canStart = computed(() => Boolean(selectedDataset.value && !starting.value && !busy.value))
const busy = computed(() => items.value.some((item) => ['queued', 'running', 'cancelling'].includes(item.status)))

async function load() {
  if (!engine.client) return
  try {
    items.value = await engine.client.trainings()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function start() {
  if (!engine.client || !canStart.value || !selectedDataset.value?.listPath) return
  starting.value = true
  error.value = ''
  try {
    await engine.client.createTraining({
      dataset_list: selectedDataset.value.listPath,
      exp_name: expName.value.trim() || 'my_voice',
      s1_epochs: s1Epochs.value,
      s2_epochs: s2Epochs.value,
      batch_size: batchSize.value,
      num_workers: dataWorkers.value,
      force: force.value,
    })
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    starting.value = false
  }
}

async function cancel() {
  const active = items.value.find((item) => ['queued', 'running', 'cancelling'].includes(item.status))
  if (!engine.client || !active || cancelling.value) return
  cancelling.value = true
  try {
    await engine.client.cancelTraining(active.id)
    await load()
  } finally {
    cancelling.value = false
  }
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void load()
  },
  { immediate: true },
)

onMounted(() => {
  if (!selectedDatasetId.value && readyDatasets.value.length) selectedDatasetId.value = readyDatasets.value[0].id
  timer = window.setInterval(() => {
    if (busy.value) void load()
  }, 2000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>训练配置</h2>
          <p class="muted small">选择预处理完成的数据集，启动 V5 微调训练。</p>
        </div>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <label class="field">
        <span>预处理数据集</span>
        <select v-model="selectedDatasetId" class="input">
          <option value="">请选择</option>
          <option v-for="item in readyDatasets" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <small class="field-hint">需要先在「预处理」页完成文本、HuBERT、说话人向量与语义提取。</small>
      </label>
      <p v-if="!readyDatasets.length" class="muted small">还没有预处理完成的数据集，请先到「预处理」页面执行。</p>
      <div class="form-grid">
        <label class="field">
          <span>实验名</span>
          <input v-model="expName" class="input" />
          <small class="field-hint">模型与实验目录的名称，用于在「模型库」里区分。</small>
        </label>
        <label class="field">
          <span>S1 epochs</span>
          <input v-model.number="s1Epochs" class="input" type="number" min="1" max="50" />
          <small class="field-hint">GPT 阶段训练轮数（默认 5）。1 轮 = 遍历一遍数据集；越大越拟合，但更慢、更易过拟合。</small>
        </label>
        <label class="field">
          <span>S2 epochs</span>
          <input v-model.number="s2Epochs" class="input" type="number" min="1" max="50" />
          <small class="field-hint">SoVITS 阶段训练轮数（默认 2）。决定音色细节，常用 2–10；耗时比 S1 更长。</small>
        </label>
        <label class="field">
          <span>batch</span>
          <input v-model.number="batchSize" class="input" type="number" min="1" max="8" />
          <small class="field-hint">每步送入的切片数。显存 6GB 建议 1–2，12GB 可 2–4；显存不足会自动减半重试。</small>
        </label>
        <label class="field" style="grid-column: span 2">
          <span>DataLoader 进程数：{{ dataWorkers }}</span>
          <input v-model.number="dataWorkers" type="range" min="1" max="8" step="1" :disabled="!!busy" style="width:100%" />
          <small class="field-hint">{{ busy ? '任务进行中不可修改；下次启动任务时生效。' : '并行加载数据的进程数，CPU 核数多可调 2–4；过大反而占用内存。' }}</small>
        </label>
        <label class="check" style="grid-column: span 3">
          <input v-model="force" type="checkbox" />
          <span>不足 1 分钟也强制训练</span>
          <small class="field-hint">跳过“数据总时长 ≥ 60 秒”的检查，仅建议用于流程测试。</small>
        </label>
      </div>
      <div class="row gap" style="margin-top:14px">
        <button class="button primary" :disabled="!canStart" @click="start">{{ starting ? '启动中…' : '开始训练' }}</button>
        <button v-if="busy" class="button ghost" :disabled="cancelling" @click="cancel">{{ cancelling ? '停止中…' : '取消训练' }}</button>
      </div>
    </div>

  </section>
</template>
