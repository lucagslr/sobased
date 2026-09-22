<script setup lang="ts">
/** Recurring expenses of a scope, with their next due date. */
import { Repeat } from 'lucide-vue-next'
import { ref, watch } from 'vue'

import { financeApi, type RecurringExpense } from '@/api/finance'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { describeSchedule } from '@/utils/finance'
import { chf } from '@/utils/money'
import { formatDate } from '@/utils/projects'

import RecurringExpensePanel from './RecurringExpensePanel.vue'

const props = defineProps<{
  project?: number
  workspace?: number
  /** Projects a new recurring expense may go to (can_edit_finance). */
  editableProjects: number[]
  showProject?: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const expenses = ref<RecurringExpense[] | null>(null)
const panel = ref(false)
const editing = ref<RecurringExpense | null>(null)

async function load() {
  expenses.value = await financeApi.recurringExpenses({
    project: props.project,
    workspace: props.workspace,
  })
}
watch(() => [props.project, props.workspace], load, { immediate: true })

function openCreate() {
  editing.value = null
  panel.value = true
}
function openEdit(expense: RecurringExpense) {
  editing.value = expense
  panel.value = true
}
function onSaved() {
  load()
  emit('changed')
}
</script>

<template>
  <div>
    <div v-if="editableProjects.length" class="mb-3">
      <BaseButton variant="secondary" @click="openCreate">
        <Repeat class="size-4" aria-hidden="true" /> Nouveau frais récurrent
      </BaseButton>
    </div>

    <SkeletonBlock v-if="expenses === null" class="h-24" />
    <EmptyState
      v-else-if="!expenses.length"
      :icon="Repeat"
      title="Aucun frais récurrent"
      text="Abonnements, logiciels, loyer du local : une écriture « À payer » est créée à chaque échéance."
    />
    <ul v-else class="divide-y divide-line rounded-2xl border border-line">
      <li v-for="expense in expenses" :key="expense.id">
        <button
          type="button"
          class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-surface-2"
          @click="openEdit(expense)"
        >
          <span class="min-w-0 flex-1">
            <span class="font-medium" :class="expense.is_active ? '' : 'text-muted line-through'">
              {{ expense.label }}
            </span>
            <span class="block text-xs text-muted">
              <span v-if="showProject" class="inline-flex items-center gap-1.5">
                <ColorDot :color="expense.project_color" /> {{ expense.project_name }} ·
              </span>
              {{ expense.category_name }} ·
              {{ describeSchedule(expense.frequency, expense.day, expense.month) }}
              <template v-if="expense.next_due">
                · prochain le {{ formatDate(expense.next_due) }}</template
              >
              <template v-else-if="!expense.is_active"> · inactif</template>
            </span>
          </span>
          <span class="font-semibold tabular-nums">{{ chf(expense.amount) }}</span>
        </button>
      </li>
    </ul>

    <RecurringExpensePanel
      v-model:open="panel"
      :expense="editing"
      :project-choices="editableProjects"
      @saved="onSaved"
      @deleted="onSaved"
    />
  </div>
</template>
