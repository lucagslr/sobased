<script setup lang="ts">
/** Body of the task widgets (En retard, Aujourd'hui, 7 prochains jours). */
import type { Task } from '@/api/tasks'
import TaskRow from '@/components/tasks/TaskRow.vue'
import { useProjectsStore } from '@/stores/projects'
import { useAuthStore } from '@/stores/auth'
import { atLeast } from '@/utils/roles'

defineProps<{ tasks: Task[]; total: number }>()
const emit = defineEmits<{ open: [task: Task]; toggleDone: [task: Task] }>()

const projects = useProjectsStore()
const auth = useAuthStore()

// Same rule as everywhere: editors tick anything, an assigned commenter ticks
// their own task (decision D6). The server has the last word anyway.
function canComplete(task: Task): boolean {
  const role = projects.byId.get(task.project)?.my_role
  if (atLeast(role, 'editor')) return true
  const mine = task.assignees.some((user) => user.username === auth.user?.username)
  return mine && atLeast(role, 'commenter')
}
</script>

<template>
  <ul>
    <TaskRow
      v-for="task in tasks"
      :key="task.id"
      :task="task"
      show-project
      :can-complete="canComplete(task)"
      @open="emit('open', task)"
      @toggle-done="emit('toggleDone', task)"
    />
  </ul>
  <p v-if="total > tasks.length" class="pt-2 text-center text-xs text-muted">
    et {{ total - tasks.length }} de plus
  </p>
</template>
