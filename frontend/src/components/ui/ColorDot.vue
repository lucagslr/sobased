<script setup lang="ts">
/** The pastel dot that identifies a project (or workspace, or tag) everywhere. */
withDefaults(defineProps<{ color: string; size?: 'sm' | 'md' }>(), { size: 'sm' })
</script>

<template>
  <span
    class="inline-block shrink-0 rounded-full border border-black/10"
    :class="size === 'sm' ? 'size-2.5' : 'size-3.5'"
    :style="{ backgroundColor: color }"
    aria-hidden="true"
  />
</template>
