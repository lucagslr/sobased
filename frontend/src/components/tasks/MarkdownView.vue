<script setup lang="ts">
/**
 * The ONLY place where v-html is used. `render()` escapes all user HTML and
 * validates links (see utils/markdown.ts and its tests).
 */
import { computed } from 'vue'

import { render } from '@/utils/markdown'

const props = defineProps<{ source: string }>()
const html = computed(() => render(props.source))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown text-[15px] leading-relaxed" v-html="html" />
</template>

<style scoped>
.markdown :deep(p + p),
.markdown :deep(ul),
.markdown :deep(ol) {
  margin-top: 0.5rem;
}
.markdown :deep(ul) {
  list-style: disc;
  padding-left: 1.25rem;
}
.markdown :deep(ol) {
  list-style: decimal;
  padding-left: 1.25rem;
}
.markdown :deep(a) {
  text-decoration: underline;
}
.markdown :deep(code) {
  border-radius: 4px;
  background: var(--c-surface-2);
  padding: 0.1rem 0.3rem;
  font-size: 0.9em;
}
.markdown :deep(.mention) {
  border-radius: 4px;
  background: var(--c-surface-2);
  padding: 0 0.2rem;
  font-weight: 600;
}
</style>
