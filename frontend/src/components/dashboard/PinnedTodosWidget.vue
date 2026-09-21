<script setup lang="ts">
/** "Todo épinglées": pinned checklist items, tickable right from the dashboard. */
import type { PinnedItem } from '@/api/tasks'
import ColorDot from '@/components/ui/ColorDot.vue'

defineProps<{ items: PinnedItem[] }>()
const emit = defineEmits<{ tick: [item: PinnedItem]; open: [item: PinnedItem] }>()
</script>

<template>
  <ul class="divide-y divide-line">
    <li v-for="item in items" :key="item.id" class="flex items-start gap-3 py-2.5">
      <input
        type="checkbox"
        class="mt-1 size-4 shrink-0"
        :aria-label="`Cocher « ${item.title} »`"
        @change="emit('tick', item)"
      />
      <button type="button" class="min-w-0 flex-1 text-left" @click="emit('open', item)">
        <span class="block text-sm font-medium hover:underline">{{ item.title }}</span>
        <span class="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
          <ColorDot :color="item.project_color" />
          <span class="truncate">{{ item.project_name }} · {{ item.task_title }}</span>
        </span>
      </button>
    </li>
  </ul>
</template>
