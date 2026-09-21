<script setup lang="ts">
/**
 * Toggle the tags of a workspace on an item, and create a new one inline.
 * Used for projects now; tasks, events and assets reuse it later.
 */
import { Plus } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import { workspacesApi } from '@/api/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { PASTEL_PALETTE } from '@/utils/projects'

const props = defineProps<{ workspaceId: number; canCreate?: boolean }>()
const model = defineModel<number[]>({ required: true })

const workspaces = useWorkspacesStore()
const ui = useUiStore()
const tags = computed(() => workspaces.tagsByWorkspace[props.workspaceId] ?? [])
const newName = ref('')
const creating = ref(false)

onMounted(() => workspaces.loadTags(props.workspaceId))

function toggle(id: number) {
  model.value = model.value.includes(id)
    ? model.value.filter((tagId) => tagId !== id)
    : [...model.value, id]
}

async function create() {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  try {
    // Next colour of the palette, so that new tags do not all look alike.
    const color = PASTEL_PALETTE[tags.value.length % PASTEL_PALETTE.length]
    const tag = await workspacesApi.createTag(props.workspaceId, name, color)
    await workspaces.loadTags(props.workspaceId, true)
    model.value = [...model.value, tag.id]
    newName.value = ''
  } catch (error) {
    const message = error instanceof ApiError ? (error.fieldErrors.name?.[0] ?? error.message) : ''
    ui.toast(message || "Le tag n'a pas pu être créé.", 'error')
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div>
    <p class="mb-1.5 text-sm font-medium">Tags</p>
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="tag in tags"
        :key="tag.id"
        type="button"
        :aria-pressed="model.includes(tag.id)"
        class="inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-medium transition-opacity"
        :class="
          model.includes(tag.id)
            ? 'border-black/10 text-stone-800'
            : 'border-line text-muted hover:text-fg'
        "
        :style="model.includes(tag.id) ? { backgroundColor: tag.color } : {}"
        @click="toggle(tag.id)"
      >
        {{ tag.name }}
      </button>
      <p v-if="!tags.length && !canCreate" class="text-sm text-muted">Aucun tag dans cet espace.</p>
    </div>
    <div v-if="canCreate" class="mt-2 flex gap-2">
      <input
        v-model="newName"
        type="text"
        maxlength="40"
        placeholder="Nouveau tag"
        aria-label="Nom du nouveau tag"
        class="h-8 min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 text-sm placeholder:text-muted"
        @keydown.enter.prevent="create"
      />
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-2.5 text-sm font-medium hover:bg-surface-2 disabled:opacity-50"
        :disabled="creating || !newName.trim()"
        @click="create"
      >
        <Plus class="size-3.5" aria-hidden="true" /> Ajouter
      </button>
    </div>
  </div>
</template>
