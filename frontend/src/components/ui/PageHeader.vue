<script setup lang="ts">
/** Page title (the single <h1>), optional subtitle, actions on the right. */
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <header class="mb-6 flex flex-wrap items-end justify-between gap-3 lg:mb-8">
    <div class="min-w-0">
      <h1 class="truncate text-2xl font-semibold tracking-tight">{{ title }}</h1>
      <p v-if="subtitle" class="mt-1 text-sm text-muted">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="flex items-center gap-2"><slot /></div>
  </header>
</template>
