<script setup lang="ts">
/** Card used by every public form page (sign-in, sign-up, reset...). */
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="w-full max-w-sm">
    <h1 class="text-2xl font-semibold tracking-tight">{{ title }}</h1>
    <p v-if="subtitle" class="mt-2 text-sm text-muted">{{ subtitle }}</p>
    <div class="mt-8"><slot /></div>
    <div v-if="$slots.footer" class="mt-6 text-sm text-muted"><slot name="footer" /></div>
  </div>
</template>
