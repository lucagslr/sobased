<script setup lang="ts">
/**
 * Header of one workspace in the Projects page: the workspace is the
 * container, the rows below it are its projects. From here: filter the
 * whole app on this workspace (or leave the filter), create a project in it.
 */
import { Filter, Plus, X } from 'lucide-vue-next'

import type { Workspace } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { ROLE_LABELS } from '@/utils/roles'

defineProps<{
  workspace: Workspace
  /** Projects of this workspace visible to me, sub-projects included. */
  count: number
  /** True when the app is filtered on this workspace. */
  filtered: boolean
  canCreate: boolean
}>()
const emit = defineEmits<{ create: []; filter: []; clear: [] }>()
</script>

<template>
  <div class="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
    <ColorDot :color="workspace.color" class="size-3" />
    <h2 class="text-base font-semibold">{{ workspace.name }}</h2>
    <span class="text-xs text-muted">
      Espace
      <template v-if="workspace.my_role"> · {{ ROLE_LABELS[workspace.my_role] }}</template>
      · {{ count }} projet{{ count > 1 ? 's' : '' }}
    </span>
    <span class="flex-1" />
    <BaseButton v-if="filtered" variant="ghost" size="sm" @click="emit('clear')">
      <X class="size-4" aria-hidden="true" /> Tous les espaces
    </BaseButton>
    <BaseButton v-else variant="ghost" size="sm" @click="emit('filter')">
      <Filter class="size-4" aria-hidden="true" /> Voir cet espace seul
    </BaseButton>
    <BaseButton v-if="canCreate" variant="secondary" size="sm" @click="emit('create')">
      <Plus class="size-4" aria-hidden="true" /> Projet
    </BaseButton>
  </div>
</template>
