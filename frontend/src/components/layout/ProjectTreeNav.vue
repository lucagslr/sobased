<script setup lang="ts">
/**
 * Collapsible project tree of the sidebar (4 levels, colour dots).
 * Recursive: each node renders its children with the same component.
 * Open / closed state is remembered per node on this device.
 */
import { useStorage } from '@vueuse/core'
import { ChevronRight } from 'lucide-vue-next'
import { RouterLink, useRoute } from 'vue-router'

import ColorDot from '@/components/ui/ColorDot.vue'
import type { TreeNode } from '@/utils/projects'

defineProps<{ nodes: TreeNode[]; level?: number }>()

const route = useRoute()
// Shared by every level of the recursion (same storage key).
const collapsed = useStorage<Record<number, boolean>>('faiblegraine-tree-collapsed', {})

function toggle(id: number) {
  collapsed.value = { ...collapsed.value, [id]: !collapsed.value[id] }
}
</script>

<template>
  <ul :class="level ? 'ml-3 border-l border-line pl-1' : ''">
    <li v-for="node in nodes" :key="node.id">
      <div
        class="group flex h-8 items-center rounded-lg pr-2 text-sm transition-colors hover:bg-surface-2"
        :class="route.params.id === String(node.id) ? 'bg-surface-2 text-fg' : 'text-muted'"
      >
        <button
          v-if="node.children.length"
          type="button"
          class="flex size-6 shrink-0 items-center justify-center rounded hover:text-fg"
          :aria-label="collapsed[node.id] ? `Déplier ${node.name}` : `Replier ${node.name}`"
          :aria-expanded="!collapsed[node.id]"
          @click="toggle(node.id)"
        >
          <ChevronRight
            class="size-3.5 transition-transform"
            :class="collapsed[node.id] ? '' : 'rotate-90'"
            aria-hidden="true"
          />
        </button>
        <span v-else class="size-6 shrink-0" />
        <RouterLink
          :to="`/projets/${node.id}`"
          class="flex min-w-0 flex-1 items-center gap-2 py-1 hover:text-fg"
          :class="node.is_shell ? 'italic opacity-70' : ''"
          :title="node.is_shell ? 'Tu as accès à une partie de ce projet seulement' : undefined"
        >
          <ColorDot :color="node.color" />
          <span class="truncate">{{ node.name }}</span>
        </RouterLink>
      </div>
      <ProjectTreeNav
        v-if="node.children.length && !collapsed[node.id]"
        :nodes="node.children"
        :level="(level ?? 0) + 1"
      />
    </li>
  </ul>
</template>
