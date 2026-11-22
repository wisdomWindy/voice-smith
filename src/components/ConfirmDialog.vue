<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
  }>(),
  {
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
  },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()

function onKey(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') emit('cancel')
  if (event.key === 'Enter') emit('confirm')
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
  },
)

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm">
      <div v-if="open" class="confirm-mask" @click.self="emit('cancel')">
        <div class="confirm-dialog" role="dialog" aria-modal="true" :aria-label="title">
          <div class="confirm-icon" :class="{ danger }">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path
                d="M12 8v5m0 3.5v.1M10.3 3.9 2.6 17.4A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.6L13.7 3.9a2 2 0 0 0-3.4 0Z"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
          <div class="confirm-body">
            <h3>{{ title }}</h3>
            <p>{{ message }}</p>
          </div>
          <div class="confirm-actions">
            <button type="button" class="confirm-button ghost" @click="emit('cancel')">
              {{ cancelText }}
            </button>
            <button
              type="button"
              class="confirm-button"
              :class="danger ? 'danger' : 'primary'"
              @click="emit('confirm')"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(4, 7, 12, 0.72);
  backdrop-filter: blur(3px);
}
.confirm-dialog {
  width: min(420px, 100%);
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 22px;
  border: 1px solid #263349;
  border-radius: 16px;
  background: linear-gradient(180deg, #151c27, #10151e);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}
.confirm-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #8ea6c9;
  background: #1b2637;
  border: 1px solid #2b3a52;
}
.confirm-icon.danger {
  color: #ff9d9d;
  background: #2a1517;
  border-color: #4b2323;
}
.confirm-body h3 {
  margin: 1px 0 7px;
  font-size: 16px;
  color: #eef3fb;
}
.confirm-body p {
  margin: 0;
  color: #9aa8bd;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-line;
}
.confirm-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  margin-top: 6px;
}
.confirm-button {
  min-height: 35px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1px solid transparent;
  font-size: 13px;
  color: #eaf0fa;
}
.confirm-button.ghost {
  background: transparent;
  border-color: #2b3a52;
  color: #aebbd0;
}
.confirm-button.ghost:hover {
  background: #1a2230;
}
.confirm-button.primary {
  background: linear-gradient(180deg, #6f8fff, #5b7df0);
  border-color: #5b7df0;
  font-weight: 600;
}
.confirm-button.danger {
  background: linear-gradient(180deg, #e05d5d, #c74444);
  border-color: #c74444;
  font-weight: 600;
}
.confirm-button:hover {
  filter: brightness(1.08);
}
.confirm-enter-active,
.confirm-leave-active {
  transition: opacity 0.16s ease;
}
.confirm-enter-active .confirm-dialog,
.confirm-leave-active .confirm-dialog {
  transition: transform 0.16s ease, opacity 0.16s ease;
}
.confirm-enter-from,
.confirm-leave-to {
  opacity: 0;
}
.confirm-enter-from .confirm-dialog,
.confirm-leave-to .confirm-dialog {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}
</style>
