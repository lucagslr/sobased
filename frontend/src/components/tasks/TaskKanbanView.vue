<script setup lang="ts">
/**
 * Kanban: one column per status (SPECIFICATIONS §2), order inside a column
 * saved on the server. A card is dragged by its handle only, so that the board
 * still scrolls under a finger.
 *
 * Who may drag: editors, and the assignee of a task with the Commenter role
 * (decision D6: moving a card IS changing its status). Cards of the others
 * have no handle.
 */
import { ref, watch } from 'vue'
import draggable from 'vuedraggable'

import { ApiError } from '@/api/client'
import { type Task, tasksApi, type TaskStatus } from '@/api/tasks'
import { useUiStore } from '@/stores/ui'
import { TASK_STATUS_LABELS, TASK_STATUS_ORDER } from '@/utils/tasks'
import { dropPosition, type KanbanColumns, kanbanColumns } from '@/utils/taskViews'

import TaskCard from './TaskCard.vue'

const props = defineProps<{
  tasks: Task[]
  /** Project of the board: cards of its sub-projects show their project. */
  projectId: number
  canMove: (task: Task) => boolean
}>()
const emit = defineEmits<{ open: [task: Task]; changed: [] }>()

const ui = useUiStore()

// vuedraggable reorders these arrays in place while a card is dragged.
const columns = ref<KanbanColumns>(kanbanColumns(props.tasks))
watch(
  () => props.tasks,
  (tasks) => (columns.value = kanbanColumns(tasks)),
)

interface DragChange {
  added?: { element: Task; newIndex: number }
  moved?: { element: Task; newIndex: number }
}

async function onChange(status: TaskStatus, change: DragChange) {
  const drop = change.added ?? change.moved // "removed" is the other half of "added"
  if (!drop) return
  try {
    const moved = await tasksApi.move(
      drop.element.id,
      status,
      dropPosition(columns.value[status], drop.newIndex),
    )
    // Allowed on purpose (SPEC §7): starting a blocked task only warns.
    if (moved.warning) ui.toast(moved.warning, 'info')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "La carte n'a pas été déplacée.", 'error')
  }
  emit('changed') // the server is the reference for statuses and positions
}
</script>

<template>
  <!-- Phones: columns scroll sideways and snap one by one. -->
  <div
    class="no-scrollbar -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0 lg:snap-none"
  >
    <section
      v-for="status in TASK_STATUS_ORDER"
      :key="status"
      class="flex w-[82vw] max-w-80 shrink-0 snap-center flex-col rounded-2xl bg-surface-2 p-2.5 sm:w-72 lg:w-auto lg:max-w-none lg:min-w-44 lg:flex-1 lg:shrink"
      :aria-label="`Colonne ${TASK_STATUS_LABELS[status]}`"
    >
      <h3 class="flex items-center justify-between px-1.5 pt-1 pb-2.5 text-sm font-semibold">
        {{ TASK_STATUS_LABELS[status] }}
        <span class="font-normal text-muted">{{ columns[status].length }}</span>
      </h3>
      <draggable
        :list="columns[status]"
        group="kanban"
        item-key="id"
        handle=".kanban-handle"
        :animation="160"
        :force-fallback="true"
        ghost-class="opacity-40"
        class="min-h-24 flex-1 space-y-2"
        @change="onChange(status, $event)"
      >
        <template #item="{ element }: { element: Task }">
          <TaskCard
            :task="element"
            :show-project="element.project !== projectId"
            :movable="canMove(element)"
            @open="emit('open', element)"
          />
        </template>
      </draggable>
    </section>
  </div>
</template>
