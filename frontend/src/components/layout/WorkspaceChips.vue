<script setup lang="ts">
/**
 * The workspace filter as a row of chips, on the page itself: "Tous les
 * espaces", one chip per workspace, "Nouvel espace". Bound to the same
 * selection as the sidebar switcher, so both always agree.
 */
import { Layers, Plus } from 'lucide-vue-next'
import { computed } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'
import ChoiceChips from '@/components/ui/ChoiceChips.vue'
import { useWorkspacesStore, type WorkspaceSelection } from '@/stores/workspaces'

const emit = defineEmits<{ create: [] }>()
const workspaces = useWorkspacesStore()

const options = computed(() => [
  { value: 'all' as WorkspaceSelection, label: 'Tous les espaces', icon: Layers },
  ...workspaces.items.map((w) => ({
    value: w.id as WorkspaceSelection,
    label: w.name,
    color: w.color,
  })),
])
const selection = computed<WorkspaceSelection>({
  get: () => workspaces.selection,
  set: (value) => workspaces.select(value),
})
</script>

<template>
  <ChoiceChips
    v-if="workspaces.items.length"
    v-model="selection"
    label="Filtrer par espace"
    :options="options"
  >
    <BaseButton variant="ghost" size="sm" @click="emit('create')">
      <Plus class="size-4" aria-hidden="true" /> Nouvel espace
    </BaseButton>
  </ChoiceChips>
</template>
