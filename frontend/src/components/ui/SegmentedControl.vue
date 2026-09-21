<script setup lang="ts" generic="T extends string">
/** Small exclusive choice (theme, later: list / kanban / calendar / gantt). */
import type { Component } from 'vue'

defineProps<{
  label: string
  options: { value: T; label: string; icon?: Component }[]
  /** Icon-only buttons; labels stay available to screen readers. */
  hideLabels?: boolean
}>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div
    role="radiogroup"
    :aria-label="label"
    class="inline-flex rounded-lg border border-line bg-surface-2 p-1"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      class="inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors"
      :class="model === option.value ? 'bg-surface text-fg shadow-sm' : 'text-muted hover:text-fg'"
      @click="model = option.value"
    >
      <component :is="option.icon" v-if="option.icon" class="size-4" aria-hidden="true" />
      <span :class="hideLabels && 'sr-only'">{{ option.label }}</span>
    </button>
  </div>
</template>
