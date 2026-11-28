import { createRouter, createWebHashHistory } from 'vue-router'
import Workbench from './views/Workbench.vue'
import Doctor from './views/Doctor.vue'
import Voices from './views/Voices.vue'
import Training from './views/Training.vue'
import History from './views/History.vue'
import Models from './views/Models.vue'
import Assets from './views/Assets.vue'
import Settings from './views/Settings.vue'
import Datasets from './views/Datasets.vue'
import Preprocess from './views/Preprocess.vue'
import Tasks from './views/Tasks.vue'
import Projects from './views/Projects.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'inference',
      component: Workbench,
      meta: { title: '推理', desc: '文本 → 音色 → 参数 → 试听 → 导出，全部在本机完成。' },
    },
    {
      path: '/projects',
      name: 'projects',
      component: Projects,
      meta: { title: '项目', desc: '一个项目 = 一个工作区：数据集、训练、输出与日志相互隔离。' },
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: Datasets,
      meta: { title: '数据集', desc: '导入音频、转写与切片，生成可以训练的清单。' },
    },
    {
      path: '/preprocess',
      name: 'preprocess',
      component: Preprocess,
      meta: { title: '预处理', desc: '生成文本、HuBERT、说话人向量与语义 token，训练前必须先完成。' },
    },
    {
      path: '/training',
      name: 'training',
      component: Training,
      meta: { title: '训练', desc: 'S1 / S2 训练、进度与失败原因，显存不足会自动降 batch 重试。' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: Tasks,
      meta: { title: '任务', desc: '预处理、训练、推理统一在这里排队，切换页面不会中断。' },
    },
    {
      path: '/voices',
      name: 'voices',
      component: Voices,
      meta: { title: '音色库', desc: '已发布音色与情感参考，可直接用于推理。' },
    },
    {
      path: '/doctor',
      name: 'doctor',
      component: Doctor,
      meta: { title: '环境自检', desc: '逐项检查 Python / torch / CUDA / ffmpeg / 磁盘与模型资产。' },
    },
    {
      path: '/history',
      name: 'history',
      component: History,
      meta: { title: '历史', desc: '合成记录与导出，失败的批次可以重试。' },
    },
    {
      path: '/models',
      name: 'models',
      component: Models,
      meta: { title: '模型库', desc: '训练产出的 S1 / S2 权重，删除前确认没有被音色引用。' },
    },
    {
      path: '/assets',
      name: 'assets',
      component: Assets,
      meta: { title: '模型资产', desc: '推理所需权重与工具的状态、校验和离线导入。' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: Settings,
      meta: { title: '设置', desc: '引擎信息、更新检查与诊断包导出。' },
    },
  ],
})
