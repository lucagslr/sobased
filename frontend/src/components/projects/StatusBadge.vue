<script setup lang="ts">
/** Project status as a neutral pill. Red is reserved for "end date passed". */
import type { ProjectStatus } from '@/api/projects'
import { STATUS_LABELS } from '@/utils/projects'

defineProps<{ status: ProjectStatus; overdue?: boolean }>()
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <span
      class="inline-flex h-6 items-center rounded-full border border-line bg-surface-2 px-2.5 text-xs font-medium"
      :class="
        status === 'done' || status === 'cancelled' || status === 'archived' ? 'text-muted' : ''
      "
    >
      {{ STATUS_LABELS[status] }}
    </span>
    <span
      v-if="overdue"
      class="inline-flex h-6 items-center rounded-full bg-danger-soft px-2.5 text-xs font-semibold text-danger"
    >
      Fin dépassée
    </span>
  </span>
</template>
