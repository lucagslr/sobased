<script setup lang="ts">
/** À payer (orange) > À justifier (red) > À rembourser > OK (SPECIFICATIONS §9). */
import type { DisplayStatus } from '@/api/finance'
import { DISPLAY_STATUS } from '@/utils/finance'

defineProps<{ status: DisplayStatus }>()
</script>

<template>
  <span
    v-if="status !== 'ok'"
    class="inline-flex h-5 shrink-0 items-center rounded-full px-2 text-[11px] font-semibold"
    :class="DISPLAY_STATUS[status].tone"
  >
    {{ DISPLAY_STATUS[status].label }}
  </span>
</template>
