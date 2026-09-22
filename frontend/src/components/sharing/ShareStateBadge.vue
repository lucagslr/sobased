<script setup lang="ts">
/** Actif / Expiré / Épuisé / Révoqué. */
import type { ShareState } from '@/api/sharing'
import { STATE_META } from '@/utils/sharing'

defineProps<{ state: ShareState }>()
</script>

<template>
  <span
    class="inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium"
    :class="STATE_META[state].tone"
  >
    {{ STATE_META[state].label }}
  </span>
</template>
