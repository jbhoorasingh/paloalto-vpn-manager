<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition ease-out duration-300 transform"
      enter-from-class="translate-x-full opacity-0"
      enter-to-class="translate-x-0 opacity-100"
      leave-active-class="transition ease-in duration-200 transform"
      leave-from-class="translate-x-0 opacity-100"
      leave-to-class="translate-x-full opacity-0"
    >
      <div
        v-if="visible"
        class="fixed right-4 top-4 z-[100] max-w-sm rounded-lg shadow-lg"
        :class="containerClasses"
        role="alert"
      >
        <div class="flex items-start gap-3 p-4">
          <!-- Icon -->
          <div class="flex-shrink-0">
            <!-- Success -->
            <svg v-if="type === 'success'" class="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <!-- Error -->
            <svg v-else-if="type === 'error'" class="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <!-- Warning -->
            <svg v-else-if="type === 'warning'" class="h-5 w-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <!-- Info -->
            <svg v-else class="h-5 w-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>

          <!-- Message -->
          <p class="text-sm font-medium" :class="textClass">
            {{ message }}
          </p>

          <!-- Close button -->
          <button
            class="ml-auto flex-shrink-0 rounded p-1 hover:bg-black/5 focus:outline-none"
            @click="dismiss"
          >
            <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps({
  message: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'info',
    validator: (v) => ['success', 'error', 'warning', 'info'].includes(v),
  },
  show: {
    type: Boolean,
    default: false,
  },
  duration: {
    type: Number,
    default: 3000,
  },
})

const emit = defineEmits(['dismiss'])

const visible = ref(false)
let timer = null

const typeStyles = {
  success: { container: 'bg-green-50 border border-green-200', text: 'text-green-800' },
  error: { container: 'bg-red-50 border border-red-200', text: 'text-red-800' },
  warning: { container: 'bg-yellow-50 border border-yellow-200', text: 'text-yellow-800' },
  info: { container: 'bg-blue-50 border border-blue-200', text: 'text-blue-800' },
}

import { computed } from 'vue'

const containerClasses = computed(() => (typeStyles[props.type] || typeStyles.info).container)
const textClass = computed(() => (typeStyles[props.type] || typeStyles.info).text)

function dismiss() {
  visible.value = false
  emit('dismiss')
}

function startTimer() {
  clearTimeout(timer)
  if (props.duration > 0) {
    timer = setTimeout(dismiss, props.duration)
  }
}

watch(
  () => props.show,
  (val) => {
    visible.value = val
    if (val) startTimer()
  },
  { immediate: true }
)

onUnmounted(() => {
  clearTimeout(timer)
})
</script>
