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
  background: rgba(8, 10, 13, 0.78);
  backdrop-filter: blur(3px);
}
.confirm-dialog {
  width: min(420px, 100%);
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}
.confirm-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--muted);
  background: var(--panel-2);
  border: 1px solid var(--line);
}
.confirm-icon.danger {
  color: #f0a5a5;
  background: rgba(223, 91, 91, 0.12);
  border-color: rgba(223, 91, 91, 0.4);
}
.confirm-body h3 {
  margin: 1px 0 7px;
  font-size: 15px;
  color: var(--text);
}
.confirm-body p {
  margin: 0;
  color: var(--muted);
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
  min-height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.confirm-button.ghost {
  background: transparent;
  border-color: var(--line);
  color: var(--muted);
}
.confirm-button.ghost:hover {
  background: var(--panel-2);
  color: var(--text);
}
.confirm-button.primary {
  background: var(--accent);
  border-color: var(--accent);
  font-weight: 600;
}
.confirm-button.primary:hover {
  background: var(--accent-2);
}
.confirm-button.danger {
  background: var(--red);
  border-color: var(--red);
  font-weight: 600;
}
.confirm-button:hover {
  filter: brightness(1.06);
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
}</style>
