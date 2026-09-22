<script setup lang="ts">
/** Brouillon / À valider / Validé / Refusé, one tone each (SPEC §9). */
import type { AssetStatus } from '@/api/files'
import { STATUS_META } from '@/utils/files'

defineProps<{ status: AssetStatus }>()
</script>

<template>
  <span
    class="inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium"
    :class="STATUS_META[status].tone"
  >
    {{ STATUS_META[status].label }}
  </span>
</template>
