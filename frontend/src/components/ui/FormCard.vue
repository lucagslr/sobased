<script setup lang="ts">
/** Titled block used by settings sections and similar forms. */
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <section class="rounded-2xl border border-line bg-surface p-5 sm:p-6">
    <h2 class="text-base font-semibold">{{ title }}</h2>
    <p v-if="description" class="mt-1 text-sm text-muted">{{ description }}</p>
    <div class="mt-5"><slot /></div>
  </section>
</template>
