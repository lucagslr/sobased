<script setup lang="ts">
/** What a page shows when there is nothing yet: icon, sentence, next action. */
import type { Component } from 'vue'

defineProps<{ icon: Component; title: string; text?: string }>()
</script>

<template>
  <div
    class="flex flex-col items-center rounded-2xl border border-dashed border-line px-6 py-14 text-center"
  >
    <span class="mb-4 inline-flex size-12 items-center justify-center rounded-full bg-surface-2">
      <component :is="icon" class="size-5 text-muted" aria-hidden="true" />
    </span>
    <h2 class="text-base font-semibold">{{ title }}</h2>
    <p v-if="text" class="mt-1 max-w-sm text-sm text-muted">{{ text }}</p>
    <div v-if="$slots.default" class="mt-5"><slot /></div>
  </div>
</template>
