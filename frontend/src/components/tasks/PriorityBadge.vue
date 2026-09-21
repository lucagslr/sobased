<script setup lang="ts">
/** Priority 1-5 as a pastel pill (5 = highest). `compact` shows "P5" only. */
import { PRIORITIES } from '@/utils/tasks'

defineProps<{ priority: number; compact?: boolean }>()
</script>

<template>
  <span
    class="inline-flex h-6 shrink-0 items-center rounded-full border border-black/10 px-2 text-xs font-semibold text-stone-800"
    :style="{ backgroundColor: PRIORITIES[priority]?.color }"
    :title="`Priorité ${priority} sur 5 : ${PRIORITIES[priority]?.label}`"
  >
    P{{ priority
    }}<span v-if="!compact" class="ml-1 font-medium">{{ PRIORITIES[priority]?.label }}</span>
  </span>
</template>
