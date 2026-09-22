<script setup lang="ts">
/**
 * One task on the kanban board. Same signals as a list row (SPEC §7): red +
 * "Urgent" when overdue, a padlock when a blocker is still open.
 */
import { GripVertical, Lock, MessageSquare, Repeat, SquareCheckBig } from 'lucide-vue-next'
import { computed } from 'vue'

import type { Task } from '@/api/tasks'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { CLOSED_STATUSES, formatTaskDate } from '@/utils/tasks'

import PriorityBadge from './PriorityBadge.vue'

const props = defineProps<{
  task: Task
  showProject?: boolean
  /** The user may drag this card to another column (editor, or D6 assignee). */
  movable?: boolean
}>()
const emit = defineEmits<{ open: [] }>()

const closed = computed(() => CLOSED_STATUSES.includes(props.task.status))
const checklistDone = computed(() => props.task.checklist.filter((item) => item.done).length)
</script>

<template>
  <article
    class="flex gap-1 rounded-xl border bg-surface p-3 shadow-sm"
    :class="task.is_overdue ? 'border-danger' : 'border-line'"
  >
    <!-- The handle is the only drag zone: the rest of the card scrolls and
         clicks normally, which matters on a phone. -->
    <span
      v-if="movable"
      class="kanban-handle -ml-1.5 flex w-5 shrink-0 cursor-grab touch-none items-start justify-center pt-0.5 text-muted"
      aria-hidden="true"
    >
      <GripVertical class="size-4" />
    </span>
    <button type="button" class="min-w-0 flex-1 text-left" @click="emit('open')">
      <span class="flex items-start gap-1.5">
        <Lock
          v-if="task.is_blocked"
          class="mt-0.5 size-3.5 shrink-0 text-muted"
          aria-label="Bloquée par une autre tâche"
        />
        <span
          class="text-sm leading-snug font-medium hover:underline"
          :class="[closed ? 'text-muted line-through' : '', task.is_overdue ? 'text-danger' : '']"
        >
          {{ task.title }}
        </span>
      </span>
      <span v-if="showProject" class="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
        <ColorDot :color="task.project_color" />
        <span class="truncate">{{ task.project_name }}</span>
      </span>
      <span class="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted">
        <span
          v-if="task.is_overdue"
          class="inline-flex h-5 items-center rounded-full bg-danger px-2 text-[11px] font-semibold tracking-wide text-white uppercase dark:text-stone-950"
        >
          Urgent
        </span>
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
      <span class="mt-2.5 flex items-center justify-between gap-2">
        <span class="flex -space-x-1.5">
          <AppAvatar
            v-for="user in task.assignees.slice(0, 4)"
            :key="user.username"
            :name="user.display_name"
            :src="user.avatar_url"
            :size="22"
            class="ring-2 ring-surface"
          />
        </span>
        <PriorityBadge :priority="task.priority" compact />
      </span>
    </button>
  </article>
</template>
