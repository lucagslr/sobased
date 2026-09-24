<script setup lang="ts" generic="T extends string | number">
/**
 * A row of pill buttons, one of which is selected: the quick filter of a
 * page (workspace, project, status…). Wraps on small screens; a trailing
 * slot takes an action button ("Nouvel espace").
 */
import type { Component } from 'vue'

import ColorDot from './ColorDot.vue'

defineProps<{
  label: string
  options: { value: T; label: string; color?: string | null; icon?: Component }[]
}>()
const model = defineModel<T>({ required: true })

const base = 'flex h-8 items-center gap-1.5 rounded-full border px-3 text-sm transition-colors'
function tone(active: boolean): string {
  return active ? 'border-fg bg-fg text-surface' : 'border-line text-muted hover:text-fg'
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2" role="group" :aria-label="label">
    <button
      v-for="option in options"
      :key="String(option.value)"
      type="button"
      :class="[base, tone(model === option.value)]"
      :aria-pressed="model === option.value"
      @click="model = option.value"
    >
      <component :is="option.icon" v-if="option.icon" class="size-3.5" aria-hidden="true" />
      <ColorDot v-else-if="option.color" :color="option.color" />
      {{ option.label }}
    </button>
    <slot />
  </div>
</template>
