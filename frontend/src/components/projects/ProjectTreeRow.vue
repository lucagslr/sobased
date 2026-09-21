<script setup lang="ts">
/**
 * One row of the "Arbre" view of the Projects page, and its children
 * (recursive). Indentation shows the level; a shell row is greyed and has no
 * details, because the user only has access to something below it.
 */
import { ChevronRight, Plus } from 'lucide-vue-next'
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import ColorDot from '@/components/ui/ColorDot.vue'
import { formatDateRange, MAX_DEPTH, type TreeNode } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

import StatusBadge from './StatusBadge.vue'

defineProps<{ node: TreeNode }>()
const emit = defineEmits<{ addChild: [node: TreeNode] }>()
const expanded = ref(true)
</script>

<template>
  <li>
    <div
      class="group flex min-h-12 items-center gap-2 border-b border-line py-2 pr-2"
      :style="{ paddingLeft: `${(node.depth - 1) * 1.25 + 0.25}rem` }"
    >
      <button
        v-if="node.children.length"
        type="button"
        class="flex size-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-fg"
        :aria-expanded="expanded"
        :aria-label="expanded ? `Replier ${node.name}` : `Déplier ${node.name}`"
        @click="expanded = !expanded"
      >
        <ChevronRight
          class="size-4 transition-transform"
          :class="expanded ? 'rotate-90' : ''"
          aria-hidden="true"
        />
      </button>
      <span v-else class="size-7 shrink-0" />

      <RouterLink
        :to="`/projets/${node.id}`"
        class="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1"
      >
        <span class="flex min-w-0 items-center gap-2">
          <ColorDot :color="node.color" size="md" />
          <span
            class="truncate font-medium"
            :class="node.is_shell ? 'text-muted italic' : 'group-hover:underline'"
          >
            {{ node.name }}
          </span>
        </span>
        <template v-if="!node.is_shell && node.status">
          <span class="text-xs text-muted">{{ node.type_name }}</span>
          <StatusBadge :status="node.status" :overdue="node.end_overdue" />
          <span class="hidden text-xs text-muted sm:inline">
            {{ formatDateRange(node.start_date, node.end_date) }}
          </span>
        </template>
        <span v-else class="text-xs text-muted">Accès partiel</span>
      </RouterLink>

      <button
        v-if="atLeast(node.my_role, 'editor') && node.depth < MAX_DEPTH"
        type="button"
        class="flex size-8 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-fg sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
        :aria-label="`Ajouter un sous-projet à ${node.name}`"
        @click="emit('addChild', node)"
      >
        <Plus class="size-4" aria-hidden="true" />
      </button>
    </div>
    <ul v-if="node.children.length && expanded">
      <ProjectTreeRow
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        @add-child="emit('addChild', $event)"
      />
    </ul>
  </li>
</template>
