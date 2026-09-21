<script setup lang="ts">
/**
 * Checklist of a task. Every action is saved at once (its own endpoints).
 * Pinned items show up in the "Todo épinglées" dashboard widget.
 * `canEdit`: add / rename / pin / delete. `canTick`: only tick (decision D6).
 */
import { Pin, Plus, Trash2 } from 'lucide-vue-next'
import { ref } from 'vue'

import { ApiError } from '@/api/client'
import { type ChecklistItem, tasksApi } from '@/api/tasks'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ taskId: number; canEdit: boolean; canTick: boolean }>()
const items = defineModel<ChecklistItem[]>({ required: true })
const ui = useUiStore()
const newTitle = ref('')

function fail(error: unknown) {
  ui.toast(
    error instanceof ApiError ? error.message : 'La checklist a refusé la modification.',
    'error',
  )
}

async function add() {
  const title = newTitle.value.trim()
  if (!title) return
  try {
    items.value = [...items.value, await tasksApi.addChecklistItem(props.taskId, title)]
    newTitle.value = ''
  } catch (error) {
    fail(error)
  }
}

async function patch(
  item: ChecklistItem,
  body: Parameters<typeof tasksApi.updateChecklistItem>[1],
) {
  try {
    const updated = await tasksApi.updateChecklistItem(item.id, body)
    items.value = items.value.map((current) => (current.id === item.id ? updated : current))
  } catch (error) {
    fail(error)
  }
}

async function remove(item: ChecklistItem) {
  try {
    await tasksApi.removeChecklistItem(item.id)
    items.value = items.value.filter((current) => current.id !== item.id)
  } catch (error) {
    fail(error)
  }
}
</script>

<template>
  <div>
    <ul v-if="items.length" class="mb-2 space-y-1">
      <li v-for="item in items" :key="item.id" class="group flex items-center gap-2">
        <input
          type="checkbox"
          class="size-4 shrink-0"
          :checked="item.done"
          :disabled="!canTick"
          :aria-label="`Cocher « ${item.title} »`"
          @change="patch(item, { done: !item.done })"
        />
        <input
          v-if="canEdit"
          type="text"
          :value="item.title"
          maxlength="240"
          class="h-8 min-w-0 flex-1 rounded-md border border-transparent bg-transparent px-1.5 text-sm hover:border-line focus:border-line"
          :class="item.done ? 'text-muted line-through' : ''"
          :aria-label="`Intitulé de « ${item.title} »`"
          @change="patch(item, { title: ($event.target as HTMLInputElement).value })"
        />
        <span v-else class="flex-1 text-sm" :class="item.done ? 'text-muted line-through' : ''">
          {{ item.title }}
        </span>
        <template v-if="canEdit">
          <button
            type="button"
            class="rounded-md p-1.5 hover:bg-surface-2"
            :class="item.pinned ? 'text-fg' : 'text-muted sm:opacity-0 sm:group-hover:opacity-100'"
            :aria-pressed="item.pinned"
            :aria-label="item.pinned ? 'Retirer du dashboard' : 'Épingler au dashboard'"
            :title="item.pinned ? 'Épinglée au dashboard' : 'Épingler au dashboard'"
            @click="patch(item, { pinned: !item.pinned })"
          >
            <Pin class="size-3.5" :class="item.pinned ? 'fill-current' : ''" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-danger sm:opacity-0 sm:group-hover:opacity-100"
            :aria-label="`Supprimer « ${item.title} »`"
            @click="remove(item)"
          >
            <Trash2 class="size-3.5" aria-hidden="true" />
          </button>
        </template>
      </li>
    </ul>
    <p v-else-if="!canEdit" class="text-sm text-muted">Aucun élément.</p>
    <form v-if="canEdit" class="flex gap-2" @submit.prevent="add">
      <input
        v-model="newTitle"
        type="text"
        maxlength="240"
        placeholder="Ajouter un élément"
        aria-label="Nouvel élément de checklist"
        class="h-9 min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 text-sm placeholder:text-muted"
      />
      <button
        type="submit"
        class="inline-flex h-9 items-center gap-1 rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface-2 disabled:opacity-50"
        :disabled="!newTitle.trim()"
      >
        <Plus class="size-3.5" aria-hidden="true" /> Ajouter
      </button>
    </form>
  </div>
</template>
