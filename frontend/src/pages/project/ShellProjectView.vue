<script setup lang="ts">
/**
 * What a guest of a sub-project sees of its ancestors: the name, the colour,
 * and the way down to what they can actually open. Nothing else exists for
 * them (SPEC §6).
 */
import { Lock } from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { ShellProject } from '@/api/projects'
import ColorDot from '@/components/ui/ColorDot.vue'
import { useProjectsStore } from '@/stores/projects'

const props = defineProps<{ project: ShellProject }>()
const projects = useProjectsStore()
const children = computed(() => projects.childrenOf(props.project.id))
</script>

<template>
  <header class="mb-6">
    <h1 class="flex items-center gap-3 text-2xl font-semibold tracking-tight">
      <ColorDot :color="project.color" size="md" /> {{ project.name }}
    </h1>
    <p class="mt-2 flex items-center gap-2 text-sm text-muted">
      <Lock class="size-4" aria-hidden="true" />
      Tu as accès à une partie de ce projet seulement.
    </p>
  </header>

  <ul class="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
    <li v-for="child in children" :key="child.id">
      <RouterLink
        :to="`/projets/${child.id}`"
        class="flex h-14 items-center gap-3 px-4 hover:bg-surface-2"
      >
        <ColorDot :color="child.color" size="md" />
        <span class="font-medium" :class="child.is_shell ? 'text-muted italic' : ''">
          {{ child.name }}
        </span>
      </RouterLink>
    </li>
  </ul>
</template>
