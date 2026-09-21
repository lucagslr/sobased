<script setup lang="ts">
/** Avatar image, or initials on a neutral disc when there is none. */
import { computed } from 'vue'

import { initials } from '@/utils/initials'

const props = withDefaults(defineProps<{ name: string; src?: string | null; size?: number }>(), {
  size: 32,
})
const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * 0.4)}px`,
}))
</script>

<template>
  <img
    v-if="src"
    :src="src"
    :alt="name"
    :style="style"
    class="shrink-0 rounded-full object-cover"
  />
  <span
    v-else
    :style="style"
    :aria-label="name"
    role="img"
    class="inline-flex shrink-0 items-center justify-center rounded-full bg-surface-2 font-semibold text-muted"
  >
    {{ initials(name) }}
  </span>
</template>
