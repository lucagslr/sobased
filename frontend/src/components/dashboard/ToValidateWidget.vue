<script setup lang="ts">
/** "À valider": tasks and projects waiting for a decision (assets in phase 8). */
import { CircleCheckBig, FolderTree } from 'lucide-vue-next'

import type { ValidateItem } from '@/api/dashboard'
import ColorDot from '@/components/ui/ColorDot.vue'

defineProps<{ items: ValidateItem[] }>()
const emit = defineEmits<{ open: [item: ValidateItem] }>()

const KIND_LABELS = { task: 'Tâche', project: 'Projet', asset: 'Fichier' }
</script>

<template>
  <ul class="divide-y divide-line">
    <li v-for="item in items" :key="`${item.kind}-${item.id}`">
      <button
        type="button"
        class="flex w-full items-start gap-3 py-2.5 text-left"
        @click="emit('open', item)"
      >
        <component
          :is="item.kind === 'project' ? FolderTree : CircleCheckBig"
          class="mt-0.5 size-4 shrink-0 text-muted"
          aria-hidden="true"
        />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm font-medium hover:underline">{{ item.title }}</span>
          <span class="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            <ColorDot :color="item.project_color" />
            {{ KIND_LABELS[item.kind] }}
            <template v-if="item.kind !== 'project'"> · {{ item.project_name }}</template>
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>
