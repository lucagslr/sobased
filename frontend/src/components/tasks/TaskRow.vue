<script setup lang="ts">
/**
 * One task in a list. Everything the spec wants visible at a glance: red +
 * "Urgent" when overdue, a padlock when a blocker is still open, priority,
 * due date, assignees, checklist progress.
 */
import { Check, Lock, MessageSquare, Repeat, SquareCheckBig } from 'lucide-vue-next'
import { computed } from 'vue'

import type { Task } from '@/api/tasks'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { CLOSED_STATUSES, formatTaskDate, TASK_STATUS_LABELS } from '@/utils/tasks'

import PriorityBadge from './PriorityBadge.vue'

const props = defineProps<{
  task: Task
  /** Show the project name (lists that mix several projects). */
  showProject?: boolean
  /** The user may tick the task done from the list. */
  canComplete?: boolean
}>()
const emit = defineEmits<{ open: []; toggleDone: [] }>()

const closed = computed(() => CLOSED_STATUSES.includes(props.task.status))
const checklistDone = computed(() => props.task.checklist.filter((item) => item.done).length)
</script>

<template>
  <li
    class="group flex items-start gap-3 border-b border-line px-1 py-3"
    :class="task.is_overdue ? 'bg-danger-soft/40' : ''"
  >
    <button
      type="button"
      class="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors disabled:cursor-default"
      :class="
        task.status === 'done'
          ? 'border-fg bg-fg text-bg'
          : 'border-muted text-transparent enabled:hover:border-fg enabled:hover:text-muted'
      "
      :disabled="!canComplete"
      :aria-label="task.status === 'done' ? 'Rouvrir la tâche' : 'Marquer comme terminée'"
      :aria-pressed="task.status === 'done'"
      @click="emit('toggleDone')"
    >
      <Check class="size-3.5" aria-hidden="true" />
    </button>

    <button type="button" class="min-w-0 flex-1 text-left" @click="emit('open')">
      <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Lock
          v-if="task.is_blocked"
          class="size-3.5 shrink-0 text-muted"
          aria-label="Bloquée par une autre tâche"
        />
        <span
          class="font-medium group-hover:underline"
          :class="[closed ? 'text-muted line-through' : '', task.is_overdue ? 'text-danger' : '']"
        >
          {{ task.title }}
        </span>
        <span
          v-if="task.is_overdue"
          class="inline-flex h-5 items-center rounded-full bg-danger px-2 text-[11px] font-semibold tracking-wide text-white uppercase dark:text-stone-950"
        >
          Urgent
        </span>
      </span>
      <span class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span v-if="showProject" class="inline-flex items-center gap-1.5">
          <ColorDot :color="task.project_color" /> {{ task.project_name }}
        </span>
        <span v-if="task.status !== 'todo'">{{ TASK_STATUS_LABELS[task.status] }}</span>
        <span v-if="task.due_at" :class="task.is_overdue ? 'font-semibold text-danger' : ''">
          {{ formatTaskDate(task.due_at, task.all_day) }}
        </span>
        <Repeat v-if="task.recurrence" class="size-3.5" aria-label="Tâche récurrente" />
        <span v-if="task.checklist.length" class="inline-flex items-center gap-1">
          <SquareCheckBig class="size-3.5" aria-hidden="true" />
          {{ checklistDone }}/{{ task.checklist.length }}
        </span>
        <span v-if="task.comments_count" class="inline-flex items-center gap-1">
          <MessageSquare class="size-3.5" aria-hidden="true" /> {{ task.comments_count }}
        </span>
      </span>
    </button>

    <div class="flex shrink-0 items-center gap-2">
      <span class="flex -space-x-1.5">
        <AppAvatar
          v-for="user in task.assignees.slice(0, 3)"
          :key="user.username"
          :name="user.display_name"
          :src="user.avatar_url"
          :size="24"
          class="ring-2 ring-bg"
        />
      </span>
      <PriorityBadge :priority="task.priority" compact />
    </div>
  </li>
</template>
